"""Evaluate PP-OCRv5_server_rec on a labelled calligraphy manifest.

Recognition-only mode measures the recognizer on already-cropped characters.
System mode additionally runs detection and separates no-box failures from
wrong-text failures.  Results are written incrementally so interrupted CPU runs
can resume safely.
"""

from __future__ import annotations

import argparse
import ctypes
import csv
import json
import os
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


MODEL_NAME = "PP-OCRv5_server_rec"


def preload_torch_windows_dependencies() -> None:
    if os.name != "nt":
        return
    torch_lib = Path(sys.prefix) / "Lib" / "site-packages" / "torch" / "lib"
    for filename in ("c10.dll", "torch_global_deps.dll", "torch_cpu.dll", "shm.dll"):
        dll = torch_lib / filename
        if dll.exists():
            ctypes.WinDLL(str(dll))


def value(result: Any, key: str, default: Any = None) -> Any:
    if isinstance(result, dict):
        return result.get(key, default)
    try:
        return result[key]
    except (KeyError, IndexError, TypeError):
        return getattr(result, key, default)


def normalized(text: str) -> str:
    return unicodedata.normalize("NFKC", str(text)).replace(" ", "").strip()


def load_manifest(path: Path, limit: int | None) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    return rows[:limit] if limit else rows


def load_completed(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return {row["sample_id"] for row in csv.DictReader(stream)}


def append_row(path: Path, row: dict[str, Any]) -> None:
    exists = path.exists()
    with path.open("a", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(row))
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def recognition_prediction(model: Any, image_path: str) -> tuple[str, float]:
    outputs: Iterable[Any] = model.predict(input=image_path, batch_size=1)
    result = next(iter(outputs), None)
    if result is None:
        return "", 0.0
    return str(value(result, "rec_text", "")), float(value(result, "rec_score", 0.0) or 0.0)


def system_prediction(model: Any, image_path: str) -> tuple[str, float, int]:
    texts: list[str] = []
    scores: list[float] = []
    detected = 0
    for result in model.predict(image_path) or []:
        boxes = value(result, "dt_polys", []) or []
        detected += len(boxes)
        texts.extend(str(x) for x in (value(result, "rec_texts", []) or []))
        scores.extend(float(x) for x in (value(result, "rec_scores", []) or []))
    best = max(scores) if scores else 0.0
    return "".join(texts), best, detected


def write_summary(results_path: Path, summary_path: Path, model_name: str, mode: str) -> None:
    with results_path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    by_style: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        by_style[row["style"]]["total"] += 1
        by_style[row["style"]][row["failure_type"]] += 1
    summary = {
        "model": model_name,
        "mode": mode,
        "total": len(rows),
        "by_style": {style: dict(counts) for style, counts in sorted(by_style.items())},
        "definitions": {
            "correct": "规范化后预测与原始单字标签完全一致",
            "detection_error": "完整OCR模式未产生任何文字检测框",
            "recognition_error": "已有裁切或检测框，但预测文字不等于标签",
        },
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser(description="运行 PP-OCRv5 书法识别基线")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--mode", choices=("recognition", "system"), default="recognition")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    results_path = args.output_dir / f"results_{args.mode}.csv"
    summary_path = args.output_dir / f"summary_{args.mode}.json"
    rows = load_manifest(args.manifest, args.limit)
    completed = load_completed(results_path)

    os.environ.setdefault("PADDLE_PDX_MODEL_SOURCE", "BOS")
    preload_torch_windows_dependencies()
    if args.mode == "recognition":
        from paddleocr import TextRecognition

        model = TextRecognition(model_name=MODEL_NAME, enable_mkldnn=False)
        predict = lambda path: (*recognition_prediction(model, path), 1)
    else:
        from paddleocr import PaddleOCR

        model = PaddleOCR(
            text_recognition_model_name=MODEL_NAME,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            enable_mkldnn=False,
        )
        predict = lambda path: system_prediction(model, path)

    for index, source in enumerate(rows, 1):
        if source["sample_id"] in completed:
            continue
        prediction, confidence, detected = predict(source["image_path"])
        expected_norm = normalized(source["label"])
        prediction_norm = normalized(prediction)
        if prediction_norm == expected_norm:
            failure_type = "correct"
        elif args.mode == "system" and detected == 0:
            failure_type = "detection_error"
        else:
            failure_type = "recognition_error"
        append_row(results_path, {
            "sample_id": source["sample_id"],
            "style": source["style"],
            "label": source["label"],
            "prediction": prediction,
            "confidence": f"{confidence:.6f}",
            "detected_boxes": detected,
            "failure_type": failure_type,
            "image_path": source["image_path"],
        })
        print(f"[{index}/{len(rows)}] {source['sample_id']} {failure_type}: {source['label']} -> {prediction}", flush=True)

    write_summary(results_path, summary_path, MODEL_NAME, args.mode)
    print(f"结果: {results_path}")
    print(f"汇总: {summary_path}")


if __name__ == "__main__":
    main()
