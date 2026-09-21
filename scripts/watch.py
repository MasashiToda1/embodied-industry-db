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


def load_state() -> tuple[set[str], set[str]]:
    """返回（已报过的条目键, 上次见到的上游机构 id）。"""
    if STATE.exists():
        d = json.loads(STATE.read_text())
        return set(d.get("seen", [])), set(d.get("upstream_institutions", []))
    return set(), set()


def save_state(seen: set[str], insts: set[str]) -> None:
    # seen 只留最近的，否则文件无限长；机构表要全存，它是拿来做差集的
    STATE.write_text(json.dumps(
        {"seen": sorted(seen)[-4000:], "upstream_institutions": sorted(insts)},
        ensure_ascii=False, indent=0,
    ))


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


# 这些公司名本身是普通词，出现在任何标题里都不能当归属依据。
# 它们只能靠 accounts（HF / GitHub）这种结构化归属命中。
GENERIC_NAMES = {"humanoid", "figure", "foundation", "genesis", "apollo", "atlas",
                 "optimus", "digit", "phoenix", "carbon", "field ai", "sunday"}

# 早报串烧：一条标题里塞七八家公司，命中任何一家都没意义
RE_ROUNDUP = re.compile(r"[;；]")


def is_roundup(title: str) -> bool:
    return len(RE_ROUNDUP.findall(title)) >= 2


def match_org(text: str, orgs: list[dict]) -> dict | None:
    """命中 registry 主体。

    先按候选名长度降序，长名优先——「UBTECH Walker」里既有 UBTECH 又有普通词，
    要认成优必选而不是别的。普通词公司名不参与文本匹配。
    """
    cands: list[tuple[str, dict]] = []
    for org in orgs:
        for cand in [org["zh"], org["en"], *org["aliases"]]:
            if len(cand) >= 3 and cand.lower() not in GENERIC_NAMES:
                cands.append((cand, org))
    cands.sort(key=lambda x: -len(x[0]))
    for cand, org in cands:
        if cand in text:
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


# 实验日志的命名特征：_test_、纯时间戳、debug/tmp、纯数字 id
RE_HF_JUNK = re.compile(r"(_test_|_test$|\d{8}_\d{6}|debug|tmp|scratch|^\d+$)", re.I)

# 搜索结果只要最近这些天的。Exa 会翻出半年前的旧闻，每日盯梢报旧闻就是噪音。
# 没日期的保留——招投标公告页常不带日期，宁可多看一眼。
SEARCH_MAX_AGE_DAYS = 30
# 同一主体同类超过这个数就聚成一条「批量发布」
HF_BATCH_MIN = 3


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
            fresh = []
            for it in items if isinstance(items, list) else []:
                created = (it.get("createdAt") or "")[:19]
                if created and created < cutoff[:19]:
                    continue
                name = it.get("id", "").split("/")[-1]
                # 实验日志不是发布：带 _test_ 或 20260921_194739 这种时间戳的名字直接丢
                if RE_HF_JUNK.search(name):
                    continue
                fresh.append((created[:10], name, it))

            path = "datasets/" if kind == "datasets" else ""
            # 批量上传聚成一条。宇树一周推 58 个数据集，一条一个 issue 就是垃圾；
            # 而「批量发布 N 个数据集」本身才是那个值得记的事件。
            if len(fresh) > HF_BATCH_MIN:
                dates = sorted(d for d, _, _ in fresh)
                names = [n for _, n, _ in fresh]
                out.append({
                    "source": f"Hugging Face · {slug}",
                    "tier": "official",
                    "title": f"{org['zh']}批量发布 {len(fresh)} 个{label}（{dates[0]}～{dates[-1]}）",
                    "url": f"https://huggingface.co/{slug}",
                    "date": dates[-1],
                    "summary": "含：" + "、".join(names[:8]) + ("…" if len(names) > 8 else ""),
                    "kind": "dataset_release" if kind == "datasets" else "publication",
                    "org": {"id": org["id"], "zh": org["zh"], "matched": slug},
                })
                continue
            for created, name, it in fresh:
                rid = it.get("id", "")
                out.append({
                    "source": f"Hugging Face · {slug}",
                    "tier": "official",
                    "title": f"{org['zh']}发布{label} {name}",
                    "url": f"https://huggingface.co/{path}{rid}",
                    "date": created,
                    "summary": f"许可 {(it.get('cardData') or {}).get('license', '未标')}；"
                               f"标签 {'、'.join((it.get('tags') or [])[:6])}",
                    "kind": "dataset_release" if kind == "datasets" else "publication",
                    "org": {"id": org["id"], "zh": org["zh"], "matched": slug},
                })
    return out


def _gh_headers() -> dict:
    """GitHub 未认证只有 60 次/小时，跑不完；CI 里用 github.token，本地用 gh 的。"""
    import os
    import subprocess

    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not tok:
        try:
            tok = subprocess.run(["gh", "auth", "token"], capture_output=True,
                                 text=True, check=True).stdout.strip()
        except Exception:  # noqa: BLE001
            tok = ""
    h = {"User-Agent": "embodied-industry-db", "Accept": "application/vnd.github+json"}
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


# 这些仓不是发布：组织配置、主页、fork、归档
RE_GH_SKIP = re.compile(r"^(\.github|.*\.github\.io|profile)$", re.I)
GH_BATCH_MIN = 3
GH_RELEASE_REPOS = 8      # 每个主体查最近推送的这么多仓的 release；再多调用量上去意义不大
MAX_ISSUES_PER_RUN = 15   # 每轮最多开的 issue 数，溢出进 digest


def fetch_github(orgs: list[dict], days: int = 14) -> list[dict]:
    """盯 registry 里填了 accounts.github 的主体：新建的仓、新发的 release。

    GitHub 比 HF 宽：除模型外还有 SDK、部署工具、仿真环境、URDF。
    LightwheelAI/usd2mjcf 这种仓直接暴露技术栈（在用 MuJoCo），HF 上看不出来。

    只看新仓和 release，不看 commit——commit 是噪音。
    每个主体两次调用：repos?sort=created 拿新仓，orgs/{o}/events 拿 ReleaseEvent。
    """
    h = _gh_headers()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    out: list[dict] = []

    for org in orgs:
        login = (org.get("accounts") or {}).get("github")
        if not login:
            continue

        # ① 新建的仓
        try:
            r = httpx.get(f"https://api.github.com/orgs/{login}/repos",
                          params={"sort": "created", "direction": "desc", "per_page": 30},
                          timeout=20, headers=h)
            repos = r.json() if r.status_code == 200 else []
        except Exception as exc:  # noqa: BLE001
            print(f"  ! GitHub {login}/repos 取不到：{type(exc).__name__}", file=sys.stderr)
            repos = []
        if not isinstance(repos, list):
            repos = []

        fresh = []
        for rp in repos:
            if rp.get("fork") or rp.get("archived") or RE_GH_SKIP.match(rp.get("name", "")):
                continue
            if (rp.get("created_at") or "") < cutoff:
                continue
            fresh.append(rp)

        if len(fresh) > GH_BATCH_MIN:
            dates = sorted(rp["created_at"][:10] for rp in fresh)
            out.append({
                "source": f"GitHub · {login}",
                "tier": "official",
                "title": f"{org['zh']}新建 {len(fresh)} 个仓库（{dates[0]}～{dates[-1]}）",
                "url": f"https://github.com/{login}",
                "date": dates[-1],
                "summary": "含：" + "、".join(rp["name"] for rp in fresh[:8]),
                "kind": "publication",
                "org": {"id": org["id"], "zh": org["zh"], "matched": login},
            })
        else:
            for rp in fresh:
                desc = (rp.get("description") or "").strip()
                out.append({
                    "source": f"GitHub · {login}",
                    "tier": "official",
                    "title": f"{org['zh']}新建仓库 {rp['name']}",
                    "url": rp.get("html_url", ""),
                    "date": rp["created_at"][:10],
                    "summary": (desc[:200] + ("；" if desc else "")
                                + f"语言 {rp.get('language') or '—'}；★{rp.get('stargazers_count', 0)}"),
                    "kind": "publication",
                    "org": {"id": org["id"], "zh": org["zh"], "matched": login},
                })

        # ② release。不能用 orgs/{o}/events —— 它被 star 和 push 事件淹掉，
        # 宇树 100 条事件只覆盖 3 天，EmbodiChain 9/10 的 release 根本进不来。
        # 改成：取最近推送的仓，逐个查 /releases。多几次调用，但准。
        try:
            r = httpx.get(f"https://api.github.com/orgs/{login}/repos",
                          params={"sort": "pushed", "direction": "desc", "per_page": GH_RELEASE_REPOS},
                          timeout=20, headers=h)
            active = r.json() if r.status_code == 200 else []
        except Exception as exc:  # noqa: BLE001
            print(f"  ! GitHub {login}/repos(pushed) 取不到：{type(exc).__name__}", file=sys.stderr)
            active = []
        for rp in active if isinstance(active, list) else []:
            if rp.get("fork") or rp.get("archived") or RE_GH_SKIP.match(rp.get("name", "")):
                continue
            if (rp.get("pushed_at") or "") < cutoff:
                continue          # 窗口内没推送，不可能有新 release
            full = rp.get("full_name", "")
            try:
                rr = httpx.get(f"https://api.github.com/repos/{full}/releases",
                               params={"per_page": 3}, timeout=20, headers=h)
                rels = rr.json() if rr.status_code == 200 else []
            except Exception:  # noqa: BLE001
                rels = []
            for rel in rels if isinstance(rels, list) else []:
                pub = rel.get("published_at") or ""
                if rel.get("draft") or pub < cutoff:
                    continue
                tag = rel.get("tag_name", "")
                body = re.sub(r"\s+", " ", rel.get("body") or "")[:200]
                out.append({
                    "source": f"GitHub · {login}",
                    "tier": "official",
                    "title": f"{org['zh']}发布 {rp['name']} {tag}",
                    "url": rel.get("html_url") or f"https://github.com/{full}/releases/tag/{tag}",
                    "date": pub[:10],
                    "summary": (rel.get("name") or "") + ("：" + body if body else ""),
                    "kind": "publication",
                    "org": {"id": org["id"], "zh": org["zh"], "matched": login},
                })
            time.sleep(0.1)
        time.sleep(0.2)
    return out


def fetch_exa(queries: list[str], num_results: int) -> list[dict]:
    """Exa 语义搜索，Agent-Reach 的搜索渠道。

    调用方式就是 Agent-Reach 的 SKILL 教 agent 用的那条命令，不绕过它。
    补的是 RSS 的盲区：媒体 feed 只覆盖两家，搜索能扫到全网。

    没装 mcporter 就静默跳过——它是可选源，缺了不该让整轮盯梢失败。
    """
    import shutil
    import subprocess

    if not shutil.which("mcporter"):
        print("  · mcporter 未安装，跳过 Exa（npm install -g mcporter）", file=sys.stderr)
        return []

    def call(q: str) -> str:
        r = subprocess.run(
            ["mcporter", "call", "exa.web_search_exa",
             f"query={q}", f"numResults={num_results}", "--output", "json"],
            capture_output=True, text=True, timeout=60,
        )
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip()[:80])
        payload = json.loads(r.stdout)
        return "\n".join(c.get("text", "") for c in payload.get("content", []))

    out: list[dict] = []
    for q in queries:
        # ⚠️ Exa 结果不稳定：同一条查询两次运行相差可以很大（实测 dry-run 10 条、
        # 真跑 1 条，且不报错）。所以每条都记返回数，空了重试一次；
        # 今天漏的明天可能又出来——它是发现渠道，不是权威索引。
        text = ""
        for attempt in (1, 2):
            try:
                text = call(q)
            except Exception as exc:  # noqa: BLE001
                print(f"  ! Exa「{q}」第 {attempt} 次失败：{exc}", file=sys.stderr)
                text = ""
            if text.strip():
                break
            time.sleep(2)
        n_before = len(out)

        # 返回体是固定格式的文本块：Title / URL / Published / Author / Highlights，块间用 --- 分隔
        for block in re.split(r"\n---\n", text):
            title = re.search(r"^Title:\s*(.+)$", block, re.M)
            url = re.search(r"^URL:\s*(\S+)$", block, re.M)
            pub = re.search(r"^Published:\s*(\d{4}-\d{2}-\d{2})", block, re.M)
            hl = re.search(r"Highlights:\s*\n(.*)", block, re.S)
            if not (title and url):
                continue
            summary = re.sub(r"\s+", " ", (hl.group(1) if hl else ""))[:300]
            if pub:
                age = (datetime.now(timezone.utc).date()
                       - datetime.strptime(pub.group(1), "%Y-%m-%d").date()).days
                if age > SEARCH_MAX_AGE_DAYS:
                    continue
            out.append({
                "source": f"Exa · {q}",
                "tier": "media",
                "title": norm(title.group(1)).lstrip("# ").strip(),
                "url": url.group(1),
                "date": pub.group(1) if pub else "",
                "summary": summary,
                "kind": "news",
            })
        print(f"  · Exa「{q}」返回 {len(out) - n_before} 条（30 天内）", file=sys.stderr)
        time.sleep(1)
    return out


def match_pages(vid: str, paths: list[str], limit: int = 3) -> list[str]:
    """把取值 id 匹配到上游页面。

    按连字符分词做**连续子序列**匹配，不做裸子串——裸子串会让 `arm`
    命中 armature-modeling、harmonic-drive、leftarmmotionsolver 一堆无关页。

    排序上让 concepts / methods / 非 paper 的 entities 靠前：
    那些是规范页，paper-* 是具体论文，不适合当轴取值的定义锚点。
    """
    want = [t for t in vid.split("-") if t]
    scored: list[tuple[int, str]] = []
    for p in paths:
        stem = Path(p).stem.lower()
        toks = [t for t in re.split(r"[-_]", stem) if t]
        hit = any(toks[i:i + len(want)] == want for i in range(len(toks) - len(want) + 1))
        if not hit:
            continue
        if stem == vid:
            rank = 0
        elif "/concepts/" in p or "/methods/" in p:
            rank = 1
        elif "paper-" in stem:
            rank = 3
        else:
            rank = 2
        scored.append((rank, p))
    return [p for _, p in sorted(scored)[:limit]]


def fetch_upstream(known_insts: set[str]) -> tuple[list[dict], set[str]]:
    """盯 Robotics_Notebooks 的两件事，只盯这两件。

    他一天几十个提交全是技术知识 ingest，全量接进来就是噪音，
    而且我们明确定过不重建技术知识、只引用。所以只看：

      1. institutions.json 的**新增条目** —— 他策展过的机构，是候选主体的好来源。
         只报增量，全量对比出来一百多条大厂噪音，没意义。
      2. 我们 ref 留空的轴取值，上游是否已经有页面可指。
    """
    out: list[dict] = []
    seen_insts = set(known_insts)

    try:
        r = httpx.get(
            "https://raw.githubusercontent.com/ImChong/Robotics_Notebooks"
            "/main/schema/institutions.json",
            timeout=25, headers=UA, follow_redirects=True,
        )
        r.raise_for_status()
        reg = json.loads(r.text).get("registry", {})
    except Exception as exc:  # noqa: BLE001
        print(f"  ! 上游机构表取不到：{type(exc).__name__}", file=sys.stderr)
        return out, seen_insts

    if known_insts:
        added = [(k, v.get("label", k)) for k, v in reg.items() if k not in known_insts]
        for k, label in added[:20]:
            out.append({
                "source": "Robotics_Notebooks · institutions",
                "tier": "aggregator",
                "title": f"上游新增机构：{label}",
                "url": f"https://github.com/ImChong/Robotics_Notebooks/blob/main/schema/institutions.json#{k}",
                "date": datetime.now(CST).strftime("%Y-%m-%d"),
                "summary": f"上游 institutions.json 新增 `{k}`。判断是否在本库边界内，在就建条目。",
                "kind": "upstream-org",
            })
        if len(added) > 20:
            print(f"  · 上游新增机构 {len(added)} 家，只报前 20", file=sys.stderr)
    else:
        print(f"  · 首次记录上游机构表（{len(reg)} 家），本轮不报增量", file=sys.stderr)
    seen_insts = set(reg)

    # 我们 ref 留空的取值，上游是否已经有页面了
    blanks: list[tuple[str, str, str]] = []
    doc = yaml.safe_load((ROOT / "vocab/axes-tech.yaml").read_text())
    for ax in doc["axes"]:
        for v in ax["values"]:
            if not v.get("ref"):
                blanks.append((ax["field"], v["id"], v["zh"]))
    if blanks:
        try:
            t = httpx.get(
                "https://api.github.com/repos/ImChong/Robotics_Notebooks"
                "/git/trees/main?recursive=1", timeout=30, headers=UA,
            ).json()
            paths = [x["path"] for x in t.get("tree", []) if x["path"].startswith("wiki/")]
        except Exception as exc:  # noqa: BLE001
            print(f"  ! 上游文件树取不到：{type(exc).__name__}", file=sys.stderr)
            paths = []
        for field, vid, zh in blanks:
            cands = match_pages(vid, paths)
            if cands:
                out.append({
                    "source": "Robotics_Notebooks · wiki",
                    "tier": "aggregator",
                    "title": f"可补引用：{zh}（{field}.{vid}）",
                    "url": f"https://github.com/ImChong/Robotics_Notebooks/blob/main/{cands[0]}",
                    "date": datetime.now(CST).strftime("%Y-%m-%d"),
                    "summary": "上游出现了可能对应的页面："
                               + "、".join(f"`{c}`" for c in cands)
                               + f"。核对后把 ref 填进 vocab/axes-tech.yaml 的 {vid}。",
                    "kind": "upstream-ref",
                })
    return out, seen_insts


# ----------------------------------------------------------------- 产出

def _day(date: str) -> str:
    """把各种日期写法压成 YYYY-MM-DD 或空，供聚类用。"""
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", date or "")
    if m:
        return m.group(0)
    m = re.search(r"(\d{1,2}) (\w{3}) (\d{4})", date or "")   # RSS 的 "21 Sep 2026"
    if m:
        months = {n: i for i, n in enumerate(
            ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
        mo = months.get(m.group(2)[:3].title())
        if mo:
            return f"{int(m.group(3)):04d}-{mo:02d}-{int(m.group(1)):02d}"
    return ""


def cluster_hits(hits: list[tuple[str, dict]]) -> list[list[dict]]:
    """同主体、同事件类型、发生日期相差 ≤3 天的合成一件事。

    Humanoid 融资被 8 家媒体报了 8 遍，超维动力 2 遍——那是一件事不是八件。
    HF 的批量发布已经在源头聚过，这里主要合新闻。
    """
    buckets: dict[tuple, list[dict]] = {}
    for _, it in hits:
        d = _day(it.get("date", ""))
        # 日期粗到 3 天桶，同一件事不同媒体发稿日差一两天很常见
        day_bucket = d[:8] + str(int(d[8:10]) // 3) if d else "?"
        key = (it["org"]["id"], it.get("kind", "news"), day_bucket)
        buckets.setdefault(key, []).append(it)
    groups = list(buckets.values())
    # 每组内按来源等级排：official > primary > media > aggregator，取最好的当头条
    rank = {"official": 0, "primary": 1, "media": 2, "aggregator": 3}
    for g in groups:
        g.sort(key=lambda x: (rank.get(x.get("tier"), 9), x.get("date", "")))

    # 组间排序决定谁能进每轮 15 个的名额。不能只按日期——第一次实跑时
    # 一笔 4 亿美元融资被 robopi_analyze v1.0.9 这种补丁版本挤进了 digest。
    # 商业信号是本库的立足点，新闻类命中比日常推送稀有得多，排前面；
    # 多个独立来源印证的再往前；同级才看日期。
    def source_class(g: list[dict]) -> int:
        src = g[0].get("source", "")
        if g[0].get("kind") == "news":
            return 0
        if src.startswith("Hugging Face"):
            return 1
        if src.startswith("GitHub"):
            return 2
        return 3

    # 稳定排序两遍：先按日期倒序，再按（来源类别，来源数）——同级内自然保持日期新的在前
    groups.sort(key=lambda g: _day(g[0].get("date", "")), reverse=True)
    groups.sort(key=lambda g: (source_class(g), -len(g)))
    return groups


def issue_body_group(group: list[dict]) -> str:
    """一件事多个来源 → 一条 issue。头条填表单字段，其余来源附在补充里。"""
    head = group[0]
    body = issue_body(head)
    if len(group) > 1:
        others = "\n".join(f"- [{x['title'][:70]}]({x['url']}) — {x['source']}" for x in group[1:])
        body += (f"\n\n### 其他来源（{len(group) - 1} 个，同一件事）\n\n{others}\n\n"
                 "多个独立来源报了同一件事，入库时 corroboration 可填 multi。")
    return body


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
    seen, insts = load_state()
    if args.no_state:
        seen = set()
    kw = re.compile("|".join(map(re.escape, conf["keywords"])))

    items: list[dict] = []
    for f in conf.get("rss") or []:
        items += fetch_rss(f["name"], f["url"], f.get("tier", "media"))
    if (conf.get("arxiv") or {}).get("enabled"):
        items += fetch_arxiv(conf["arxiv"]["query"], conf["arxiv"].get("max_results", 40))
    if (conf.get("huggingface") or {}).get("enabled"):
        items += fetch_huggingface(orgs)
    if (conf.get("github") or {}).get("enabled"):
        items += fetch_github(orgs)
    if (conf.get("exa") or {}).get("enabled"):
        items += fetch_exa(conf["exa"].get("queries") or [], conf["exa"].get("num_results", 8))
    if (conf.get("upstream") or {}).get("enabled"):
        up_items, insts = fetch_upstream(insts)
        items += up_items

    already = ingested_urls()
    hits, digest, skipped = [], [], 0
    for it in items:
        k = key_of(it["url"], it["title"])
        # 两道去重：报过的不再报，已入库的更不该报
        if k in seen or re.sub(r"[?#].*$", "", it.get("url", "")) in already:
            skipped += 1
            continue
        blob = f"{it['title']} {it.get('summary','')}"
        # 早报串烧提到七八家公司，命中任何一家都没意义，直接进 digest 让人扫一眼
        if is_roundup(it["title"]) and not it.get("org"):
            if kw.search(blob):
                digest.append((k, it))
            continue
        org = it.get("org") or match_org(blob, orgs)
        if org:
            it["org"] = org
            hits.append((k, it))
        elif it["kind"].startswith("upstream-"):
            # 上游线索天然没有主体可匹配，直接进 digest
            digest.append((k, it))
        elif it["kind"] == "paper":
            # 论文没匹配到产业主体就丢弃，不进 digest。
            # 本库只收产业主体，而 cs.RO 每天几十篇绝大多数是纯高校成果；
            # 全放进来候选表立刻变噪音，人就不看了。
            # 关键词也不用在这儿过一遍——arXiv 查询本身已经过滤过。
            continue
        elif kw.search(blob):
            digest.append((k, it))

    # 同一件事常被多家媒体报，聚成一条：一个 issue、多个来源 URL。
    # 多个独立来源正是 corroboration=multi 的依据，聚合是加分不是妥协。
    groups = cluster_hits(hits)

    papers = sum(1 for it in items if it["kind"] == "paper")
    print(f"抓到 {len(items)} 条（其中论文 {papers}），去重跳过 {skipped}，"
          f"命中主体 {len(hits)} 条 → 聚成 {len(groups)} 件事，仅命中关键词 {len(digest)}")

    for g in groups:
        head = g[0]
        extra = f"  ＋{len(g) - 1} 个来源" if len(g) > 1 else ""
        print(f"  ◆ [{head['org']['zh']}] {head['date']}  {head['title'][:50]}{extra}")
    for _, it in digest:
        print(f"  · {it['date']}  {it['title'][:52]}  ({it['source']})")

    if args.emit:
        out = Path(args.emit)
        out.mkdir(parents=True, exist_ok=True)
        # 每轮最多开这么多 issue。第一次实跑会把两周存量全倒出来（实测 41 件），
        # 一天 41 个 issue 没人看；溢出的放进 digest 让人扫一眼，明天再来。
        head_groups, overflow = groups[:MAX_ISSUES_PER_RUN], groups[MAX_ISSUES_PER_RUN:]
        for i, g in enumerate(head_groups):
            (out / f"hit-{i:02d}.md").write_text(issue_body_group(g), encoding="utf-8")
            (out / f"hit-{i:02d}.title").write_text(
                f"[事件] {g[0]['org']['zh']}：{g[0]['title'][:40]}", encoding="utf-8")
        # 溢出和「未匹配主体」是两码事，分开写，别再混进一条里当「新主体」——
        # 第一次实跑就把 20 条已收录主体的事件标成了「未匹配」。
        if overflow or digest:
            lines: list[str] = []
            if overflow:
                lines += [f"## 已收录主体的事件（{len(overflow)} 件，超出本轮 {MAX_ISSUES_PER_RUN} 个名额）", "",
                          "这些主体都在 registry 里，只是本轮名额满了。要收的直接说，或明天等它们再冒出来。", ""]
                for g in overflow:
                    it = g[0]
                    more = f"（＋{len(g) - 1} 个来源）" if len(g) > 1 else ""
                    lines.append(f"- [{it['org']['zh']}] [{it['date']}] [{it['title']}]({it['url']}){more} — {it['source']}")
                lines.append("")
            if digest:
                lines += [f"## 没匹配到主体的线索（{len(digest)} 条）", "",
                          "命中了关键词但 registry 里没有对应主体，多半是还没收录的公司。该收的用「新主体」模板建条目。", ""]
                for _, it in digest:
                    lines.append(f"- [{it['date']}] [{it['title']}]({it['url']}) — {it['source']}")
            (out / "digest.md").write_text("\n".join(lines), encoding="utf-8")
            (out / "digest.title").write_text(
                f"[线索] 溢出 {len(overflow)} 件 · 未匹配 {len(digest)} 条 · {datetime.now(CST):%Y-%m-%d}",
                encoding="utf-8")

    if not args.no_state:
        save_state(seen | {k for k, _ in hits} | {k for k, _ in digest}, insts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
