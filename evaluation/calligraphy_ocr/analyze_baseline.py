"""Add simplified/traditional-equivalent metrics to a strict OCR baseline."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from opencc import OpenCC


HAN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    converter = OpenCC("t2s")
    with args.results.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))

    counters: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        expected = row["label"].strip()
        predicted = row["prediction"].strip()
        if predicted == expected:
            category = "exact"
        elif predicted and converter.convert(predicted) == converter.convert(expected):
            category = "variant_equivalent"
        elif not predicted:
            category = "empty"
        elif not HAN.search(predicted):
            category = "non_han_output"
        else:
            category = "wrong_character"
        row["error_category"] = category
        counters[row["style"]]["total"] += 1
        counters[row["style"]][category] += 1

    fields = list(rows[0])
    detailed = args.output_dir / "results_recognition_detailed.csv"
    with detailed.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    summary: dict[str, object] = {"total": len(rows), "by_style": {}}
    report = [
        "# PP-OCRv5_server_rec 书法单字基线",
        "",
        "严格正确率要求预测与 HCSU 原始标签完全一致；简繁等价率会先统一为简体再比较，"
        "但不把真正的异体字、通假字或错字自动视为正确。",
        "",
        "| 书体 | 样本 | 严格正确 | 简繁等价后正确 | 真正错字 | 空结果 | 非汉字输出 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for style in ("楷", "隶", "行", "草"):
        count = counters[style]
        total = count["total"]
        exact = count["exact"]
        tolerant = exact + count["variant_equivalent"]
        item = dict(count)
        item["strict_accuracy"] = round(exact / total, 4)
        item["variant_tolerant_accuracy"] = round(tolerant / total, 4)
        summary["by_style"][style] = item
        report.append(
            f"| {style} | {total} | {exact} ({exact / total:.0%}) | "
            f"{tolerant} ({tolerant / total:.0%}) | {count['wrong_character']} | "
            f"{count['empty']} | {count['non_han_output']} |"
        )
    report.extend([
        "",
        "## 判定",
        "",
        "这些输入已经是人工标注并裁切好的单字，因此本表中的错误属于识别模型问题，"
        "不能归因于文字检测框。隶、行、草均达到需要微调的条件。",
    ])
    (args.output_dir / "summary_detailed.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (args.output_dir / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
