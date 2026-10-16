"""Single-process ArtGenome web and API service on 127.0.0.1:8000."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from flask import Flask, jsonify, redirect, send_from_directory
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.serving import run_simple

HOST = "127.0.0.1"
PORT = 8000
ROOT = Path(__file__).resolve().parent


def load_service(module_name: str, path: Path):
    service_dir = str(path.parent)
    if service_dir not in sys.path:
        sys.path.insert(0, service_dir)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载服务：{path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


ocr_service = load_service("artgenome_ocr_service", ROOT / "mcp_services" / "ocr" / "server.py")
detector_service = load_service(
    "artgenome_inscription_service",
    ROOT / "mcp_services" / "inscription_detector" / "server.py",
)
zhihua_service = load_service("artgenome_zhihua_service", ROOT / "mcp_services" / "zhihua" / "server.py")

app = Flask(__name__)


@app.get("/api/health")
def health():
    return jsonify({
        "ok": True,
        "service": "art-genome",
        "port": PORT,
        "services": ["inscription-detector", "paddleocr", "zhihua"],
    })


@app.get("/")
def index():
    return redirect("/web_demo/index.html")


@app.get("/<path:filename>")
def static_files(filename: str):
    return send_from_directory(ROOT, filename)


application = DispatcherMiddleware(app.wsgi_app, {
    "/services/inscription-detector": detector_service.app,
    "/services/ocr": ocr_service.app,
    "/services/zhihua": zhihua_service.app,
})


if __name__ == "__main__":
    run_simple(HOST, PORT, application, threaded=True, use_reloader=False)
