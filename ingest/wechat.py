"""微信公众号文章解析。

输入 URL 或整页 HTML，输出结构化字段 + 可存档的原始 HTML。

为什么不直接用 defuddle：它擅长抽正文，但微信最关键的两个字段
——公众号名和发布时间——藏在页面的 JS 变量里（`var ct = "..."`、
`var nickname = "..."`），通用抽取器拿不到。发布时间是本库的立命之本，
所以这里自己解。

URL 直取经常失败（微信有防抓、链接带时效参数），所以 HTML 粘贴是
一等路径而不是兜底。
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

CST = timezone(timedelta(hours=8))

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)

# 微信把元数据塞在内联脚本里，这几个变量名多年没变
RE_CT = re.compile(r'var\s+ct\s*=\s*"?(\d{9,})"?')
RE_CREATE_TIME = re.compile(r'var\s+create_time\s*=\s*"?(\d{9,})"?')
RE_NICKNAME = re.compile(r'var\s+nickname\s*=\s*"([^"]+)"')
RE_USER_NAME = re.compile(r'var\s+user_name\s*=\s*"([^"]+)"')
RE_APPUIN = re.compile(r'var\s+appuin\s*=\s*"([^"]+)"')
RE_TITLE_VAR = re.compile(r'var\s+msg_title\s*=\s*(?:\'|")(.*?)(?:\'|")\s*\.html', re.S)
# 「2026年9月18日 17:30」这类可见文本，URL 直取失败时的备用来源
RE_VISIBLE_DATE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")


@dataclass
class Article:
    url: str = ""
    title: str = ""
    account: str = ""
    account_id: str = ""
    published: str = ""          # YYYY-MM-DD，取不到则空
    published_basis: str = ""    # stated / derived / 空
    body: str = ""
    html: str = ""
    images: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.title and self.body)

    def summary_dict(self) -> dict:
        return {
            "url": self.url,
            "title": self.title,
            "account": self.account,
            "published": self.published,
            "published_basis": self.published_basis,
            "chars": len(self.body),
            "images": len(self.images),
            "warnings": self.warnings,
        }


def normalize(text: str) -> str:
    """微信正文里全是 \u200b、\xa0 和连续空行，先洗干净再入库。"""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u200b", "").replace("\ufeff", "")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def fetch(url: str, timeout: float = 20.0) -> str:
    """尝试直取。失败抛异常，由调用方转到粘贴路径。"""
    headers = {
        "User-Agent": UA,
        "Referer": "https://mp.weixin.qq.com/",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.text


def parse(html: str, url: str = "") -> Article:
    art = Article(url=url, html=html)
    soup = BeautifulSoup(html, "lxml")

    # 微信在文章被删或需验证时会返回一个正常 200 的提示页
    page_text = soup.get_text(" ", strip=True)[:400]
    for blocked in ("该内容已被发布者删除", "此内容因违规无法查看", "环境异常", "去微信打开"):
        if blocked in page_text:
            art.warnings.append(f"页面提示「{blocked}」，可能不是文章正文，请改用粘贴 HTML")

    art.title = _extract_title(soup, html)
    art.account, art.account_id = _extract_account(soup, html)
    art.published, art.published_basis = _extract_published(soup, html)
    art.body, art.images = _extract_body(soup, url)

    if not art.title:
        art.warnings.append("取不到标题")
    if not art.account:
        art.warnings.append("取不到公众号名")
    if not art.published:
        art.warnings.append("取不到发布时间，需人工填 date 与 date_basis")
    if len(art.body) < 80:
        art.warnings.append(f"正文只有 {len(art.body)} 字，可能没抓到主体")

    return art


def _extract_title(soup: BeautifulSoup, html: str) -> str:
    node = soup.select_one("#activity-name, h1.rich_media_title, h2.rich_media_title")
    if node and node.get_text(strip=True):
        return normalize(node.get_text(strip=True))
    meta = soup.find("meta", property="og:title")
    if meta and meta.get("content"):
        return normalize(meta["content"])
    m = RE_TITLE_VAR.search(html)
    if m:
        return normalize(m.group(1))
    if soup.title and soup.title.string:
        return normalize(soup.title.string)
    return ""


def _extract_account(soup: BeautifulSoup, html: str) -> tuple[str, str]:
    name = ""
    node = soup.select_one("#js_name, .rich_media_meta_nickname, .profile_nickname")
    if node and node.get_text(strip=True):
        name = normalize(node.get_text(strip=True))
    if not name:
        m = RE_NICKNAME.search(html)
        if m:
            name = normalize(m.group(1))
    if not name:
        meta = soup.find("meta", property="og:article:author")
        if meta and meta.get("content"):
            name = normalize(meta["content"])

    ident = ""
    for regex in (RE_USER_NAME, RE_APPUIN):
        m = regex.search(html)
        if m:
            ident = m.group(1)
            break
    return name, ident


def _extract_published(soup: BeautifulSoup, html: str) -> tuple[str, str]:
    """优先用 JS 里的 unix 时间戳，那是权威值；退化到页面可见日期。"""
    for regex in (RE_CT, RE_CREATE_TIME):
        m = regex.search(html)
        if m:
            ts = int(m.group(1))
            dt = datetime.fromtimestamp(ts, tz=CST)
            return dt.strftime("%Y-%m-%d"), "stated"

    node = soup.select_one("#publish_time, em#publish_time")
    text = node.get_text(strip=True) if node else ""
    if not text:
        text = soup.get_text(" ", strip=True)[:600]
    m = RE_VISIBLE_DATE.search(text)
    if m:
        y, mo, d = (int(x) for x in m.groups())
        return f"{y:04d}-{mo:02d}-{d:02d}", "stated"
    return "", ""


def _extract_body(soup: BeautifulSoup, url: str) -> tuple[str, list[str]]:
    root = soup.select_one("#js_content, .rich_media_content")
    if root is None:
        root = soup.body or soup

    images: list[str] = []
    for img in root.find_all("img"):
        # 微信懒加载：真实地址在 data-src
        src = img.get("data-src") or img.get("src") or ""
        if src.startswith("http"):
            images.append(src)

    parts: list[str] = []
    for node in root.find_all(["h1", "h2", "h3", "h4", "p", "li", "blockquote", "td", "section"]):
        # section 在微信里嵌套极深，只取没有块级子节点的那一层，避免整段重复
        if node.name == "section" and node.find(["p", "section", "li", "h1", "h2", "h3"]):
            continue
        text = normalize(node.get_text(" ", strip=True))
        if not text or len(text) < 2:
            continue
        if node.name in ("h1", "h2", "h3", "h4"):
            parts.append(f"## {text}")
        elif node.name == "li":
            parts.append(f"- {text}")
        else:
            parts.append(text)

    # 微信排版常把同一句拆进多个 section，去掉紧邻重复
    deduped: list[str] = []
    for part in parts:
        if deduped and (part == deduped[-1] or part in deduped[-1]):
            continue
        deduped.append(part)

    return "\n\n".join(deduped), images


def load(source: str, is_url: bool | None = None) -> Article:
    """统一入口。source 是 URL 就抓，是 HTML 就直接解。"""
    looks_url = source.strip().startswith("http") and "\n" not in source.strip()
    if is_url is None:
        is_url = looks_url

    if is_url:
        url = source.strip()
        try:
            html = fetch(url)
        except Exception as exc:  # noqa: BLE001
            art = Article(url=url)
            art.warnings.append(f"直取失败（{type(exc).__name__}: {exc}），请改用粘贴 HTML")
            return art
        return parse(html, url)

    return parse(source, "")


def save_snapshot(root: Path, art: Article, published: str, prefix: str = "wechat") -> str:
    """把原始 HTML 落盘。没有快照的事件进不了库，所以这一步不可跳过。"""
    date = published or datetime.now(CST).strftime("%Y-%m-%d")
    year, month = date[:4], date[5:7]
    folder = root / "snapshots" / year / month
    folder.mkdir(parents=True, exist_ok=True)

    # 快照文件名只留 ASCII；中文标题落在文件头注释里，不靠文件名承载。
    # 公众号名基本都是中文，所以优先用 ASCII 的公众号 id（gh_xxx）做辨识。
    raw = art.account_id or art.account or ""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", raw).strip("-").lower()[:24]
    stem = f"{prefix}-{date}-{slug or 'article'}"

    # 同一篇反复解析很常见（调参数、改判断），内容一样就复用已有快照，
    # 否则 snapshots/ 会被 -2 -3 -4 撑满。
    #
    # 指纹按「提取出的标题＋正文」算，不按原始 HTML：微信每次返回的页面都带
    # 请求级 token，原始字节每次都变，拿它当指纹永远命不中。
    digest = hashlib.sha256(
        f"{art.title}\n{art.body}".encode("utf-8", "ignore")
    ).hexdigest()[:12]
    for existing in sorted(folder.glob(f"{stem}*.html")):
        if f"sha256:{digest}" in existing.read_text(encoding="utf-8", errors="ignore")[:400]:
            return str(existing.relative_to(root))

    path = folder / f"{stem}.html"
    n = 2
    while path.exists():
        path = folder / f"{stem}-{n}.html"
        n += 1

    header = (
        f"<!-- 抓取于 {datetime.now(CST).isoformat()}"
        f" | 原始链接 {art.url or '（粘贴）'}"
        f" | 公众号 {art.account or '未知'}"
        f" | 标题 {art.title or '未知'}"
        f" | sha256:{digest} -->\n"
    )
    path.write_text(header + art.html, encoding="utf-8")
    return str(path.relative_to(root))
