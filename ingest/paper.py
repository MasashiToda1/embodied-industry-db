"""论文解析。

论文是技术轴取值最密的来源——一篇常同时透露运控路线、模型形态和仿真栈。
但它的信号比产品发布弱：论文说明团队研究过什么，不说明产品里跑什么。
所以抽取只产生**候选**，带上命中的原文片段，由人确认。

输入支持三种：arXiv 编号（2503.12345）、arXiv 页面 URL、直接粘摘要文本。
"""

from __future__ import annotations

import re
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import yaml
from bs4 import BeautifulSoup

# 必须用 https：arXiv 对 http 返回 301，且要跟随重定向
ARXIV_API = "https://export.arxiv.org/api/query"
ATOM = "{http://www.w3.org/2005/Atom}"
UA = {"User-Agent": "Mozilla/5.0 (compatible; embodied-industry-db)"}

RE_ARXIV_ID = re.compile(r"(?:arxiv\.org/(?:abs|pdf)/)?(\d{4}\.\d{4,5})(?:v\d+)?")


@dataclass
class Paper:
    arxiv_id: str = ""
    title: str = ""
    abstract: str = ""
    authors: list[str] = field(default_factory=list)
    published: str = ""
    updated: str = ""
    url: str = ""
    code_url: str = ""
    html: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.title and self.abstract)

    def summary_dict(self) -> dict:
        return {
            "arxiv_id": self.arxiv_id,
            "title": self.title,
            "published": self.published,
            "authors": len(self.authors),
            "abstract_chars": len(self.abstract),
            "url": self.url,
            "warnings": self.warnings,
        }


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace("\u200b", "")
    return re.sub(r"\s+", " ", text).strip()


# ----------------------------------------------------------------- 取数

def fetch_arxiv(arxiv_id: str, timeout: float = 20.0) -> Paper:
    """走 arXiv 官方 API。免费、无需 key，返回 Atom XML。"""
    # ⚠️ arXiv 限流紧且返回 406 而不是 429，很容易被当成参数错。
    # 官方要求请求间隔 ≥3 秒，密集调用会被挡一段时间。
    with httpx.Client(timeout=timeout, follow_redirects=True, headers=UA) as client:
        resp = client.get(f"{ARXIV_API}?id_list={arxiv_id}&max_results=1")
        if resp.status_code == 406:
            raise RuntimeError("arXiv 返回 406＝被限流，等几分钟再试，或改用粘贴 abs 页面")
        resp.raise_for_status()
        return parse_atom(resp.text, arxiv_id)


def parse_atom(xml_text: str, arxiv_id: str = "") -> Paper:
    p = Paper(arxiv_id=arxiv_id, html=xml_text)
    root = ET.fromstring(xml_text)
    entry = root.find(f"{ATOM}entry")
    if entry is None:
        p.warnings.append("arXiv 返回里没有条目，核对编号")
        return p

    def text_of(tag: str) -> str:
        node = entry.find(f"{ATOM}{tag}")
        return normalize(node.text) if node is not None and node.text else ""

    p.title = text_of("title")
    p.abstract = text_of("summary")
    p.published = text_of("published")[:10]
    p.updated = text_of("updated")[:10]
    p.authors = [
        normalize(n.text)
        for a in entry.findall(f"{ATOM}author")
        for n in a.findall(f"{ATOM}name")
        if n.text
    ]
    for link in entry.findall(f"{ATOM}link"):
        if link.get("rel") == "alternate":
            p.url = link.get("href") or ""
    if not p.arxiv_id and p.url:
        m = RE_ARXIV_ID.search(p.url)
        if m:
            p.arxiv_id = m.group(1)
    if not p.url and p.arxiv_id:
        p.url = f"https://arxiv.org/abs/{p.arxiv_id}"
    return p


def parse_abs_page(html: str) -> Paper:
    """解析 arXiv abs 页面 HTML，直取失败时的粘贴路径。"""
    soup = BeautifulSoup(html, "lxml")
    p = Paper(html=html)

    node = soup.select_one("h1.title")
    if node:
        p.title = normalize(node.get_text(" ", strip=True).replace("Title:", ""))
    node = soup.select_one("blockquote.abstract")
    if node:
        p.abstract = normalize(node.get_text(" ", strip=True).replace("Abstract:", ""))
    p.authors = [normalize(a.get_text()) for a in soup.select("div.authors a")]

    node = soup.select_one("div.dateline")
    if node:
        m = re.search(r"(\d{1,2})\s+(\w+)\s+(\d{4})", node.get_text())
        if m:
            months = {m3[:3].lower(): i for i, m3 in enumerate(
                ["January","February","March","April","May","June","July",
                 "August","September","October","November","December"], 1)}
            mo = months.get(m.group(2)[:3].lower())
            if mo:
                p.published = f"{int(m.group(3)):04d}-{mo:02d}-{int(m.group(1)):02d}"

    meta = soup.find("meta", attrs={"name": "citation_arxiv_id"})
    if meta and meta.get("content"):
        p.arxiv_id = meta["content"]
    if p.arxiv_id:
        p.url = f"https://arxiv.org/abs/{p.arxiv_id}"
    return p


def load(source: str) -> Paper:
    """统一入口：arXiv 编号、URL、abs 页面 HTML 或纯摘要文本。"""
    s = source.strip()

    if s.startswith("<") or "<html" in s[:400].lower():
        p = parse_abs_page(s)
        if not p.ok:
            p.warnings.append("页面里取不到标题或摘要，可改为直接粘标题与摘要文本")
        return p

    m = RE_ARXIV_ID.fullmatch(s) or (RE_ARXIV_ID.search(s) if "arxiv.org" in s else None)
    if m:
        try:
            return fetch_arxiv(m.group(1))
        except Exception as exc:  # noqa: BLE001
            p = Paper(arxiv_id=m.group(1), url=f"https://arxiv.org/abs/{m.group(1)}")
            p.warnings.append(f"arXiv 直取失败（{type(exc).__name__}），可粘 abs 页面 HTML 或摘要文本")
            return p

    # 纯文本：第一行当标题，其余当摘要
    lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
    p = Paper()
    if lines:
        p.title = normalize(lines[0])
        p.abstract = normalize(" ".join(lines[1:]))
    if not p.abstract:
        p.warnings.append("只取到标题没有摘要，轴抽取会很不准")
    p.warnings.append("纯文本来料：无 arXiv 编号与链接，需手填原文链接")
    return p


# ----------------------------------------------------------------- 轴抽取

def load_keywords(root: Path) -> dict:
    return (yaml.safe_load((root / "vocab/keywords.yaml").read_text()) or {}).get("axes", {})


def extract_axes(text: str, keywords: dict) -> dict:
    """关键词命中 → 轴候选，每条带原文片段。

    只出候选不出结论：命中「MuJoCo」可能来自相关工作而非本文方法，
    所以必须把片段给人看。
    """
    lowered = text.lower()
    out: dict[str, list[dict]] = {}
    for field_name, values in keywords.items():
        for value_id, words in (values or {}).items():
            for word in words:
                pos = lowered.find(word.lower())
                if pos < 0:
                    continue
                start, end = max(0, pos - 60), min(len(text), pos + len(word) + 60)
                out.setdefault(field_name, []).append({
                    "value": value_id,
                    "matched": word,
                    "snippet": "…" + text[start:end].strip() + "…",
                })
                break
    return out


def match_orgs(text: str, orgs: list[dict], min_len: int = 3) -> list[dict]:
    """从作者与机构文本里匹配 registry 主体。

    arXiv 元数据不含可靠的机构字段，所以命中率有限，只作提示。
    英文名短于 min_len 的不参与匹配，避免 1X、UR 这类误命中。
    """
    if not text:
        return []
    lowered = text.lower()
    hits = []
    for org in orgs:
        for cand in [org.get("zh") or "", org.get("en") or "", *(org.get("aliases") or [])]:
            if not cand or len(cand) < min_len:
                continue
            if cand.lower() in lowered:
                hits.append({"id": org["id"], "zh": org.get("zh"), "matched": cand})
                break
    return hits
