"""招投标公告解析。

招投标是「商业信号」里唯一能直接给出「谁在买、多少钱」的公开源，
而且中美欧都有公开平台。但公告格式极不统一，所以这里只做抽取与归一化，
判定仍然交给人审。

最容易出错的是金额：中文公告里「元」和「万元」混用，还有大写数字，
差一个量级就是一万倍的脏数据。所以 parse_amount 是本模块的重点，
拿不准一律返回 None —— 留空好过写错。
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

CN_DIGITS = {
    "零": 0, "一": 1, "壹": 1, "二": 2, "贰": 2, "两": 2, "三": 3, "叁": 3,
    "四": 4, "肆": 4, "五": 5, "伍": 5, "六": 6, "陆": 6, "七": 7, "柒": 7,
    "八": 8, "捌": 8, "九": 9, "玖": 9,
}
CN_UNITS = {"十": 10, "拾": 10, "百": 100, "佰": 100, "千": 1000, "仟": 1000}
CN_BIG = {"万": 10**4, "亿": 10**8}

CURRENCY_HINTS = [
    (re.compile(r"美元|USD|\$"), "USD"),
    (re.compile(r"欧元|EUR|€"), "EUR"),
    (re.compile(r"港[币元]|HKD"), "HKD"),
    (re.compile(r"日元|JPY"), "JPY"),
    (re.compile(r"人民币|元|CNY|￥|¥|RMB"), "CNY"),
]

# 「中标金额：123.45 万元」「成交金额 1,234,567.89元」
RE_AMOUNT_ARABIC = re.compile(
    r"(?P<num>\d[\d,]*(?:\.\d+)?)\s*(?P<unit>亿元|亿|万元|万|元|美元|欧元)"
)
# 大写金额：「人民币壹佰贰拾叁万肆仟元整」
RE_AMOUNT_CN = re.compile(r"[零一壹二贰两三叁四肆五伍六陆七柒八捌九玖十拾百佰千仟万亿]{2,}(?=元)")

LABELS = {
    "project": ["项目名称", "标的名称", "采购项目名称", "工程名称"],
    "project_no": ["项目编号", "招标编号", "采购编号", "标段编号", "项目代码"],
    "buyer": ["采购人", "招标人", "采购单位", "招标单位", "建设单位", "采购方"],
    "winner": ["中标人", "中标供应商", "成交供应商", "中标单位", "第一中标候选人", "成交人", "中选人"],
    "amount": ["中标金额", "成交金额", "中标价", "成交价", "合同金额", "中标总价", "签约金额"],
    "date": ["公告日期", "发布日期", "公示日期", "中标日期", "成交日期"],
    "agent": ["代理机构", "采购代理机构", "招标代理"],
}

RE_DATE = re.compile(r"(\d{4})\s*[-年/.]\s*(\d{1,2})\s*[-月/.]\s*(\d{1,2})")
RE_DATE_MONTH = re.compile(r"(\d{4})\s*[-年/.]\s*(\d{1,2})\s*月?(?!\s*[-日/.]?\s*\d)")


@dataclass
class Tender:
    project: str = ""
    project_no: str = ""
    buyer: str = ""
    winner: str = ""
    agent: str = ""
    amount_value: float | None = None
    amount_currency: str = ""
    amount_raw: str = ""
    date: str = ""
    date_precision: str = ""
    text: str = ""
    warnings: list[str] = field(default_factory=list)

    def summary_dict(self) -> dict:
        return {
            "project": self.project,
            "project_no": self.project_no,
            "buyer": self.buyer,
            "winner": self.winner,
            "amount": None
            if self.amount_value is None
            else {"value": self.amount_value, "currency": self.amount_currency},
            "amount_raw": self.amount_raw,
            "date": self.date,
            "date_precision": self.date_precision,
            "chars": len(self.text),
            "warnings": self.warnings,
        }


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u3000", " ").replace("\u200b", "")
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def cn_number(s: str) -> float | None:
    """解析中文大写数字。看不懂就返回 None，绝不猜。"""
    total = 0.0
    section = 0.0
    current = 0.0
    for ch in s:
        if ch in CN_DIGITS:
            current = CN_DIGITS[ch]
        elif ch in CN_UNITS:
            section += (current or 1) * CN_UNITS[ch]
            current = 0
        elif ch in CN_BIG:
            section = (section + current) * CN_BIG[ch]
            total += section
            section = current = 0
        else:
            return None
    result = total + section + current
    return result or None


def detect_currency(context: str) -> str:
    for pattern, code in CURRENCY_HINTS:
        if pattern.search(context):
            return code
    return ""


def parse_amount(text: str) -> tuple[float | None, str, str]:
    """从公告文本里解析金额，返回（数值, 币种, 原文片段）。

    只在金额标签附近取值，避免把项目编号或联系电话当成钱。
    「万元」与「元」的量级差一万倍，所以单位必须显式命中，否则不返回。
    """
    window = _label_window(text, LABELS["amount"])
    scope = window or text

    m = RE_AMOUNT_ARABIC.search(scope)
    if m:
        raw = m.group(0)
        num = float(m.group("num").replace(",", ""))
        unit = m.group("unit")
        if unit in ("亿元", "亿"):
            num *= 10**8
        elif unit in ("万元", "万"):
            num *= 10**4
        currency = detect_currency(raw) or detect_currency(scope) or "CNY"
        return num, currency, raw

    m = RE_AMOUNT_CN.search(scope)
    if m:
        raw = m.group(0)
        value = cn_number(raw)
        if value is not None:
            return value, detect_currency(scope) or "CNY", raw + "元"

    return None, "", ""


def _label_window(text: str, labels: list[str], width: int = 60) -> str:
    """取标签后面一小段。公告里字段是「标签：值」，值就在标签右侧。"""
    for label in labels:
        idx = text.find(label)
        if idx >= 0:
            return text[idx : idx + len(label) + width]
    return ""


def _field_after_label(text: str, labels: list[str]) -> str:
    for label in labels:
        # 「中标人：某某公司」「中标人 某某公司」「中标人|某某公司」
        m = re.search(
            rf"{re.escape(label)}\s*[:：\|]?\s*(?P<val>[^\n\|：:]{{2,80}})", text
        )
        if m:
            val = m.group("val").strip(" 　·、,，。;；")
            # 值里又出现别的标签说明这行是表头，跳过
            if any(other in val for group in LABELS.values() for other in group):
                continue
            if val:
                return val
    return ""


def parse_date(text: str) -> tuple[str, str]:
    window = _label_window(text, LABELS["date"], width=40) or text
    m = RE_DATE.search(window)
    if m:
        y, mo, d = (int(x) for x in m.groups())
        return f"{y:04d}-{mo:02d}-{d:02d}", "day"
    m = RE_DATE_MONTH.search(window)
    if m:
        y, mo = (int(x) for x in m.groups())
        return f"{y:04d}-{mo:02d}", "month"
    return "", ""


def parse(source: str) -> Tender:
    """输入整页 HTML 或纯文本公告，输出结构化字段。"""
    if "<" in source and ">" in source:
        soup = BeautifulSoup(source, "lxml")
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = normalize(soup.get_text("\n", strip=True))
    else:
        text = normalize(source)

    t = Tender(text=text)
    t.project = _field_after_label(text, LABELS["project"])
    t.project_no = _field_after_label(text, LABELS["project_no"])
    t.buyer = _field_after_label(text, LABELS["buyer"])
    t.winner = _field_after_label(text, LABELS["winner"])
    t.agent = _field_after_label(text, LABELS["agent"])
    t.amount_value, t.amount_currency, t.amount_raw = parse_amount(text)
    t.date, t.date_precision = parse_date(text)

    if not t.winner:
        t.warnings.append("取不到中标人，需人工确认主体")
    if not t.buyer:
        t.warnings.append("取不到采购人")
    if t.amount_value is None:
        t.warnings.append("取不到金额或单位不明确，宁可留空也不要填估算值")
    elif t.amount_value < 1000:
        t.warnings.append(
            f"金额 {t.amount_value} 偏小，核对原文单位是「元」还是「万元」（原文：{t.amount_raw}）"
        )
    if not t.date:
        t.warnings.append("取不到公告日期，需人工填 date 与 date_basis")
    return t


def match_orgs(name: str, orgs: list[dict]) -> list[dict]:
    """把中标人名字匹配到 registry 主体。

    公告里用的是工商全名（「杭州宇树科技股份有限公司」），registry 里是常用名，
    所以做双向包含匹配。只给候选，不自动绑定 —— 认错主体比没认出来更糟。
    """
    if not name:
        return []
    hits = []
    for org in orgs:
        candidates = [org.get("zh") or "", org.get("en") or "", *(org.get("aliases") or [])]
        for cand in candidates:
            if not cand or len(cand) < 2:
                continue
            if cand in name or (len(cand) >= 4 and name in cand):
                hits.append({"id": org["id"], "zh": org.get("zh"), "matched": cand})
                break
    return hits
