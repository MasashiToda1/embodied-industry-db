#!/usr/bin/env python3
"""从种子清单批量生成主体身份文件。

全球全覆盖最容易死在「一家家手写、铺不完」。所以身份用一行种子描述，
由脚本展开成 registry/orgs/*.yaml。

**不覆盖已存在的文件**——手工补过来源或字段的条目不会被冲掉。

用法：
    python3 scripts/bootstrap_orgs.py                # 写入
    python3 scripts/bootstrap_orgs.py --dry-run      # 只看会生成什么
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SEED = ROOT / "registry/_seed-orgs.yaml"
OUT = ROOT / "registry/orgs"


def build(entry: dict) -> dict:
    """种子行展开成完整身份结构。字段顺序固定，方便 diff。"""
    doc: dict = {"id": entry["id"], "names": {"zh": entry["zh"]}}
    if entry.get("en"):
        doc["names"]["en"] = entry["en"]
    if entry.get("aliases"):
        doc["names"]["aliases"] = entry["aliases"]

    for key in ("founded", "status"):
        if entry.get(key):
            doc[key] = entry[key]
    doc.setdefault("status", "active")

    if entry.get("country") or entry.get("city"):
        hq = {}
        if entry.get("country"):
            hq["country"] = entry["country"]
        if entry.get("city"):
            hq["city"] = entry["city"]
        doc["hq"] = hq

    doc["layers"] = entry["layers"]

    # 记下种子来自上游哪个机构条目，后面接论文管道时要靠它做主体映射
    if entry.get("upstream"):
        doc["upstream"] = {"robotics_notebooks_institution": entry["upstream"]}
    return doc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not SEED.exists():
        print(f"种子文件不存在：{SEED.relative_to(ROOT)}")
        return 1

    seed = yaml.safe_load(SEED.read_text()) or {}
    entries = seed.get("orgs") or []
    OUT.mkdir(parents=True, exist_ok=True)

    written, skipped, bad = 0, 0, 0
    seen: set[str] = set()

    for entry in entries:
        oid = entry.get("id")
        if not oid or not entry.get("zh") or not entry.get("layers"):
            print(f"  跳过（缺 id / zh / layers）：{entry}")
            bad += 1
            continue
        if oid in seen:
            print(f"  跳过（种子内重复）：{oid}")
            bad += 1
            continue
        seen.add(oid)

        path = OUT / f"{oid}.yaml"
        if path.exists():
            skipped += 1
            continue

        text = yaml.safe_dump(
            build(entry), allow_unicode=True, sort_keys=False, default_flow_style=False
        )
        if args.dry_run:
            print(f"--- {path.relative_to(ROOT)}\n{text}")
        else:
            path.write_text(text, encoding="utf-8")
        written += 1

    verb = "将生成" if args.dry_run else "已生成"
    print(f"\n种子 {len(entries)} 条：{verb} {written}，已存在跳过 {skipped}，无效 {bad}")
    print("身份只是起点，coverage 仍是 stub —— 要靠事件把它填起来。")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
