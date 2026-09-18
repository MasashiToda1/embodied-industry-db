#!/usr/bin/env python3
"""具身产业库门禁。

用法：
    python3 scripts/lint.py [--root .] [--strict]

--strict 把「主体事件数不足 3 条」也算失败；默认只警告，因为 stub 是合法状态。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

DATE_PATTERNS = {
    "day": re.compile(r"^\d{4}-\d{2}-\d{2}$"),
    "month": re.compile(r"^\d{4}-\d{2}$"),
    "quarter": re.compile(r"^\d{4}-Q[1-4]$"),
    "year": re.compile(r"^\d{4}$"),
}

EVENT_REQUIRED = ["id", "date", "date_precision", "type", "orgs", "title", "evidence"]
EVIDENCE_REQUIRED = ["url", "tier", "retrieved", "snapshot"]
PUBLISH_MIN_EVENTS = 3


class Vocab:
    def __init__(self, root: Path):
        self.enums = yaml.safe_load((root / "vocab/enums.yaml").read_text())
        self.layers = {v["id"] for v in yaml.safe_load((root / "vocab/layers.yaml").read_text())["values"]}
        self.axes: dict[str, dict] = {}
        for name in ("tech", "data", "business"):
            doc = yaml.safe_load((root / f"vocab/axes-{name}.yaml").read_text())
            for axis in doc["axes"]:
                self.axes[axis["field"]] = {
                    "multi": axis.get("multi", False),
                    "values": {v["id"] for v in axis["values"]},
                }


class Linter:
    def __init__(self, root: Path, strict: bool, vocab_root: Path):
        self.root = root
        self.strict = strict
        self.vocab = Vocab(vocab_root)
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.org_ids: set[str] = set()
        self.dataset_ids: set[str] = set()
        self.event_count: dict[str, int] = {}

    def err(self, where: str, msg: str) -> None:
        self.errors.append(f"{where}: {msg}")

    def warn(self, where: str, msg: str) -> None:
        self.warnings.append(f"{where}: {msg}")

    # -- registry ---------------------------------------------------------

    def load_registry(self) -> None:
        for path in sorted((self.root / "registry/orgs").glob("*.yaml")):
            doc = yaml.safe_load(path.read_text()) or {}
            rel = path.relative_to(self.root)
            oid = doc.get("id")
            if oid != path.stem:
                self.err(str(rel), f"id「{oid}」与文件名「{path.stem}」不一致")
                continue
            self.org_ids.add(oid)
            self.event_count[oid] = 0

            if not (doc.get("names") or {}).get("zh"):
                self.err(str(rel), "缺 names.zh")
            status = doc.get("status")
            if status not in self.vocab.enums["org_status"]:
                self.err(str(rel), f"status「{status}」不在枚举内")
            for layer in doc.get("layers") or []:
                if layer not in self.vocab.layers:
                    self.err(str(rel), f"layers 取值「{layer}」不在词表内")
            if not doc.get("layers"):
                self.err(str(rel), "layers 不能为空")

        for path in sorted((self.root / "registry/datasets").glob("*.yaml")):
            doc = yaml.safe_load(path.read_text()) or {}
            rel = path.relative_to(self.root)
            did = doc.get("id")
            if did != path.stem:
                self.err(str(rel), f"id「{did}」与文件名「{path.stem}」不一致")
                continue
            self.dataset_ids.add(did)
            publisher = doc.get("publisher")
            if publisher and publisher not in self.org_ids:
                self.err(str(rel), f"publisher「{publisher}」不在 registry/orgs 内")

    # -- events -----------------------------------------------------------

    def load_events(self) -> None:
        paths = sorted((self.root / "events").rglob("*.yaml"))
        if not paths:
            self.warn("events/", "没有任何事件")
        seen: dict[str, Path] = {}
        for path in paths:
            doc = yaml.safe_load(path.read_text()) or {}
            rel = str(path.relative_to(self.root))
            eid = doc.get("id")
            if eid in seen:
                self.err(rel, f"事件 id「{eid}」与 {seen[eid]} 重复")
            elif eid:
                seen[eid] = path
            self.check_event(rel, doc)

    def check_event(self, where: str, doc: dict) -> None:
        for field in EVENT_REQUIRED:
            if not doc.get(field):
                self.err(where, f"缺必填字段 {field}")
        if self.errors and not doc.get("date"):
            return

        # 门禁 2：date 与 date_precision 自洽
        precision = doc.get("date_precision")
        date = str(doc.get("date", ""))
        pattern = DATE_PATTERNS.get(precision)
        if pattern is None:
            self.err(where, f"date_precision「{precision}」不在枚举内")
        elif not pattern.match(date):
            self.err(where, f"date「{date}」不符合 precision「{precision}」的格式")

        # 允许把模糊区间钉成具体日期，但必须留痕，保证可逆
        basis = doc.get("date_basis", "stated")
        if basis not in self.vocab.enums["date_basis"]:
            self.err(where, f"date_basis「{basis}」不在枚举内")
        elif basis != "stated" and not doc.get("date_as_stated"):
            self.err(where, f"date_basis 为「{basis}」时必须填 date_as_stated，写清原文怎么说的")

        if doc.get("type") not in self.vocab.enums["event_types"]:
            self.err(where, f"type「{doc.get('type')}」不在枚举内")

        # 门禁 3：orgs 引用必须存在
        for entry in doc.get("orgs") or []:
            oid = entry.get("id")
            if oid not in self.org_ids:
                self.err(where, f"orgs 引用的「{oid}」不在 registry/orgs 内")
            else:
                self.event_count[oid] += 1
            if entry.get("role") not in self.vocab.enums["org_roles"]:
                self.err(where, f"role「{entry.get('role')}」不在枚举内")

        for did in doc.get("datasets") or []:
            if did not in self.dataset_ids:
                self.err(where, f"datasets 引用的「{did}」不在 registry/datasets 内")

        # 门禁 1：evidence 完整性
        for i, ev in enumerate(doc.get("evidence") or []):
            tag = f"evidence[{i}]"
            for field in EVIDENCE_REQUIRED:
                if not ev.get(field):
                    self.err(where, f"{tag} 缺 {field}")
            if ev.get("tier") and ev["tier"] not in self.vocab.enums["source_tiers"]:
                self.err(where, f"{tag} tier「{ev['tier']}」不在枚举内")
            snapshot = ev.get("snapshot")
            if snapshot and not snapshot.startswith("http"):
                if not (self.root / snapshot).exists():
                    self.err(where, f"{tag} 快照文件不存在：{snapshot}")

        corr = doc.get("corroboration")
        if corr and corr not in self.vocab.enums["corroboration"]:
            self.err(where, f"corroboration「{corr}」不在枚举内")

        # 门禁 4：axes 取值必须命中词表
        for field, value in (doc.get("axes") or {}).items():
            axis = self.vocab.axes.get(field)
            if axis is None:
                self.err(where, f"axes 里的「{field}」不是已定义的轴")
                continue
            values = value if isinstance(value, list) else [value]
            if len(values) > 1 and not axis["multi"]:
                self.err(where, f"轴「{field}」不允许多值")
            for v in values:
                if v not in axis["values"]:
                    self.err(where, f"轴「{field}」取值「{v}」不在词表内")

        # 门禁 6：推断性措辞
        self.check_neutrality(where, doc)

    def check_neutrality(self, where: str, doc: dict) -> None:
        texts: list[str] = []
        for key in ("title", "summary"):
            block = doc.get(key)
            if isinstance(block, dict):
                texts.extend(str(v) for v in block.values() if v)
            elif block:
                texts.append(str(block))
        joined = "\n".join(texts)
        for phrase in self.vocab.enums["inference_phrases"]:
            if phrase in joined:
                self.err(where, f"正文含推断性措辞「{phrase}」，本库只记事实")

    # -- 门禁 5 -----------------------------------------------------------

    def check_publish_gate(self) -> None:
        for oid, count in sorted(self.event_count.items()):
            if count >= PUBLISH_MIN_EVENTS:
                continue
            msg = f"主体「{oid}」只有 {count} 条事件，不足 {PUBLISH_MIN_EVENTS} 条，不进公开索引"
            if self.strict:
                self.err("registry/orgs", msg)
            else:
                self.warn("registry/orgs", msg)

    def run(self) -> int:
        self.load_registry()
        self.load_events()
        self.check_publish_gate()

        for line in self.warnings:
            print(f"  warn  {line}")
        for line in self.errors:
            print(f"  ERROR {line}")

        total = len(self.org_ids), len(self.dataset_ids), sum(self.event_count.values())
        print(f"\n主体 {total[0]} / 数据集 {total[1]} / 事件引用 {total[2]}")
        print(f"错误 {len(self.errors)}，警告 {len(self.warnings)}")
        return 1 if self.errors else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="数据根目录，可指向 tests/fixtures")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    repo = Path(__file__).resolve().parent.parent
    vocab_root = root if (root / "vocab").exists() else repo
    return Linter(root, args.strict, vocab_root).run()


if __name__ == "__main__":
    sys.exit(main())
