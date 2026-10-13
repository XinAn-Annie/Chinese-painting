"""Build a deterministic four-script single-character OCR benchmark from HCSU.

HCSU stores samples under directories named ``calligrapher-script`` and uses
the image filename as the character label.  This script copies a balanced,
deterministic subset into a standalone benchmark and records full provenance.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import random
import shutil
import subprocess
import sys
import zipfile
from collections import defaultdict
from pathlib import Path


STYLES = ("楷", "隶", "行", "草")
DATASET = "Tongji209/HCSU"
LICENSE = "CC BY-NC 4.0"
ARCHIVE_PASSWORD = b"eWZNA9hzJoyMHtQwVh7QnBtN7"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_extract(archive: Path, destination: Path) -> None:
    """Extract a ZIP only when every member stays inside destination."""
    destination = destination.resolve()
    # Validate traversal using the central directory before invoking 7-Zip.
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            target = (destination / member.filename).resolve()
            if destination != target and destination not in target.parents:
                raise ValueError(f"不安全的压缩包路径: {member.filename}")

    candidates = [
        shutil.which("7z"),
        r"C:\Program Files\7-Zip\7z.exe",
        r"C:\Program Files\i4Tools9\files\patchtools\7z-64\7z.exe",
        r"C:\Program Files\NVIDIA Corporation\NVIDIA GeForce Experience\7z.exe",
    ]
    seven_zip = next((Path(p) for p in candidates if p and Path(p).exists()), None)
    if seven_zip is None:
        raise RuntimeError("HCSU 使用 AES ZIP，需要安装 7-Zip 后再运行")
    destination.mkdir(parents=True, exist_ok=True)
    command = [
        str(seven_zip), "x", str(archive), f"-o{destination}",
        f"-p{ARCHIVE_PASSWORD.decode('ascii')}", "-y", "-sccUTF-8",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if completed.returncode != 0:
        raise RuntimeError(f"7-Zip 解压失败: {completed.stderr or completed.stdout}")


def ensure_extracted(source_root: Path) -> Path:
    extracted = source_root / "extracted_fixed"
    extracted.mkdir(parents=True, exist_ok=True)
    for name in ("bei.zip", "tie.zip"):
        archive = source_root / name
        if not archive.exists():
            raise FileNotFoundError(f"缺少 HCSU 数据包: {archive}")
        marker = extracted / f".{name}.complete"
        if not marker.exists():
            safe_extract(archive, extracted)
            marker.write_text(sha256(archive), encoding="utf-8")
    return extracted


def parse_candidate(path: Path, extracted: Path) -> dict[str, str] | None:
    if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        return None
    parent = path.parent.name
    if "-" not in parent:
        return None
    author, style = parent.rsplit("-", 1)
    if style not in STYLES:
        return None
    label = path.stem.strip()
    if not label or label == "□":
        return None
    relative_parts = path.relative_to(extracted).parts
    partition = "碑" if any("bei" in p.lower() for p in relative_parts) else "帖"
    return {
        "style": style,
        "label": label,
        "author": author,
        "partition": partition,
        "source_path": str(path.resolve()),
    }


def balanced_select(rows: list[dict[str, str]], count: int, seed: int) -> list[dict[str, str]]:
    """Round-robin calligraphers so one prolific source cannot dominate."""
    rng = random.Random(seed)
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[f"{row['partition']}::{row['author']}"] .append(row)
    for values in groups.values():
        rng.shuffle(values)
    keys = sorted(groups)
    rng.shuffle(keys)
    selected: list[dict[str, str]] = []
    cursor = 0
    while len(selected) < count and keys:
        key = keys[cursor % len(keys)]
        if groups[key]:
            selected.append(groups[key].pop())
            cursor += 1
        else:
            keys.remove(key)
            cursor = 0
    return selected


def build(source_root: Path, output_root: Path, per_style: int, seed: int) -> None:
    if output_root.exists() and any(output_root.iterdir()):
        raise FileExistsError(f"输出目录非空，为避免覆盖请换目录: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    extracted = ensure_extracted(source_root)

    candidates: dict[str, list[dict[str, str]]] = defaultdict(list)
    seen_hashes: set[str] = set()
    for image in sorted(extracted.rglob("*")):
        parsed = parse_candidate(image, extracted)
        if parsed is None:
            continue
        digest = sha256(image)
        if digest in seen_hashes:
            continue
        seen_hashes.add(digest)
        parsed["sha256"] = digest
        candidates[parsed["style"]].append(parsed)

    manifest_rows: list[dict[str, str]] = []
    for style_index, style in enumerate(STYLES):
        selected = balanced_select(candidates[style], per_style, seed + style_index)
        if len(selected) < per_style:
            raise RuntimeError(f"{style}仅找到 {len(selected)} 张，少于要求的 {per_style} 张")
        style_dir = output_root / "images" / style
        style_dir.mkdir(parents=True, exist_ok=True)
        for index, row in enumerate(selected, 1):
            source = Path(row["source_path"])
            sample_id = f"{style}_{index:03d}"
            destination = style_dir / f"{sample_id}{source.suffix.lower()}"
            shutil.copy2(source, destination)
            manifest_rows.append({
                "sample_id": sample_id,
                "style": style,
                "label": row["label"],
                "author": row["author"],
                "source_partition": row["partition"],
                "image_path": str(destination.resolve()),
                "source_path": row["source_path"],
                "sha256": row["sha256"],
                "dataset": DATASET,
                "license": LICENSE,
            })

    fields = list(manifest_rows[0])
    with (output_root / "manifest.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(manifest_rows)

    (output_root / "README.md").write_text(
        "# HCSU 四书体固定测试集\n\n"
        f"- 样本数：{len(manifest_rows)}（楷、隶、行、草各 {per_style} 张）\n"
        f"- 随机种子：{seed}\n"
        f"- 来源：{DATASET}\n"
        f"- 许可：{LICENSE}，仅限非商业用途\n"
        "- 标签：HCSU 原始目录给出书体，原始文件名给出单字标签\n"
        "- 用途：固定基线评测；不得混入后续微调训练集\n",
        encoding="utf-8",
    )
    print(f"已生成 {len(manifest_rows)} 张固定测试样本: {output_root}")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser(description="从 HCSU 构造楷隶行草固定单字测试集")
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--per-style", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20261012)
    args = parser.parse_args()
    if not 100 <= args.per_style <= 200:
        parser.error("--per-style 必须在 100 到 200 之间")
    build(args.source_root, args.output_root, args.per_style, args.seed)


if __name__ == "__main__":
    main()
