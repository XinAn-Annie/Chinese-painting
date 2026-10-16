"""古画题跋 OCR 适配器。

输出统一为可供词云、原图高亮和人工复核使用的 JSON：
[{"text": "...", "bbox": [x1, y1, x2, y2],
  "confidence": 0.92, "orientation": "horizontal"}]

PaddleOCR 的不同版本返回结构不同，本文件同时兼容 3.x predict API
和旧版 ocr API。模型不会随仓库提交，首次运行时由 PaddleOCR 按配置下载。
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TEXT_RECOGNITION_MODEL = "PP-OCRv5_server_rec"
DEFAULT_TEXT_DETECTION_MODEL = "PP-OCRv6_medium_det"
DEFAULT_TEXTLINE_ORIENTATION_MODEL = "PP-LCNet_x1_0_textline_ori"
DEFAULT_TEXT_RECOGNITION_MODEL_DIR = None
DEFAULT_FALLBACK_RECOGNITION_MODEL_DIR = (
    PROJECT_ROOT / ".models" / "PP-OCRv5_server_rec_hcsu_stage1"
)
DEFAULT_TEXT_DETECTION_MODEL_DIR = (
    PROJECT_ROOT / ".models" / "PP-OCRv6_medium_det"
)
DEFAULT_TEXTLINE_ORIENTATION_MODEL_DIR = (
    PROJECT_ROOT / ".models" / "PP-LCNet_x1_0_textline_ori"
)


def _absolute_without_resolving_links(path: str | Path) -> Path:
    """Return an absolute path while preserving Windows junction aliases."""
    return Path(os.path.abspath(os.fspath(path)))


def _preload_torch_windows_dependencies() -> None:
    """Work around PyTorch DLL load-order failures in the shared Windows venv.

    PaddleX imports ModelScope, which imports PyTorch even though the OCR model
    itself uses PaddlePaddle.  Loading these CPU DLLs in dependency order keeps
    that optional import from preventing PaddleOCR startup.
    """
    if os.name != "nt":
        return
    torch_lib = Path(sys.prefix) / "Lib" / "site-packages" / "torch" / "lib"
    if not torch_lib.exists():
        return
    for filename in ("c10.dll", "torch_global_deps.dll", "torch_cpu.dll", "shm.dll"):
        dll = torch_lib / filename
        if dll.exists():
            ctypes.WinDLL(str(dll))


def _box_to_xyxy(box: Any) -> list[float]:
    """将四点文字框或 xyxy 文字框统一成 [x1,y1,x2,y2]。"""
    values = box.tolist() if hasattr(box, "tolist") else box
    if len(values) == 4 and all(isinstance(v, (int, float)) for v in values):
        return [float(v) for v in values]
    points = [(float(p[0]), float(p[1])) for p in values]
    return [
        min(p[0] for p in points),
        min(p[1] for p in points),
        max(p[0] for p in points),
        max(p[1] for p in points),
    ]


def _orientation(bbox: list[float]) -> str:
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    return "vertical" if height > width * 1.35 else "horizontal"


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).strip()


def _result_value(result: Any, key: str, default: Any = None) -> Any:
    if isinstance(result, dict):
        return result.get(key, default)
    try:
        return result[key]
    except (KeyError, IndexError, TypeError):
        return getattr(result, key, default)


def _first_available(result: Any, *keys: str) -> Any:
    for key in keys:
        value = _result_value(result, key, None)
        if value is not None:
            return value
    return []


def _parse_new_result(result: Any) -> list[dict[str, Any]]:
    texts = _first_available(result, "rec_texts")
    scores = _first_available(result, "rec_scores")
    # rec_boxes/rec_polys align with rec_texts. dt_polys also includes text
    # detections rejected before recognition, so indexing it shifts boxes.
    boxes = _first_available(result, "rec_boxes", "rec_polys", "dt_polys")
    items = []
    for index, text in enumerate(texts):
        text = _clean_text(text)
        if not text or index >= len(boxes):
            continue
        bbox = _box_to_xyxy(boxes[index])
        score = float(scores[index]) if index < len(scores) else 0.0
        items.append({"text": text, "bbox": bbox, "confidence": score, "orientation": _orientation(bbox)})
    return items


def _parse_old_result(result: Any) -> list[dict[str, Any]]:
    """解析 PaddleOCR 2.x 的 [[box, (text, score)], ...] 结构。"""
    items = []
    for line in result or []:
        if not isinstance(line, (list, tuple)) or len(line) < 2:
            continue
        try:
            bbox, value = line[0], line[1]
            text, score = value[0], value[1]
            text = _clean_text(text)
            if not text:
                continue
            xyxy = _box_to_xyxy(bbox)
            items.append({
                "text": text,
                "bbox": xyxy,
                "confidence": float(score),
                "orientation": _orientation(xyxy),
            })
        except (TypeError, ValueError, IndexError):
            continue
    return items


class AncientPaintingOCR:
    """PaddleOCR 封装。

    默认明确使用 ``PP-OCRv5_server_rec``，覆盖简体、繁体、手写、竖排、
    生僻字等多场景中文识别。模型权重由 PaddleOCR 在首次运行时下载。
    """

    def __init__(
        self,
        text_recognition_model_name: str = DEFAULT_TEXT_RECOGNITION_MODEL,
        text_recognition_model_dir: str | Path | None = DEFAULT_TEXT_RECOGNITION_MODEL_DIR,
        fallback_recognition_model_name: str = DEFAULT_TEXT_RECOGNITION_MODEL,
        fallback_recognition_model_dir: str | Path | None = DEFAULT_FALLBACK_RECOGNITION_MODEL_DIR,
        text_detection_model_name: str = DEFAULT_TEXT_DETECTION_MODEL,
        text_detection_model_dir: str | Path | None = DEFAULT_TEXT_DETECTION_MODEL_DIR,
        textline_orientation_model_name: str = DEFAULT_TEXTLINE_ORIENTATION_MODEL,
        textline_orientation_model_dir: str | Path | None = DEFAULT_TEXTLINE_ORIENTATION_MODEL_DIR,
        min_confidence: float = 0.30,
        fallback_trigger_confidence: float = 0.60,
    ):
        _preload_torch_windows_dependencies()
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise RuntimeError(
                "未安装 PaddleOCR，请先运行: pip install -r requirements.txt"
            ) from exc

        self.min_confidence = min_confidence
        self.fallback_trigger_confidence = fallback_trigger_confidence
        self.text_recognition_model_name = text_recognition_model_name
        self.fallback_recognition_model_name = fallback_recognition_model_name
        self.text_detection_model_name = text_detection_model_name
        self.textline_orientation_model_name = textline_orientation_model_name
        self.text_recognition_model_dir = (
            _absolute_without_resolving_links(text_recognition_model_dir)
            if text_recognition_model_dir
            else None
        )
        self.fallback_recognition_model_dir = (
            _absolute_without_resolving_links(fallback_recognition_model_dir)
            if fallback_recognition_model_dir
            else None
        )
        self.text_detection_model_dir = (
            _absolute_without_resolving_links(text_detection_model_dir)
            if text_detection_model_dir
            else None
        )
        self.textline_orientation_model_dir = (
            _absolute_without_resolving_links(textline_orientation_model_dir)
            if textline_orientation_model_dir else None
        )
        for label, path in (
            ("主识别模型", self.text_recognition_model_dir),
            ("HCSU 单字备用模型", self.fallback_recognition_model_dir),
            ("文字检测模型", self.text_detection_model_dir),
            ("文字方向模型", self.textline_orientation_model_dir),
        ):
            if path and not path.exists():
                raise FileNotFoundError(f"{label}不存在: {path}")
        options = {
            "text_detection_model_name": text_detection_model_name,
            "text_recognition_model_name": text_recognition_model_name,
            "textline_orientation_model_name": textline_orientation_model_name,
            "use_doc_orientation_classify": False,
            "use_doc_unwarping": False,
            "use_textline_orientation": True,
            # PaddlePaddle 3.x + Windows 上 oneDNN 对部分 PIR 属性支持不完整，
            # 会在文本检测阶段抛出 ConvertPirAttribute2RuntimeAttribute。
            # 关闭它仍使用同一 OCR 模型，但走稳定的 CPU 推理路径。
            "enable_mkldnn": False,
        }
        try:
            import paddle
            self.device = "gpu:0" if paddle.device.is_compiled_with_cuda() else "cpu"
        except Exception:
            self.device = "cpu"
        options["device"] = self.device
        if self.text_recognition_model_dir:
            options["text_recognition_model_dir"] = str(self.text_recognition_model_dir)
        if self.text_detection_model_dir:
            options["text_detection_model_dir"] = str(self.text_detection_model_dir)
        if self.textline_orientation_model_dir:
            options["textline_orientation_model_dir"] = str(self.textline_orientation_model_dir)
        try:
            self.engine = PaddleOCR(**options)
        except TypeError as exc:
            raise RuntimeError(
                "当前 PaddleOCR 不支持显式指定文字识别模型；请安装项目要求的 "
                "PaddleOCR 3.x。"
            ) from exc
        self._fallback_engine = None

    def _get_fallback_engine(self):
        """Lazily load the HCSU recognizer without replacing the line recognizer."""
        if self._fallback_engine is not None:
            return self._fallback_engine
        if self.fallback_recognition_model_dir is None:
            return None
        from paddleocr import TextRecognition

        self._fallback_engine = TextRecognition(
            model_name=self.fallback_recognition_model_name,
            model_dir=str(self.fallback_recognition_model_dir),
            device=self.device,
            enable_mkldnn=False,
        )
        return self._fallback_engine

    def _fallback_single_character(
        self, image: str, item: dict[str, Any]
    ) -> dict[str, Any]:
        """Recheck one low-confidence Han character with the HCSU model."""
        text = item.get("text", "")
        if (
            len(text) != 1
            or not re.fullmatch(r"[\u3400-\u9fff]", text)
            or float(item.get("confidence", 0)) >= self.fallback_trigger_confidence
        ):
            item["recognizer"] = "official"
            return item
        try:
            engine = self._get_fallback_engine()
        except Exception as exc:
            item["recognizer"] = "official"
            item["fallback_error"] = str(exc)
            return item
        if engine is None:
            item["recognizer"] = "official"
            return item

        bbox = item["bbox"]
        with Image.open(image) as source:
            width, height = source.size
            x1 = max(0, int(bbox[0]))
            y1 = max(0, int(bbox[1]))
            x2 = min(width, max(x1 + 1, int(bbox[2] + 0.999)))
            y2 = min(height, max(y1 + 1, int(bbox[3] + 0.999)))
            crop = source.crop((x1, y1, x2, y2)).convert("RGB")
            descriptor, temp_name = tempfile.mkstemp(suffix=".png")
            os.close(descriptor)
            crop_path = Path(temp_name)
            crop.save(crop_path, format="PNG")
        try:
            try:
                predictions = engine.predict(str(crop_path)) or []
            except Exception as exc:
                item["recognizer"] = "official"
                item["fallback_error"] = str(exc)
                return item
            best_text = ""
            best_score = 0.0
            for prediction in predictions:
                candidate = _clean_text(_result_value(prediction, "rec_text", ""))
                score = float(_result_value(prediction, "rec_score", 0.0) or 0.0)
                if re.fullmatch(r"[\u3400-\u9fff]", candidate) and score > best_score:
                    best_text, best_score = candidate, score
            item["primary_text"] = text
            item["primary_confidence"] = float(item.get("confidence", 0))
            item["fallback_text"] = best_text
            item["fallback_confidence"] = best_score
            if best_text and best_score > item["primary_confidence"]:
                item["text"] = best_text
                item["confidence"] = best_score
                item["recognizer"] = "hcsu_single_character_fallback"
            else:
                item["recognizer"] = "official"
            return item
        finally:
            crop_path.unlink(missing_ok=True)

    def recognize(self, image: str | Path) -> list[dict[str, Any]]:
        image = str(image)
        if not Path(image).exists():
            raise FileNotFoundError(image)

        if hasattr(self.engine, "predict"):
            raw = self.engine.predict(image)
            items: list[dict[str, Any]] = []
            for result in raw or []:
                items.extend(_parse_new_result(result))
        else:
            raw = self.engine.ocr(image, cls=True)
            items = _parse_old_result(raw[0] if raw and isinstance(raw[0], list) else raw)

        reviewed = [self._fallback_single_character(image, item) for item in items]
        return [item for item in reviewed if item["confidence"] >= self.min_confidence]


def recognize_file(image: str | Path, output: str | Path | None = None, **kwargs: Any) -> list[dict[str, Any]]:
    results = AncientPaintingOCR(**kwargs).recognize(image)
    if output:
        Path(output).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="使用 PaddleOCR 识别古画题跋并输出 JSON")
    parser.add_argument("image", help="古画图片路径")
    parser.add_argument("-o", "--output", help="结果 JSON 路径；不填写则输出到终端")
    parser.add_argument(
        "--rec-model",
        default=DEFAULT_TEXT_RECOGNITION_MODEL,
        help=f"PaddleOCR 文字识别模型，默认 {DEFAULT_TEXT_RECOGNITION_MODEL}",
    )
    parser.add_argument(
        "--rec-model-dir",
        default=None,
        help="官方主识别模型目录；留空时由 PaddleOCR 管理官方权重",
    )
    parser.add_argument(
        "--fallback-rec-model-dir",
        default=str(DEFAULT_FALLBACK_RECOGNITION_MODEL_DIR),
        help="HCSU 低置信度单字备用模型目录",
    )
    parser.add_argument("--min-confidence", type=float, default=0.30)
    args = parser.parse_args()
    results = recognize_file(
        args.image,
        args.output,
        text_recognition_model_name=args.rec_model,
        text_recognition_model_dir=args.rec_model_dir,
        fallback_recognition_model_dir=args.fallback_rec_model_dir,
        min_confidence=args.min_confidence,
    )
    if not args.output:
        print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
