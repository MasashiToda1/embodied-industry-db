"""issue 表单 → 事件 的转换测试。不打网络。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import intake  # noqa: E402

# GitHub Issue Forms 渲染出来就是这个形状
BODY_FIRST_PARTY = """### 主体

具深科技

### 什么时候发生

2026-09-10

### 什么事

硬件群控模块按台买断，软件授权首年随附、次年起按台年付。

### 怎么知道的

vendor-inquiry — 以买方身份向厂商询价

### 公开链接

_No response_

### 事件类型

pricing — 公开价格

### 金额

1000 元/台

### 买方或对方

_No response_

### 补充

软件版限 6 台，对方称局域网会掉线。
"""

BODY_FUZZY_DATE = """### 主体

宇树科技

### 什么时候发生

2025 年下半年

### 什么事

舞蹈款整机公开标价下调。

### 怎么知道的

field-observation — 展会、现场、门店看到

### 金额

不确定

### 事件类型

pricing — 公开价格
"""

BODY_UNKNOWN_ORG = """### 主体

某不在库里的公司

### 什么时候发生

2026-03

### 什么事

发布了新机型。

### 怎么知道的

interview — 与从业者聊到
"""


def check(name, got, want=None, cond=None):
    ok = cond if cond is not None else got == want
    print(f"  {'OK  ' if ok else 'FAIL'} {name}" + ("" if ok else f" — 得到 {got!r}，期望 {want!r}"))
    return bool(ok)


def main() -> int:
    ok = True

    print("=== 一手询价（具深已在 registry）===")
    f = intake.parse_body(BODY_FIRST_PARTY)
    ok &= check("解析到主体", f["org"], "具深科技")
    ok &= check("_No response_ 视为空", f["url"], "")
    ev, missing = intake.build(f, "12")
    ok &= check("主体对上 jushen", ev["orgs"], [{"id": "jushen", "role": "subject"}])
    ok &= check("事件类型取破折号前的 id", ev["type"], "pricing")
    ok &= check("来源等级", ev["evidence"][0]["tier"], "first-party")
    ok &= check("渠道", ev["evidence"][0]["method"], "vendor-inquiry")
    ok &= check("一手来源无 url 字段", "url" in ev["evidence"][0], False)
    ok &= check("金额 1000 元不放大", ev["amount"], {"value": 1000.0, "currency": "CNY"})
    ok &= check("日期精度", ev["date_precision"], "day")
    ok &= check("补充信息提示需人工对轴",
                any("补充信息" in m for m in missing), cond=any("补充信息" in m for m in missing))

    print("\n=== 模糊日期必须留痕 ===")
    f2 = intake.parse_body(BODY_FUZZY_DATE)
    ev2, missing2 = intake.build(f2, "13")
    ok &= check("下半年钉到区间末月", ev2["date"], "2025-12")
    ok &= check("标成 estimated", ev2.get("date_basis"), "estimated")
    ok &= check("保留原话", ev2.get("date_as_stated"), "2025 年下半年")
    ok &= check("「不确定」不产生金额", "amount" in ev2, False)
    ok &= check("提示金额被留空",
                any("单位不明确" in m for m in missing2), cond=any("单位不明确" in m for m in missing2))

    print("\n=== 主体不在库里要阻塞 ===")
    f3 = intake.parse_body(BODY_UNKNOWN_ORG)
    ev3, missing3 = intake.build(f3, "14")
    ok &= check("主体填 TODO", ev3["orgs"][0]["id"], "TODO")
    ok &= check("给出建条目提示",
                any("没有对应条目" in m for m in missing3), cond=any("没有对应条目" in m for m in missing3))

    print("\n=== 日期解析单元 ===")
    for raw, want in [
        ("2026-09-10", ("2026-09-10", "day", "stated")),
        ("2026年9月10日", ("2026-09-10", "day", "stated")),
        ("2026-09", ("2026-09", "month", "stated")),
        ("2026-Q3", ("2026-Q3", "quarter", "stated")),
        ("2026", ("2026", "year", "stated")),
        ("2025 年上半年", ("2025-06", "month", "estimated")),
    ]:
        d, p, b, _ = intake.parse_when(raw)
        ok &= check(f"parse_when({raw})", (d, p, b), want)

    print("\n=== 金额解析单元（量级是重点）===")
    for raw, want in [
        ("1000 元/台", {"value": 1000.0, "currency": "CNY"}),
        ("480 万元", {"value": 4_800_000.0, "currency": "CNY"}),
        ("1.2 亿元", {"value": 120_000_000.0, "currency": "CNY"}),
        ("30000 美元", {"value": 30000.0, "currency": "USD"}),
        ("500 万美元", {"value": 5_000_000.0, "currency": "USD"}),
        ("200 万欧元", {"value": 2_000_000.0, "currency": "EUR"}),
        ("不确定", None),
        ("", None),
    ]:
        ok &= check(f"parse_amount({raw!r})", intake.parse_amount(raw), want)

    print("\n通过" if ok else "\n有失败项")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
