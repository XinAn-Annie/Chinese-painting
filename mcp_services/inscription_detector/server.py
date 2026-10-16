"""Local ancient-painting inscription-region detector.

Run this service with the training virtual environment that contains
PyTorch and Ultralytics. It accepts JSON with a base64 encoded image so the
file can be called directly from the portable HTML demo.
"""

from __future__ import annotations

import base64
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from flask import Flask, jsonify, request
from flask_cors import CORS
from ultralytics import YOLO


ROOT = Path(__file__).resolve().parent
MODEL_PATH = Path(os.getenv("INSCRIPTION_MODEL", ROOT / "models" / "inscription_detector_best.pt"))
HOST = "127.0.0.1"
PORT = 8000
CONFIDENCE = float(os.getenv("INSCRIPTION_DETECTOR_CONFIDENCE", "0.35"))

# Frequencies of annotated box centres in the training split, from left to
# right and top to bottom. This is only a reading-order hint: lower and edge
# regions are still passed to OCR when the detector finds them.
X_FREQUENCY = (286, 259, 180, 203, 353)
Y_FREQUENCY = (536, 284, 309, 80, 72)


def reading_priority(box: list[float], confidence: float, width: int, height: int) -> float:
    cx = (box[0] + box[2]) / (2 * width)
    cy = (box[1] + box[3]) / (2 * height)
    x_bin = min(4, max(0, int(cx * 5)))
    y_bin = min(4, max(0, int(cy * 5)))
    spatial = (X_FREQUENCY[x_bin] / 353 + Y_FREQUENCY[y_bin] / 536) / 2
    return round(0.9 * confidence + 0.1 * spatial, 4)

try:
    import torch

    DEVICE = 0 if torch.cuda.is_available() else "cpu"
except Exception:
    DEVICE = "cpu"

print(f"Loading inscription detector: {MODEL_PATH}", flush=True)
MODEL = YOLO(str(MODEL_PATH))
print(f"Detector loaded; device={DEVICE}", flush=True)

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})


@app.get("/api/health")
def health():
    return jsonify({"ok": True, "service": "inscription-detector", "device": str(DEVICE)})


@app.post("/api/detect-inscriptions")
def detect_inscriptions():
    try:
        body = request.get_json(silent=True) or {}
        encoded = body.get("image_base64", "")
        if "," in encoded:
            encoded = encoded.split(",", 1)[1]
        image_bytes = base64.b64decode(encoded, validate=True)
        if not image_bytes:
            raise ValueError("image_base64 is empty")
        with NamedTemporaryFile(suffix=".png", delete=False) as temp:
            temp.write(image_bytes)
            temp_path = Path(temp.name)
        try:
            result = MODEL.predict(
                source=str(temp_path), imgsz=1024, conf=CONFIDENCE,
                device=DEVICE, verbose=False,
            )[0]
            height, width = result.orig_shape
            regions = []
            for box, score in zip(result.boxes.xyxy.tolist(), result.boxes.conf.tolist()):
                x1, y1, x2, y2 = [float(v) for v in box]
                bbox = [x1, y1, x2, y2]
                regions.append({
                    "bbox": bbox,
                    "confidence": float(score),
                    "priority": reading_priority(bbox, float(score), width, height),
                })
            regions.sort(key=lambda item: item["priority"], reverse=True)
            return jsonify({"width": int(width), "height": int(height), "regions": regions})
        finally:
            temp_path.unlink(missing_ok=True)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=False, threaded=True)
