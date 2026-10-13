"""Create PaddleOCR evaluation lists grouped by calligraphy style."""

from __future__ import annotations

import csv
from pathlib import Path


MANIFEST = Path(r"D:\codex\书法识别资源\benchmarks\hcsu_4styles_100\manifest.csv")
IMAGE_ROOT = MANIFEST.parent / "images"
OUTPUT_DIR = MANIFEST.parent / "finetuned"
STYLE_SLUG = {"楷": "kai", "隶": "li", "行": "xing", "草": "cao"}


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    grouped: dict[str, list[str]] = {}
    with MANIFEST.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            relative = Path(row["image_path"]).resolve().relative_to(IMAGE_ROOT.resolve())
            grouped.setdefault(row["style"], []).append(f"{relative.as_posix()}\t{row['label']}")
    for style, lines in grouped.items():
        path = OUTPUT_DIR / f"eval_{STYLE_SLUG[style]}.txt"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"{style}: {len(lines)} -> {path}")


if __name__ == "__main__":
    main()
