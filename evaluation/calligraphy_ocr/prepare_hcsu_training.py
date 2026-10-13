"""Prepare a leakage-free HCSU stage-1 fine-tuning manifest for PP-OCRv5."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path

import yaml


STYLES = ("楷", "隶", "行", "草")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--test-manifest", type=Path, required=True)
    parser.add_argument("--inference-yml", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--val-per-style", type=int, default=50)
    parser.add_argument("--seed", type=int, default=20261012)
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)

    with args.test_manifest.open("r", encoding="utf-8-sig", newline="") as stream:
        test_hashes = {row["sha256"] for row in csv.DictReader(stream)}
    config = yaml.safe_load(args.inference_yml.read_text(encoding="utf-8"))
    characters = config["PostProcess"]["character_dict"]
    character_set = set(characters)
    (args.output_root / "ppocrv5_dict.txt").write_text(
        "\n".join(characters) + "\n", encoding="utf-8"
    )

    rows: dict[str, list[dict[str, str]]] = defaultdict(list)
    excluded = CounterLike()
    seen: set[str] = set()
    for image in sorted(args.source_root.rglob("*.png")):
        if "-" not in image.parent.name:
            continue
        author, style = image.parent.name.rsplit("-", 1)
        if style not in STYLES:
            continue
        label = image.stem.strip()
        if not label or label == "□":
            excluded.add("invalid_label")
            continue
        image_hash = digest(image)
        if image_hash in test_hashes:
            excluded.add("fixed_test")
            continue
        if image_hash in seen:
            excluded.add("duplicate")
            continue
        if any(char not in character_set for char in label):
            excluded.add("outside_ppocrv5_dictionary")
            continue
        seen.add(image_hash)
        rows[style].append({
            "path": image.relative_to(args.source_root).as_posix(),
            "label": label,
            "style": style,
            "author": author,
            "sha256": image_hash,
        })

    rng = random.Random(args.seed)
    train: list[dict[str, str]] = []
    val: list[dict[str, str]] = []
    for style in STYLES:
        rng.shuffle(rows[style])
        val.extend(rows[style][: args.val_per_style])
        train.extend(rows[style][args.val_per_style :])
    rng.shuffle(train)
    rng.shuffle(val)

    for name, values in (("train", train), ("val", val)):
        (args.output_root / f"{name}_list.txt").write_text(
            "".join(f"{row['path']}\t{row['label']}\n" for row in values), encoding="utf-8"
        )
        with (args.output_root / f"{name}_manifest.csv").open(
            "w", encoding="utf-8-sig", newline=""
        ) as stream:
            writer = csv.DictWriter(stream, fieldnames=list(values[0]))
            writer.writeheader()
            writer.writerows(values)

    stats = {
        "dataset": "Tongji209/HCSU",
        "license": "CC BY-NC 4.0",
        "source_root": str(args.source_root.resolve()),
        "train": len(train),
        "validation": len(val),
        "fixed_test_excluded": len(test_hashes),
        "train_by_style": dict(CounterLike.from_rows(train)),
        "validation_by_style": dict(CounterLike.from_rows(val)),
        "excluded": dict(excluded.values),
        "seed": args.seed,
    }
    (args.output_root / "dataset_stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(stats, ensure_ascii=False, indent=2))


class CounterLike:
    def __init__(self) -> None:
        self.values: dict[str, int] = defaultdict(int)

    def add(self, key: str) -> None:
        self.values[key] += 1

    @classmethod
    def from_rows(cls, rows: list[dict[str, str]]) -> dict[str, int]:
        result: dict[str, int] = defaultdict(int)
        for row in rows:
            result[row["style"]] += 1
        return result


if __name__ == "__main__":
    main()
