"""下载并校验知画使用的 Qwen 模型。

默认先使用 ModelScope 的并行与断点续传能力；ModelScope 失败时，自动从
GitHub Release 下载小于 2 GiB 的分卷，逐卷校验后合并完整权重。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import urllib.request
import zipfile
from pathlib import Path

from modelscope import snapshot_download


MODEL_ID = "Qwen/Qwen2.5-VL-3B-Instruct"
MANIFEST_PATH = Path(__file__).with_name("qwen_release_manifest.json")
BUFFER_SIZE = 8 * 1024 * 1024


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(BUFFER_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def is_complete(path: Path) -> bool:
    required = [
        path / "config.json",
        path / "model.safetensors.index.json",
        path / "model-00001-of-00002.safetensors",
        path / "model-00002-of-00002.safetensors",
        path / "tokenizer.json",
        path / "LICENSE",
        path / "NOTICE",
    ]
    return all(item.is_file() and item.stat().st_size > 0 for item in required) and not any(
        path.rglob("*.incomplete")
    )


def download_resumable(url: str, target: Path, size: int, expected_sha256: str) -> None:
    """下载一个资产；保留未完成文件并在再次启动时使用 HTTP Range 续传。"""
    if target.is_file() and target.stat().st_size == size:
        if sha256_file(target) == expected_sha256:
            print(f"[复用] {target.name}")
            return
        target.unlink()
    if target.exists() and target.stat().st_size > size:
        target.unlink()

    downloaded = target.stat().st_size if target.exists() else 0
    headers = {"User-Agent": "ArtGenome-Qwen-Downloader/1.0"}
    if downloaded:
        headers["Range"] = f"bytes={downloaded}-"
        print(f"[续传] {target.name}: {downloaded / (1024 ** 2):.1f} MiB", flush=True)
    else:
        print(f"[下载] {target.name}: {size / (1024 ** 2):.1f} MiB", flush=True)

    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=180) as response:
        status = getattr(response, "status", response.getcode())
        if downloaded and status != 206:
            downloaded = 0
        mode = "ab" if downloaded and status == 206 else "wb"
        with target.open(mode) as stream:
            while chunk := response.read(BUFFER_SIZE):
                stream.write(chunk)

    actual_size = target.stat().st_size
    if actual_size != size:
        raise RuntimeError(f"{target.name} 大小错误：期望 {size}，实际 {actual_size}")
    actual_sha256 = sha256_file(target)
    if actual_sha256 != expected_sha256:
        target.unlink(missing_ok=True)
        raise RuntimeError(
            f"{target.name} SHA256 错误：期望 {expected_sha256}，实际 {actual_sha256}"
        )


def safe_extract(archive_path: Path, target: Path) -> None:
    target_root = target.resolve()
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            destination = (target / member.filename).resolve()
            if target_root not in destination.parents and destination != target_root:
                raise RuntimeError(f"压缩包包含不安全路径：{member.filename}")
        archive.extractall(target)


def assemble_shard(download_dir: Path, target: Path, shard: dict) -> None:
    output = target / shard["filename"]
    if output.is_file() and output.stat().st_size == shard["size"]:
        if sha256_file(output) == shard["sha256"]:
            print(f"[复用] {output.name}")
            return

    assembling = output.with_suffix(output.suffix + ".assembling")
    with assembling.open("wb") as destination:
        for part in shard["parts"]:
            part_path = download_dir / part["asset"]
            with part_path.open("rb") as source:
                shutil.copyfileobj(source, destination, BUFFER_SIZE)
    if assembling.stat().st_size != shard["size"]:
        raise RuntimeError(f"{output.name} 合并后的大小不正确")
    if sha256_file(assembling) != shard["sha256"]:
        assembling.unlink(missing_ok=True)
        raise RuntimeError(f"{output.name} 合并后的 SHA256 不正确")
    assembling.replace(output)


def download_from_github(target: Path) -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    base_url = os.getenv("ZHIHUA_GITHUB_MODEL_BASE_URL", manifest["base_url"]).rstrip("/")
    download_dir = target / ".github_release_parts"
    download_dir.mkdir(parents=True, exist_ok=True)
    # ModelScope 失败后可能留下临时标记；GitHub 分卷会重新校验并覆盖权重。
    for incomplete in target.rglob("*.incomplete"):
        incomplete.unlink(missing_ok=True)

    metadata = manifest["metadata"]
    metadata_path = download_dir / metadata["asset"]
    download_resumable(
        f"{base_url}/{metadata['asset']}", metadata_path, metadata["size"], metadata["sha256"]
    )
    safe_extract(metadata_path, target)

    for shard in manifest["shards"]:
        for part in shard["parts"]:
            download_resumable(
                f"{base_url}/{part['asset']}",
                download_dir / part["asset"],
                part["size"],
                part["sha256"],
            )
        assemble_shard(download_dir, target, shard)

    if not is_complete(target):
        raise RuntimeError(f"GitHub Release 模型下载后校验未通过：{target}")
    shutil.rmtree(download_dir)


def download_from_modelscope(target: Path) -> None:
    snapshot_download(model_id=MODEL_ID, local_dir=str(target), max_workers=4)
    notice = target / "NOTICE"
    if not notice.exists():
        notice.write_text(
            "Qwen is licensed under the Qwen RESEARCH LICENSE AGREEMENT, "
            "Copyright (c) Alibaba Cloud. All Rights Reserved.\n",
            encoding="utf-8",
        )
    if not is_complete(target):
        raise RuntimeError("ModelScope 返回的模型文件不完整")


def main() -> None:
    parser = argparse.ArgumentParser(description="下载知画使用的 Qwen2.5-VL 模型")
    parser.add_argument("--target", type=Path, required=True)
    args = parser.parse_args()
    target = args.target.expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    source = os.getenv("ZHIHUA_MODEL_SOURCE", "auto").strip().lower()
    if source not in {"auto", "modelscope", "github"}:
        raise RuntimeError("ZHIHUA_MODEL_SOURCE 只能是 auto、modelscope 或 github")

    if source in {"auto", "modelscope"}:
        try:
            print("[Qwen] 正在从 ModelScope 下载（支持并行与断点续传）……", flush=True)
            download_from_modelscope(target)
            print(f"Qwen 模型下载并校验完成：{target}")
            return
        except Exception as exc:
            if source == "modelscope":
                raise
            print(f"[Qwen] ModelScope 下载失败：{exc}", flush=True)
            print("[Qwen] 自动切换到 GitHub Release 分卷……", flush=True)

    download_from_github(target)
    print(f"Qwen 模型下载并校验完成：{target}")


if __name__ == "__main__":
    main()
