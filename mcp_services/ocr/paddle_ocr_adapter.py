"""古画题跋 OCR 适配器。

输出统一为可供词云、原图高亮和人工复核使用的 JSON：
[{"text": "...", "bbox": [x1, y1, x2, y2],
  "confidence": 0.92, "orientation": "horizontal"}]

PaddleOCR 的不同版本返回结构不同，本文件同时兼容 3.x predict API
和旧版 ocr API。模型不会随仓库提交，首次运行时由 PaddleOCR 按配置下载。
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


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

    ``lang`` 优先使用 ``chinese_cht``，以兼容繁体中文；若本地安装的
    PaddleOCR 版本不接受该名称，会自动回退到 ``ch``，并在运行日志中提示。
    """

    def __init__(self, lang: str = "chinese_cht", min_confidence: float = 0.60):
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise RuntimeError(
                "未安装 PaddleOCR，请先运行: pip install -r requirements.txt"
            ) from exc

        self.min_confidence = min_confidence
        self.lang = lang
        options = {
            "lang": lang,
            "use_doc_orientation_classify": False,
            "use_doc_unwarping": False,
            "use_textline_orientation": True,
            # PaddlePaddle 3.x + Windows 上 oneDNN 对部分 PIR 属性支持不完整，
            # 会在文本检测阶段抛出 ConvertPirAttribute2RuntimeAttribute。
            # 关闭它仍使用同一 OCR 模型，但走稳定的 CPU 推理路径。
            "enable_mkldnn": False,
        }
        try:
            self.engine = PaddleOCR(**options)
        except Exception:
            # 兼容旧版 PaddleOCR；不要因为新参数不可用而阻塞项目原型。
            try:
                self.engine = PaddleOCR(lang=lang)
            except Exception:
                # 部分版本把繁体中文模型名称收敛为 ch；由调用者在结果中保留原文。
                self.lang = "ch"
                self.engine = PaddleOCR(lang="ch")

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

        return [item for item in items if item["confidence"] >= self.min_confidence]


def recognize_file(image: str | Path, output: str | Path | None = None, **kwargs: Any) -> list[dict[str, Any]]:
    results = AncientPaintingOCR(**kwargs).recognize(image)
    if output:
        Path(output).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="使用 PaddleOCR 识别古画题跋并输出 JSON")
    parser.add_argument("image", help="古画图片路径")
    parser.add_argument("-o", "--output", help="结果 JSON 路径；不填写则输出到终端")
    parser.add_argument("--lang", default="chinese_cht", help="PaddleOCR 语言模型，默认 chinese_cht")
    parser.add_argument("--min-confidence", type=float, default=0.60)
    args = parser.parse_args()
    results = recognize_file(args.image, args.output, lang=args.lang, min_confidence=args.min_confidence)
    if not args.output:
        print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
