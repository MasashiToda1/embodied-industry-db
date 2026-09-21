#!/usr/bin/env python3
"""把 issue 表单转成事件草稿。

手机上随手填一条 issue，这里把它变成 events/ 下的 YAML。
GitHub Issue Forms 的正文格式是可预测的（`### 标签` 后跟值），所以能稳定解析。

用法：
    python3 scripts/intake.py --issue 12              # 从 GitHub 拉（需要 gh CLI）
    python3 scripts/intake.py --file body.md          # 从文件读正文
    cat body.md | python3 scripts/intake.py           # 从 stdin 读
    ... --write                                       # 确认无误后写入 events/

默认只打印解析结果和缺什么，不写盘。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import unicodedata
from datetime import date as date_cls
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))          # 让 snapshot() 能 import ingest.wechat
NO_RESPONSE = {"_no response_", "_No response_", "无", ""}

# 表单标签 → 内部字段
FIELDS = {
    "主体": "org",
    "什么时候发生": "happened",
    "什么事": "fact",
    "怎么知道的": "method",
    "公开链接": "url",
    "事件类型": "type",
    "金额": "amount",
    "买方或对方": "counterparty",
    "补充": "extra",
}

RE_SECTION = re.compile(r"^###\s+(.+?)\s*$", re.M)

# 「2026-09-10」「2026-09」「2026-Q3」「2026」以及中文写法
RE_DAY = re.compile(r"(\d{4})\s*[-年/.]\s*(\d{1,2})\s*[-月/.]\s*(\d{1,2})")
RE_MONTH = re.compile(r"(\d{4})\s*[-年/.]\s*(\d{1,2})\s*月?$")
RE_QUARTER = re.compile(r"(\d{4})\s*[-\s]*Q([1-4])", re.I)
RE_YEAR = re.compile(r"^(\d{4})\s*年?")
RE_HALF = re.compile(r"(\d{4})\s*年?\s*(上|下)半年")

# 「万」「亿」放在前面先匹配，否则 480 万元 会被当成 480 元。
# 币种后缀也要收进来，否则「30000 美元」里的「元」前面是「美」，匹配不到单位。
RE_AMOUNT = re.compile(
    r"(?P<num>\d[\d,]*(?:\.\d+)?)\s*"
    r"(?P<unit>亿美元|万美元|亿欧元|万欧元|亿元|万元|亿|万|美元|欧元|港元|元)"
)


def parse_body(text: str) -> dict:
    """issue 表单正文 → 字段字典。"""
    out: dict[str, str] = {}
    marks = list(RE_SECTION.finditer(text))
    for i, m in enumerate(marks):
        label = unicodedata.normalize("NFKC", m.group(1)).strip()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        value = text[m.end() : end].strip()
        if value in NO_RESPONSE:
            value = ""
        key = FIELDS.get(label)
        if key:
            out[key] = value
    return out


def parse_choice(value: str) -> str:
    """下拉项形如「vendor-inquiry — 以买方身份向厂商询价」，取破折号前的 id。"""
    if not value:
        return ""
    return re.split(r"\s+[—-]\s+", value.strip(), maxsplit=1)[0].strip()


def parse_when(raw: str) -> tuple[str, str, str, str]:
    """返回（date, precision, basis, as_stated）。

    模糊表述钉成具体日期时一律标 estimated 并保留原话，保证可逆。
    """
    s = unicodedata.normalize("NFKC", raw or "").strip()
    if not s:
        return "", "", "", ""

    m = RE_HALF.search(s)
    if m:
        year, half = m.group(1), m.group(2)
        # 取区间末月，与 compile 的粗精度排序口径一致
        return (f"{year}-06" if half == "上" else f"{year}-12"), "month", "estimated", s

    m = RE_DAY.search(s)
    if m:
        y, mo, d = (int(x) for x in m.groups())
        return f"{y:04d}-{mo:02d}-{d:02d}", "day", "stated", ""

    m = RE_QUARTER.search(s)
    if m:
        return f"{m.group(1)}-Q{m.group(2)}", "quarter", "stated", ""

    m = RE_MONTH.search(s)
    if m:
        y, mo = (int(x) for x in m.groups())
        return f"{y:04d}-{mo:02d}", "month", "stated", ""

    m = RE_YEAR.match(s)
    if m:
        return m.group(1), "year", "stated", ""

    return "", "", "", s


def parse_amount(raw: str) -> dict | None:
    """金额。单位不明确一律返回 None——留空好过写错一个量级。"""
    if not raw:
        return None
    s = unicodedata.normalize("NFKC", raw)
    m = RE_AMOUNT.search(s)
    if not m:
        return None
    num = float(m.group("num").replace(",", ""))
    unit = m.group("unit")
    # 量级和币种分开判，这样「万美元」「亿欧元」都不用单独列
    if unit.startswith("亿"):
        num *= 10**8
    elif unit.startswith("万"):
        num *= 10**4
    currency = (
        "USD" if "美元" in unit else
        "EUR" if "欧元" in unit else
        "HKD" if "港元" in unit else
        "CNY"
    )
    return {"value": num, "currency": currency}


def load_orgs() -> list[dict]:
    out = []
    folder = ROOT / "registry/orgs"
    if folder.exists():
        for path in sorted(folder.glob("*.yaml")):
            doc = yaml.safe_load(path.read_text()) or {}
            names = doc.get("names") or {}
            out.append({
                "id": doc.get("id"),
                "zh": names.get("zh"),
                "en": names.get("en"),
                "aliases": names.get("aliases") or [],
            })
    return out


def match_org(name: str, orgs: list[dict]) -> list[dict]:
    """双向包含匹配。只给候选，不自动绑定。"""
    if not name:
        return []
    hits = []
    for org in orgs:
        for cand in [org.get("zh") or "", org.get("en") or "", *(org.get("aliases") or [])]:
            if len(cand) < 2:
                continue
            if cand in name or (len(cand) >= 4 and name in cand):
                hits.append({"id": org["id"], "zh": org.get("zh"), "matched": cand})
                break
    return hits


RE_URL = re.compile(r"https?://[^\s;；)）\]]+")
OFFICIAL_HOSTS = ("huggingface.co", "github.com", "arxiv.org")

# 从标题推事件类型。watch.py 生成的 issue 标题格式固定，推得准；手填的留空就默认 statement。
TYPE_HINTS = [
    (re.compile(r"发布数据集|批量发布 \d+ 个数据集|dataset"), "dataset_release"),
    (re.compile(r"发布模型|新建仓库|新建 \d+ 个仓库|发布 \S+ v?\d|开源|release"), "publication"),
    (re.compile(r"融资|轮|raises|funding"), "funding"),
    (re.compile(r"中标|采购|成交"), "procurement"),
    (re.compile(r"部署|落地|签约|deploy"), "deployment"),
    (re.compile(r"发布会|新品|上市|开售"), "product_launch"),
]


def infer_type(text: str) -> str:
    for rx, t in TYPE_HINTS:
        if rx.search(text):
            return t
    return "statement"


def tier_for(url: str) -> str:
    """官方托管页（HF / GitHub / arXiv）是主体自己发的，算 official；其余算 media。"""
    return "official" if any(h in url for h in OFFICIAL_HOSTS) else "media"


def snapshot(url: str, date: str, tag: str) -> str:
    """抓原页面落盘。公开来源没有快照进不了库，这一步不能省。"""
    import httpx

    from ingest import wechat

    r = httpx.get(url, timeout=30, follow_redirects=True,
                  headers={"User-Agent": "Mozilla/5.0 (compatible; embodied-industry-db)"})
    r.raise_for_status()
    art = wechat.Article(title=tag, html=r.text, url=url, account_id=tag)
    host = re.sub(r"^www\.", "", re.sub(r"^https?://", "", url).split("/")[0]).split(".")[0]
    return wechat.save_snapshot(ROOT, art, date, prefix=host[:12])


def build(fields: dict, issue_no: str = "", fetch: bool = False) -> tuple[dict, list[str]]:
    """字段字典 → 事件结构 + 缺项清单。fetch=True 时抓页面存快照。"""
    missing: list[str] = []
    orgs = load_orgs()
    hits = match_org(fields.get("org", ""), orgs)

    date, precision, basis, as_stated = parse_when(fields.get("happened", ""))
    if not date:
        missing.append(f"发生时间无法解析（原文「{fields.get('happened','')}」），需人工填 date")

    method = parse_choice(fields.get("method", ""))
    url = fields.get("url", "").strip()
    first_party = method in {
        "interview", "customer-review", "vendor-inquiry", "field-observation", "hands-on-test"
    }

    # 「其他来源」写在补充里，一条 URL 一个 evidence；多个独立来源就是 corroboration=multi
    extra_urls = [u for u in RE_URL.findall(fields.get("extra", "")) if u != url]
    evidences: list[dict] = []

    if first_party:
        evidences.append({
            "tier": "first-party",
            "method": method,
            "retrieved": date_cls.today().isoformat(),
        })
    else:
        if not url:
            missing.append("选了「有公开链接」但没填链接")
        for u in ([url] if url else []) + extra_urls:
            ev = {"url": u, "publisher": "", "tier": tier_for(u),
                  "retrieved": date_cls.today().isoformat(), "snapshot": ""}
            if fetch and date:
                try:
                    ev["snapshot"] = snapshot(u, date, (hits[0]["id"] if hits else "src"))
                except Exception as exc:  # noqa: BLE001
                    missing.append(f"快照抓取失败 {u[:60]}：{type(exc).__name__}")
            elif not fetch:
                missing.append("公开来源需存页面快照（加 --fetch 自动抓）")
            evidences.append(ev)

    if not hits:
        missing.append(f"主体「{fields.get('org','')}」在 registry 里没有对应条目，需先建（注意先搜别名）")
    elif len(hits) > 1:
        missing.append(f"主体匹配到多个：{'、'.join(h['id'] for h in hits)}，需人工选定")

    etype = parse_choice(fields.get("type", "")) or infer_type(fields.get("fact", ""))
    primary = hits[0]["id"] if len(hits) == 1 else "TODO"

    fact = fields.get("fact", "").strip()
    # watch.py 生成的 fact 形如「标题。摘要」，标题就是句号前那段
    title_zh = fact.split("。")[0][:60]

    event: dict = {
        "id": f"evt-{date or 'TODO'}-{primary}-{etype}-{issue_no or 'x'}",
        "date": date or "TODO",
        "date_precision": precision or "day",
        "type": etype,
        "orgs": [{"id": primary, "role": "subject"}],
        "title": {"zh": title_zh},
        "summary": {"zh": fact},
        "evidence": evidences,
        "corroboration": "multi" if len(evidences) > 1 else "single",
    }

    # 数据集发布：许可写在摘要里，能直接给 data_openness。模型开源不算——那是权重不是数据。
    if etype == "dataset_release":
        lic = re.search(r"许可\s*([\w.\-]+)", fact)
        if lic and lic.group(1).lower() not in ("未标", "none", "unknown", "other"):
            event["axes"] = {"data_openness": "fully-open"}
    if basis and basis != "stated":
        event["date_basis"] = basis
        event["date_as_stated"] = as_stated
    if fields.get("counterparty"):
        event["counterparties"] = [fields["counterparty"]]

    amount = parse_amount(fields.get("amount", ""))
    if amount:
        event["amount"] = amount
    elif fields.get("amount"):
        missing.append(f"金额「{fields['amount']}」单位不明确，已留空——留空好过写错一个量级")

    if fields.get("extra"):
        missing.append("补充信息里可能含轴取值线索，需人工对到词表：" + fields["extra"][:80])
    missing.append("轴取值未填：手工事件不做关键词抽取，按事实自己判")

    return event, missing


def fetch_issue(number: int) -> tuple[str, str]:
    raw = subprocess.run(
        ["gh", "issue", "view", str(number), "--json", "body,title"],
        capture_output=True, text=True, check=True,
    ).stdout
    d = json.loads(raw)
    return d.get("body") or "", d.get("title") or ""


def is_blocking(event: dict, missing: list[str]) -> bool:
    return ("TODO" in str(event)
            or any("registry 里没有" in m or "无法解析" in m or "快照抓取失败" in m for m in missing))


def write_event(event: dict) -> Path:
    year, month = str(event["date"])[:4], str(event["date"])[5:7]
    folder = ROOT / "events" / year / (month if month.isdigit() else "00")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{event['id']}.yaml"
    if path.exists():
        raise FileExistsError(str(path.relative_to(ROOT)))
    path.write_text(yaml.safe_dump(event, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def process_one(body: str, issue_no: str, fetch: bool, write: bool, quiet: bool) -> tuple[bool, str]:
    """处理一条。返回（是否写入, 一行摘要）。"""
    fields = parse_body(body)
    if not fields:
        return False, f"#{issue_no}: 解析不到表单字段，不是「手工事件」模板"
    event, missing = build(fields, issue_no, fetch=fetch)
    if not quiet:
        print("── 解析出的事件 ──")
        print(yaml.safe_dump(event, allow_unicode=True, sort_keys=False).rstrip())
        if missing:
            print("\n── 还缺 / 需人工确认 ──")
            for m in missing:
                print(f"  · {m}")
    blocking = is_blocking(event, missing)
    label = f"#{issue_no} {event['orgs'][0]['id']:<16} {event['title']['zh'][:40]}"
    if blocking:
        why = "；".join(m for m in missing if "registry" in m or "无法解析" in m or "快照" in m)[:80]
        return False, f"✗ {label}  阻塞：{why}"
    if not write:
        return False, f"· {label}  （未写盘）"
    try:
        path = write_event(event)
    except FileExistsError as exc:
        return False, f"= {label}  已存在 {exc}"
    return True, f"✓ {label}  → {path.relative_to(ROOT)}"


def parse_issue_range(spec: str) -> list[int]:
    out: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        elif part:
            out.append(int(part))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--issue", type=int)
    ap.add_argument("--issues", help="批量，如 6-24 或 6,7,21-24")
    ap.add_argument("--file")
    ap.add_argument("--fetch", action="store_true", help="抓原页面存快照（公开来源入库必需）")
    ap.add_argument("--write", action="store_true", help="确认无误后写入 events/")
    args = ap.parse_args()

    if args.issues:
        results = []
        for n in parse_issue_range(args.issues):
            try:
                body, _ = fetch_issue(n)
            except Exception as exc:  # noqa: BLE001
                results.append((False, f"✗ #{n} 取不到 issue：{type(exc).__name__}"))
                continue
            results.append(process_one(body, str(n), args.fetch, args.write, quiet=True))
        ok = sum(1 for w, _ in results if w)
        for _, line in results:
            print(line)
        print(f"\n{len(results)} 条：写入 {ok}，未写 {len(results) - ok}")
        if args.write and ok:
            print("跑一次 make preflight。")
        return 0

    issue_no = ""
    if args.issue:
        body, title = fetch_issue(args.issue)
        issue_no = str(args.issue)
        print(f"issue #{args.issue}：{title}\n")
    elif args.file:
        body = Path(args.file).read_text()
    else:
        body = sys.stdin.read()

    wrote, line = process_one(body, issue_no, args.fetch, args.write, quiet=False)
    print("\n" + line)
    if not args.write:
        print("（未写盘。确认无误后加 --write，公开来源再加 --fetch 抓快照）")
    return 0 if (wrote or not args.write) else 1


if __name__ == "__main__":
    sys.exit(main())
