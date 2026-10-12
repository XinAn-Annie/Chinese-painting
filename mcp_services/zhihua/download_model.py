"""从 ModelScope 下载并校验本地 Qwen 模型。"""

from __future__ import annotations

import argparse
from pathlib import Path

from modelscope import snapshot_download


MODEL_ID = "Qwen/Qwen2.5-VL-3B-Instruct"


def is_complete(path: Path) -> bool:
    required = [
        path / "config.json",
        path / "model.safetensors.index.json",
        path / "model-00001-of-00002.safetensors",
        path / "model-00002-of-00002.safetensors",
        path / "tokenizer.json",
    ]
    return all(item.is_file() and item.stat().st_size > 0 for item in required) and not any(path.rglob("*.incomplete"))


def main() -> None:
    parser = argparse.ArgumentParser(description="下载知画使用的 Qwen2.5-VL 模型")
    parser.add_argument("--target", type=Path, required=True)
    args = parser.parse_args()
    target = args.target.expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    snapshot_download(model_id=MODEL_ID, local_dir=str(target), max_workers=4)
    if not is_complete(target):
        raise RuntimeError(f"模型文件不完整，可重新运行启动器继续下载：{target}")
    print(f"Qwen 模型下载并校验完成：{target}")


if __name__ == "__main__":
    main()
