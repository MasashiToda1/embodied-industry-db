#!/usr/bin/env python3
"""自动盯梢：发现新线索，不写库。

**只开 issue，绝不写 events/。** 抓到的东西是候选不是事实，
自动写库等于把所有门禁绕过去。

分两档处理：
  命中 registry 主体 → 单开一条 issue，字段按「手工事件」模板预填，可直接 make intake
  只命中关键词      → 汇总成一条 digest，多半是新主体线索，人工判

用法：
    python3 scripts/watch.py                 # 只打印，不开 issue
    python3 scripts/watch.py --emit out/     # 把 issue 正文写到目录，交给 workflow 去开
    python3 scripts/watch.py --no-state      # 忽略去重，调试用
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlencode

import httpx
import yaml

ROOT = Path(__file__).resolve().parent.parent
CONF = ROOT / "scripts/watch-sources.yaml"
STATE = ROOT / ".watch-state.json"
CST = timezone(timedelta(hours=8))
UA = {"User-Agent": "Mozilla/5.0 (compatible; embodied-industry-db watch)"}
ATOM = "{http://www.w3.org/2005/Atom}"


def norm(s: str) -> str:
    return unicodedata.normalize("NFKC", (s or "")).strip()


def key_of(url: str, title: str) -> str:
    """去重键。URL 常带跟踪参数，所以连标题一起算。"""
    base = re.sub(r"[?#].*$", "", url or "") + "|" + norm(title)
    return hashlib.sha256(base.encode("utf-8", "ignore")).hexdigest()[:16]


def ingested_urls() -> set[str]:
    """已入库事件引用过的来源 URL。

    不播种的话，第一次跑会把库里已有的东西又报一遍——
    比如已经记过的 HF 发布，会再开一条重复 issue。
    """
    out: set[str] = set()
    for p in (ROOT / "events").rglob("*.yaml"):
        doc = yaml.safe_load(p.read_text()) or {}
        for ev in doc.get("evidence") or []:
            url = ev.get("url")
            if url:
                out.add(re.sub(r"[?#].*$", "", url))
    return out


def load_state() -> set[str]:
    seen: set[str] = set()
    if STATE.exists():
        seen = set(json.loads(STATE.read_text()).get("seen", []))
    return seen


def save_state(seen: set[str]) -> None:
    # 只留最近的，否则文件无限长
    STATE.write_text(json.dumps({"seen": sorted(seen)[-4000:]}, indent=0))


def load_orgs() -> list[dict]:
    out = []
    folder = ROOT / "registry/orgs"
    if folder.exists():
        for p in sorted(folder.glob("*.yaml")):
            d = yaml.safe_load(p.read_text()) or {}
            names = d.get("names") or {}
            out.append({
                "id": d.get("id"),
                "zh": names.get("zh") or "",
                "en": names.get("en") or "",
                "aliases": names.get("aliases") or [],
                "accounts": d.get("accounts") or {},
            })
    return out


def match_org(text: str, orgs: list[dict]) -> dict | None:
    """命中 registry 主体。短名不参与，避免 1X 这类误命中。"""
    for org in orgs:
        for cand in [org["zh"], org["en"], *org["aliases"]]:
            if len(cand) >= 3 and cand in text:
                return {"id": org["id"], "zh": org["zh"], "matched": cand}
    return None


# ----------------------------------------------------------------- 各源

def fetch_rss(name: str, url: str, tier: str) -> list[dict]:
    try:
        r = httpx.get(url, timeout=20, headers=UA, follow_redirects=True)
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except Exception as exc:  # noqa: BLE001
        print(f"  ! {name} 取不到：{type(exc).__name__}", file=sys.stderr)
        return []

    out = []
    for it in root.findall(".//item"):
        out.append({
            "source": name,
            "tier": tier,
            "title": norm(it.findtext("title")),
            "url": norm(it.findtext("link")),
            "date": norm(it.findtext("pubDate"))[:16],
            "summary": re.sub(r"<[^>]+>", "", norm(it.findtext("description")))[:300],
            "kind": "news",
        })
    return out


def fetch_arxiv(query: str, max_results: int) -> list[dict]:
    try:
        # 三个坑，都踩过：
        #   1. http 会 301，必须 https 且跟随重定向
        #   2. 查询串按官方写法拼，冒号括号引号保持字面量
        #   3. ⚠️ arXiv 限流很紧，官方要求请求间隔 ≥3 秒；短时间内请求密了
        #      会把你整个挡掉，而且返回的是 406 不是 429，很容易误判成参数错。
        #      每天跑一次不会碰到，调试时务必加 sleep。
        time.sleep(3)
        qs = urlencode(
            {"search_query": query, "max_results": max_results,
             "sortBy": "submittedDate", "sortOrder": "descending"},
            quote_via=quote, safe=':()"',
        )
        r = httpx.get(f"https://export.arxiv.org/api/query?{qs}",
                      timeout=25, headers=UA, follow_redirects=True)
        if r.status_code == 406:
            print("  ! arXiv 返回 406＝被限流（不是参数错），本轮跳过", file=sys.stderr)
            return []
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except Exception as exc:  # noqa: BLE001
        print(f"  ! arXiv 取不到：{type(exc).__name__}", file=sys.stderr)
        return []

    out = []
    for e in root.findall(f"{ATOM}entry"):
        link = ""
        for ln in e.findall(f"{ATOM}link"):
            if ln.get("rel") == "alternate":
                link = ln.get("href") or ""
        out.append({
            "source": "arXiv",
            "tier": "primary",
            "title": norm(e.findtext(f"{ATOM}title")),
            "url": link,
            "date": norm(e.findtext(f"{ATOM}published"))[:10],
            "summary": norm(e.findtext(f"{ATOM}summary"))[:300],
            "kind": "paper",
        })
    return out


def fetch_huggingface(orgs: list[dict], days: int = 14) -> list[dict]:
    """盯 registry 里填了 accounts.huggingface 的主体。

    这是精度最高的一条源：许可、模态、规模都是结构化字段，
    而且发布方就是主体本身，不存在归属歧义。
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    out = []
    for org in orgs:
        slug = (org.get("accounts") or {}).get("huggingface")
        if not slug:
            continue
        for kind, label in (("models", "模型"), ("datasets", "数据集")):
            try:
                r = httpx.get(f"https://huggingface.co/api/{kind}",
                              params={"author": slug, "sort": "createdAt", "direction": -1},
                              timeout=20, headers=UA)
                items = r.json()
            except Exception as exc:  # noqa: BLE001
                print(f"  ! HF {slug}/{kind} 取不到：{type(exc).__name__}", file=sys.stderr)
                continue
            for it in items if isinstance(items, list) else []:
                created = (it.get("createdAt") or "")[:19]
                if created and created < cutoff[:19]:
                    continue
                rid = it.get("id", "")
                path = "datasets/" if kind == "datasets" else ""
                out.append({
                    "source": f"Hugging Face · {slug}",
                    "tier": "official",
                    "title": f"{org['zh']}发布{label} {rid.split('/')[-1]}",
                    "url": f"https://huggingface.co/{path}{rid}",
                    "date": created[:10],
                    "summary": f"许可 {(it.get('cardData') or {}).get('license', '未标')}；"
                               f"标签 {'、'.join((it.get('tags') or [])[:6])}",
                    "kind": "dataset_release" if kind == "datasets" else "publication",
                    "org": {"id": org["id"], "zh": org["zh"], "matched": slug},
                })
    return out


# ----------------------------------------------------------------- 产出

def issue_body(item: dict) -> str:
    """按「手工事件」表单格式产出，这样 make intake 能直接解析。"""
    org = (item.get("org") or {}).get("zh", "")
    etype = {
        "publication": "publication — 论文、开源发布",
        "dataset_release": "dataset_release — 数据集发布",
    }.get(item.get("kind", ""), "")
    return "\n\n".join([
        "### 主体", org or "_No response_",
        "### 什么时候发生", item.get("date") or "_No response_",
        "### 什么事", f"{item['title']}。{item.get('summary','')}".strip(),
        "### 怎么知道的", "有公开链接（不是一手信息）",
        "### 公开链接", item.get("url") or "_No response_",
        "### 事件类型", etype or "_No response_",
        "### 金额", "_No response_",
        "### 买方或对方", "_No response_",
        "### 补充", f"由 watch.py 自动发现，来源：{item['source']}。**入库前须核实原页面。**",
    ])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--emit", help="把 issue 正文写到这个目录")
    ap.add_argument("--no-state", action="store_true")
    args = ap.parse_args()

    conf = yaml.safe_load(CONF.read_text())
    orgs = load_orgs()
    seen = set() if args.no_state else load_state()
    kw = re.compile("|".join(map(re.escape, conf["keywords"])))

    items: list[dict] = []
    for f in conf.get("rss") or []:
        items += fetch_rss(f["name"], f["url"], f.get("tier", "media"))
    if (conf.get("arxiv") or {}).get("enabled"):
        items += fetch_arxiv(conf["arxiv"]["query"], conf["arxiv"].get("max_results", 40))
    if (conf.get("huggingface") or {}).get("enabled"):
        items += fetch_huggingface(orgs)

    already = ingested_urls()
    hits, digest, skipped = [], [], 0
    for it in items:
        k = key_of(it["url"], it["title"])
        # 两道去重：报过的不再报，已入库的更不该报
        if k in seen or re.sub(r"[?#].*$", "", it.get("url", "")) in already:
            skipped += 1
            continue
        blob = f"{it['title']} {it.get('summary','')}"
        org = it.get("org") or match_org(blob, orgs)
        if org:
            it["org"] = org
            hits.append((k, it))
        elif it["kind"] == "paper":
            # 论文没匹配到产业主体就丢弃，不进 digest。
            # 本库只收产业主体，而 cs.RO 每天几十篇绝大多数是纯高校成果；
            # 全放进来候选表立刻变噪音，人就不看了。
            # 关键词也不用在这儿过一遍——arXiv 查询本身已经过滤过。
            continue
        elif kw.search(blob):
            digest.append((k, it))

    papers = sum(1 for it in items if it["kind"] == "paper")
    print(f"抓到 {len(items)} 条（其中论文 {papers}），去重跳过 {skipped}，"
          f"命中主体 {len(hits)}，仅命中关键词 {len(digest)}")

    for _, it in hits:
        print(f"  ◆ [{it['org']['zh']}] {it['date']}  {it['title'][:52]}  ({it['source']})")
    for _, it in digest:
        print(f"  · {it['date']}  {it['title'][:52]}  ({it['source']})")

    if args.emit:
        out = Path(args.emit)
        out.mkdir(parents=True, exist_ok=True)
        for i, (_, it) in enumerate(hits):
            (out / f"hit-{i:02d}.md").write_text(issue_body(it), encoding="utf-8")
            (out / f"hit-{i:02d}.title").write_text(
                f"[事件] {it['org']['zh']}：{it['title'][:40]}", encoding="utf-8")
        if digest:
            lines = ["以下线索命中了关键词但**没匹配到 registry 主体**，多半是还没收录的公司。",
                     "逐条判断：该收的用「新主体」模板建条目，不该收的直接忽略。", ""]
            for _, it in digest:
                lines.append(f"- [{it['date']}] [{it['title']}]({it['url']}) — {it['source']}")
            (out / "digest.md").write_text("\n".join(lines), encoding="utf-8")
            (out / "digest.title").write_text(
                f"[线索] 未匹配主体的候选 {len(digest)} 条 · {datetime.now(CST):%Y-%m-%d}",
                encoding="utf-8")

    if not args.no_state:
        save_state(seen | {k for k, _ in hits} | {k for k, _ in digest})
    return 0


if __name__ == "__main__":
    sys.exit(main())
