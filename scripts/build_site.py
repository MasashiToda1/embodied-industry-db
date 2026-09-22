#!/usr/bin/env python3
"""生成静态站要吃的 JSON。

三份文件，都是编译产物，不进 git，Pages workflow 部署时现场生成：
  docs/data/all.json    主体 + 事件 + 数据集 + 词表标签 + 编译出的 stack
  docs/data/graph.json  节点＝主体；边＝事件里的主体间关系（investor / customer / supplier / counterparty）
  docs/data/axes.json   每条轴每个取值的「首次可见」序列，收敛视图用

用法：
    python3 scripts/build_site.py [--root .] [--out docs/data]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compile import Compiler  # noqa: E402

ROLE_ZH = {"subject": "主体", "counterparty": "对手方", "investor": "投资方",
           "customer": "客户", "supplier": "供应方"}


def build_graph(c: Compiler) -> dict:
    """边全部来自事件。同一条事件里两个产业主体之间连一条，边上带角色和事件 id。

    共享技术栈的虚线边也算出来（shared），前端默认关——
    技术选择相同不代表有关系，180 个节点会连成一团毛线。
    """
    nodes: dict[str, dict] = {}
    edges: dict[tuple, dict] = {}
    text_nodes: dict[str, dict] = {}

    for oid, seed in c.orgs.items():
        evs = c.by_org.get(oid, [])
        nodes[oid] = {
            "id": oid,
            "zh": (seed.get("names") or {}).get("zh") or oid,
            "layers": seed.get("layers") or [],
            "events": len(evs),
        }

    for ev in c.events:
        parts = [(o["id"], o.get("role", "subject")) for o in ev.get("orgs") or [] if o.get("id") in nodes]
        subjects = [p for p in parts if p[1] == "subject"] or parts[:1]
        others = [p for p in parts if p not in subjects]
        # 主体 ↔ 其他产业主体
        for s, _ in subjects:
            for o, role in others:
                key = tuple(sorted((s, o)))
                e = edges.setdefault(key, {"source": key[0], "target": key[1], "kind": "event",
                                           "roles": set(), "events": []})
                e["roles"].add(role)
                e["events"].append(ev["id"])
            # 主体 ↔ 文本对手方（不在 registry 的买方），画成灰节点
            for cp in ev.get("counterparties") or []:
                tid = "txt:" + cp
                text_nodes.setdefault(tid, {"id": tid, "zh": cp, "text": True, "events": 0})
                text_nodes[tid]["events"] += 1
                key = (s, tid)
                e = edges.setdefault(key, {"source": s, "target": tid, "kind": "event",
                                           "roles": set(), "events": []})
                e["roles"].add("counterparty")
                e["events"].append(ev["id"])

    # 共享技术栈（可开关的叠加层）：同一轴同一取值的主体两两相连
    by_value: dict[tuple, list[str]] = defaultdict(list)
    for oid in nodes:
        stack = c.derive_stack(c.by_org.get(oid, []), oid)
        for field, items in stack.items():
            for it in items:
                by_value[(field, it["value"])].append(oid)
    shared: dict[tuple, dict] = {}
    for (field, value), ids in by_value.items():
        ids = sorted(set(ids))
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                key = (ids[i], ids[j])
                e = shared.setdefault(key, {"source": ids[i], "target": ids[j], "kind": "shared", "values": []})
                e["values"].append(f"{field}:{value}")

    out_edges = []
    for e in edges.values():
        e["roles"] = sorted(e["roles"])
        out_edges.append(e)
    out_edges += list(shared.values())

    # 只放有事件的主体进图，否则 180 个孤点。前端可选「显示全部」
    active = {n["id"]: n for n in nodes.values() if n["events"] > 0}
    linked = {e["source"] for e in out_edges} | {e["target"] for e in out_edges}
    for oid in linked:
        if oid in nodes and oid not in active:
            active[oid] = nodes[oid]
    return {
        "nodes": list(active.values()) + list(text_nodes.values()),
        "all_nodes": list(nodes.values()),
        "edges": out_edges,
    }


def build_axes(c: Compiler) -> dict:
    """每条轴：{value: [{org, first_seen}, ...]}。前端据此算「各取值主体数随时间」。"""
    out: dict[str, dict] = {}
    for oid in c.orgs:
        stack = c.derive_stack(c.by_org.get(oid, []), oid)
        for field, items in stack.items():
            ax = out.setdefault(field, {"zh": c.vocab["labels"].get(field, field), "values": {}})
            for it in items:
                ax["values"].setdefault(it["value"], {
                    "zh": c.vocab["labels"].get(f"{field}:{it['value']}", it["value"]),
                    "orgs": [],
                })["orgs"].append({"org": oid, "first_seen": it["as_of"], "event": it["evidence"]})
    for ax in out.values():
        for v in ax["values"].values():
            v["orgs"].sort(key=lambda x: x["first_seen"])
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--out", default="docs/data")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    out = Path(args.out)
    if not out.is_absolute():
        out = root / out
    out.mkdir(parents=True, exist_ok=True)

    c = Compiler(root, out / "_unused_build", vocab_root=root)
    c.load_events()

    payload = c.export_json()
    # 词表标签与层，前端显示中文用
    payload["labels"] = c.vocab["labels"]
    payload["layers"] = {v["id"]: v["zh"] for v in yaml.safe_load((root / "vocab/layers.yaml").read_text())["values"]}
    payload["event_types"] = c.vocab["enums"]["event_types"]
    payload["roles"] = ROLE_ZH
    payload["axes_meta"] = {
        f: {"zh": c.vocab["labels"].get(f, f), "group": a.get("group", "")}
        for f, a in c.vocab["axes"].items()
    }
    # 主体带上 layers 中文与事件数，列表页直接用
    for o in payload["orgs"]:
        o["event_count"] = len(c.by_org.get(o["id"], []))

    (out / "all.json").write_text(json.dumps(payload, ensure_ascii=False, default=str), encoding="utf-8")
    (out / "graph.json").write_text(json.dumps(build_graph(c), ensure_ascii=False), encoding="utf-8")
    (out / "axes.json").write_text(json.dumps(build_axes(c), ensure_ascii=False), encoding="utf-8")

    g = json.loads((out / "graph.json").read_text())
    print(f"all.json   主体 {len(payload['orgs'])} / 事件 {len(payload['events'])}")
    print(f"graph.json 节点 {len(g['nodes'])}（含文本对手方）/ 边 {len(g['edges'])}"
          f"（事件边 {sum(1 for e in g['edges'] if e['kind']=='event')}）")
    print(f"axes.json  轴 {len(json.loads((out / 'axes.json').read_text()))} 条")
    print(f"输出 {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
