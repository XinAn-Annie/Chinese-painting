"""本地 OCR HTTP 服务，供 web_demo/index.html 调用。"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS

from paddle_ocr_adapter import (
    AncientPaintingOCR,
    DEFAULT_TEXT_RECOGNITION_MODEL,
    DEFAULT_TEXT_RECOGNITION_MODEL_DIR,
)

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})
ocr = None


@app.get("/api/health")
def health():
    return jsonify({
        "ok": True,
        "service": "paddleocr",
        "loaded": ocr is not None,
        "text_recognition_model": (
            ocr.text_recognition_model_name if ocr is not None
            else os.getenv("OCR_TEXT_RECOGNITION_MODEL", DEFAULT_TEXT_RECOGNITION_MODEL)
        ),
        "text_recognition_model_dir": (
            str(ocr.text_recognition_model_dir) if ocr is not None
            else os.getenv(
                "OCR_TEXT_RECOGNITION_MODEL_DIR",
                str(DEFAULT_TEXT_RECOGNITION_MODEL_DIR),
            )
        ),
    })


@app.post("/api/ocr")
def recognize():
    global ocr
    uploaded = request.files.get("image")
    if uploaded is None or not uploaded.filename:
        return jsonify({"error": "请上传图片文件"}), 400
    suffix = Path(uploaded.filename).suffix.lower() or ".png"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
        uploaded.save(temp)
        temp_path = temp.name
    try:
        if ocr is None:
            ocr = AncientPaintingOCR(
                text_recognition_model_name=os.getenv(
                    "OCR_TEXT_RECOGNITION_MODEL", DEFAULT_TEXT_RECOGNITION_MODEL
                ),
                text_recognition_model_dir=os.getenv(
                    "OCR_TEXT_RECOGNITION_MODEL_DIR",
                    str(DEFAULT_TEXT_RECOGNITION_MODEL_DIR),
                ),
                min_confidence=float(os.getenv("OCR_MIN_CONFIDENCE", "0.60")),
            )
        return jsonify({"items": ocr.recognize(temp_path)})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        Path(temp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8004, debug=False)
