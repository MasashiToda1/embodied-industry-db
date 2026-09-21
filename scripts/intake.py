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


def build(fields: dict, issue_no: str = "") -> tuple[dict, list[str]]:
    """字段字典 → 事件结构 + 缺项清单。"""
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

    if first_party:
        evidence = {
            "tier": "first-party",
            "method": method,
            "retrieved": date_cls.today().isoformat(),
        }
    else:
        evidence = {
            "url": url,
            "publisher": "",
            "tier": "official" if url else "",
            "retrieved": date_cls.today().isoformat(),
            "snapshot": "",
        }
        if not url:
            missing.append("选了「有公开链接」但没填链接")
        else:
            missing.append("公开来源需存页面快照：用 make serve 粘链接走解析路径，会自动存")

    if not hits:
        missing.append(f"主体「{fields.get('org','')}」在 registry 里没有对应条目，需先建（注意先搜别名）")
    elif len(hits) > 1:
        missing.append(f"主体匹配到多个：{'、'.join(h['id'] for h in hits)}，需人工选定")

    etype = parse_choice(fields.get("type", "")) or "statement"
    primary = hits[0]["id"] if len(hits) == 1 else "TODO"

    event: dict = {
        "id": f"evt-{date or 'TODO'}-{primary}-{etype}-{issue_no or 'x'}",
        "date": date or "TODO",
        "date_precision": precision or "day",
        "type": etype,
        "orgs": [{"id": primary, "role": "subject"}],
        "title": {"zh": (fields.get("fact") or "").split("。")[0][:60]},
        "summary": {"zh": fields.get("fact", "")},
        "evidence": [evidence],
        "corroboration": "single",
    }
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--issue", type=int)
    ap.add_argument("--file")
    ap.add_argument("--write", action="store_true", help="确认无误后写入 events/")
    args = ap.parse_args()

    issue_no = ""
    if args.issue:
        body, title = fetch_issue(args.issue)
        issue_no = str(args.issue)
        print(f"issue #{args.issue}：{title}\n")
    elif args.file:
        body = Path(args.file).read_text()
    else:
        body = sys.stdin.read()

    fields = parse_body(body)
    if not fields:
        print("解析不到任何表单字段，确认这条 issue 是用「手工事件」模板提的")
        return 1

    event, missing = build(fields, issue_no)

    print("── 解析出的事件 ──")
    print(yaml.safe_dump(event, allow_unicode=True, sort_keys=False).rstrip())

    if missing:
        print("\n── 还缺 / 需人工确认 ──")
        for m in missing:
            print(f"  · {m}")

    blocking = [m for m in missing if "TODO" in str(event) or "registry 里没有" in m or "无法解析" in m]
    if args.write:
        if blocking:
            print("\n有阻塞项，拒绝写入。先补齐再来。")
            return 1
        year, month = str(event["date"])[:4], str(event["date"])[5:7]
        folder = ROOT / "events" / year / (month if month.isdigit() else "00")
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{event['id']}.yaml"
        if path.exists():
            print(f"\n已存在：{path.relative_to(ROOT)}")
            return 1
        path.write_text(
            yaml.safe_dump(event, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        print(f"\n已写入 {path.relative_to(ROOT)}。跑一次 make preflight。")
    else:
        print("\n（未写盘。确认无误后加 --write）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
