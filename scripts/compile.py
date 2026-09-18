#!/usr/bin/env python3
"""把事件流编译成主体页与数据集页。

幂等：输出目录每次全量重建，不做增量。
人只维护 registry/ 和 events/，build/ 下的东西一律不要手改。

用法：
    python3 scripts/compile.py [--root .] [--out build]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path

import yaml

PUBLISH_MIN_EVENTS = 3
SORT_KEY = {"year": "-12-31", "quarter": "", "month": "-31", "day": ""}
QUARTER_END = {"Q1": "03-31", "Q2": "06-30", "Q3": "09-30", "Q4": "12-31"}


def sortable(date: str, precision: str) -> str:
    """把混合精度的日期压成可排序字符串，粗精度排在该区间末尾。"""
    if precision == "year":
        return f"{date}-12-31"
    if precision == "quarter":
        year, q = date.split("-")
        return f"{year}-{QUARTER_END[q]}"
    if precision == "month":
        return f"{date}-31"
    return date


class Compiler:
    def __init__(self, root: Path, out: Path, vocab_root: Path | None = None):
        self.root = root
        self.out = out
        self.vocab_root = vocab_root or root
        self.vocab = self.load_vocab()
        self.orgs = self.load_registry("orgs")
        self.datasets = self.load_registry("datasets")
        self.events: list[dict] = []
        self.by_org: dict[str, list[dict]] = defaultdict(list)
        self.by_dataset: dict[str, list[dict]] = defaultdict(list)

    def load_vocab(self) -> dict:
        vocab = {"axes": {}, "labels": {}}
        for name in ("tech", "data", "business"):
            doc = yaml.safe_load((self.vocab_root / f"vocab/axes-{name}.yaml").read_text())
            for axis in doc["axes"]:
                vocab["axes"][axis["field"]] = axis
                vocab["labels"][axis["field"]] = axis["zh"]
                for v in axis["values"]:
                    vocab["labels"][f"{axis['field']}:{v['id']}"] = v["zh"]
        layers = yaml.safe_load((self.vocab_root / "vocab/layers.yaml").read_text())
        for v in layers["values"]:
            vocab["labels"][f"layers:{v['id']}"] = v["zh"]
        vocab["enums"] = yaml.safe_load((self.vocab_root / "vocab/enums.yaml").read_text())
        return vocab

    def load_registry(self, kind: str) -> dict[str, dict]:
        out = {}
        folder = self.root / "registry" / kind
        if folder.exists():
            for path in sorted(folder.glob("*.yaml")):
                doc = yaml.safe_load(path.read_text()) or {}
                out[doc["id"]] = doc
        return out

    def load_events(self) -> None:
        for path in sorted((self.root / "events").rglob("*.yaml")):
            doc = yaml.safe_load(path.read_text()) or {}
            doc["_sort"] = sortable(str(doc["date"]), doc["date_precision"])
            self.events.append(doc)
            for entry in doc.get("orgs") or []:
                self.by_org[entry["id"]].append(doc)
            for did in doc.get("datasets") or []:
                self.by_dataset[did].append(doc)
        self.events.sort(key=lambda e: e["_sort"])
        for bucket in (self.by_org, self.by_dataset):
            for items in bucket.values():
                items.sort(key=lambda e: e["_sort"])

    # -- stack 推导 -------------------------------------------------------

    def derive_stack(self, events: list[dict]) -> dict[str, list[dict]]:
        """从事件的 axes 推导技术栈，历史取值全部保留。"""
        stack: dict[str, dict[str, dict]] = defaultdict(dict)
        for ev in events:
            for field, value in (ev.get("axes") or {}).items():
                values = value if isinstance(value, list) else [value]
                for v in values:
                    prev = stack[field].get(v)
                    # 同一取值只留最早的一条证据，那是「何时首次可见」
                    if prev is None or ev["_sort"] < prev["_sort"]:
                        stack[field][v] = {
                            "value": v,
                            "as_of": str(ev["date"]),
                            "_sort": ev["_sort"],
                            "evidence": ev["id"],
                        }
        result = {}
        for field, values in stack.items():
            items = sorted(values.values(), key=lambda x: x["_sort"], reverse=True)
            for item in items:
                item.pop("_sort")
            result[field] = items
        return result

    def coverage(self, events: list[dict], stack: dict) -> str:
        if len(events) < PUBLISH_MIN_EVENTS:
            return "stub"
        if len(stack) >= 4 and len(events) >= 8:
            return "complete"
        return "draft"

    # -- 渲染 -------------------------------------------------------------

    def label(self, key: str, fallback: str) -> str:
        return self.vocab["labels"].get(key, fallback)

    def render_org(self, oid: str, seed: dict) -> str:
        events = self.by_org.get(oid, [])
        stack = self.derive_stack(events)
        names = seed.get("names") or {}
        lines = [
            "<!-- 本文件由 scripts/compile.py 生成，请勿手改。改事实去 events/，改身份去 registry/ -->",
            "",
            f"# {names.get('zh') or oid}",
            "",
        ]
        if names.get("en"):
            lines += [f"**{names['en']}**", ""]

        layers = "、".join(self.label(f"layers:{x}", x) for x in seed.get("layers") or [])
        meta = [
            ("产业层", layers or "—"),
            ("状态", self.vocab["enums"]["org_status"].get(seed.get("status"), "—")),
            ("成立", str(seed.get("founded") or "—")),
            ("总部", "".join(str(v) for v in (seed.get("hq") or {}).values()) or "—"),
            ("事件数", str(len(events))),
            ("收录深度", self.coverage(events, stack)),
        ]
        lines += ["| 项 | 值 |", "|---|---|"]
        lines += [f"| {k} | {v} |" for k, v in meta]
        lines.append("")

        if stack:
            lines += ["## 技术与商业栈", "", "历史取值不删，`首次可见` 指本库收录到的最早证据日期。", ""]
            lines += ["| 轴 | 取值 | 首次可见 | 来源事件 |", "|---|---|---|---|"]
            for field, items in stack.items():
                axis_zh = self.label(field, field)
                for item in items:
                    val_zh = self.label(f"{field}:{item['value']}", item["value"])
                    lines.append(f"| {axis_zh} | {val_zh} | {item['as_of']} | `{item['evidence']}` |")
            lines.append("")

        if events:
            lines += ["## 时间线", ""]
            lines += ["| 日期 | 精度 | 类型 | 事件 | 佐证 | 来源 |", "|---|---|---|---|---|---|"]
            for ev in reversed(events):
                title = (ev.get("title") or {}).get("zh") or ev["id"]
                etype = self.vocab["enums"]["event_types"].get(ev["type"], ev["type"])
                corr = ev.get("corroboration", "—")
                urls = " ".join(
                    f"[{e.get('tier', '?')}]({e['url']})" for e in (ev.get("evidence") or []) if e.get("url")
                )
                lines.append(
                    f"| {ev['date']} | {ev['date_precision']} | {etype} | {title} | {corr} | {urls} |"
                )
            lines.append("")

        if not events:
            lines += ["## 时间线", "", "暂无收录事件。", ""]

        return "\n".join(lines)

    def render_dataset(self, did: str, seed: dict) -> str:
        events = self.by_dataset.get(did, [])
        names = seed.get("names") or {}
        lines = [
            "<!-- 本文件由 scripts/compile.py 生成，请勿手改 -->",
            "",
            f"# {names.get('zh') or did}",
            "",
        ]
        scale = seed.get("scale") or {}
        scale_txt = "、".join(f"{k} {v}" for k, v in scale.items() if v) or "未公布"
        meta = [
            ("发布主体", seed.get("publisher") or "—"),
            ("发布时间", str(seed.get("released") or "—")),
            ("规模", scale_txt),
            ("模态", "、".join(self.label(f"data_modality:{m}", m) for m in seed.get("modality") or []) or "—"),
            ("采集方式", "、".join(self.label(f"data_acquisition:{a}", a) for a in seed.get("acquisition") or []) or "—"),
            ("开放程度", self.label(f"data_openness:{seed.get('openness')}", seed.get("openness") or "—")),
            ("许可", seed.get("license") or "—"),
        ]
        lines += ["| 项 | 值 |", "|---|---|"]
        lines += [f"| {k} | {v} |" for k, v in meta]
        lines.append("")
        if events:
            lines += ["## 相关事件", ""]
            for ev in reversed(events):
                title = (ev.get("title") or {}).get("zh") or ev["id"]
                lines.append(f"- {ev['date']} — {title}（`{ev['id']}`）")
            lines.append("")
        return "\n".join(lines)

    # -- 导出 -------------------------------------------------------------

    def export_json(self) -> dict:
        def clean(ev: dict) -> dict:
            return {k: v for k, v in ev.items() if not k.startswith("_")}

        return {
            "orgs": [
                {
                    **seed,
                    "event_count": len(self.by_org.get(oid, [])),
                    "stack": self.derive_stack(self.by_org.get(oid, [])),
                }
                for oid, seed in sorted(self.orgs.items())
            ],
            "datasets": [seed for _, seed in sorted(self.datasets.items())],
            "events": [clean(e) for e in self.events],
        }

    def run(self) -> int:
        self.load_events()
        if self.out.exists():
            shutil.rmtree(self.out)
        (self.out / "orgs").mkdir(parents=True)
        (self.out / "datasets").mkdir(parents=True)

        for oid, seed in sorted(self.orgs.items()):
            (self.out / "orgs" / f"{oid}.md").write_text(self.render_org(oid, seed))
        for did, seed in sorted(self.datasets.items()):
            (self.out / "datasets" / f"{did}.md").write_text(self.render_dataset(did, seed))

        payload = self.export_json()
        (self.out / "all.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        )

        published = sum(
            1 for oid in self.orgs if len(self.by_org.get(oid, [])) >= PUBLISH_MIN_EVENTS
        )
        print(f"主体 {len(self.orgs)} 页（{published} 达到公开门槛）")
        print(f"数据集 {len(self.datasets)} 页")
        print(f"事件 {len(self.events)} 条")
        print(f"输出 {self.out}")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--out", default="build")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    repo = Path(__file__).resolve().parent.parent
    vocab_root = root if (root / "vocab").exists() else repo
    # out 相对当前工作目录解析，不跟着 --root 走
    out = Path(args.out).resolve()
    return Compiler(root, out, vocab_root).run()


if __name__ == "__main__":
    sys.exit(main())
