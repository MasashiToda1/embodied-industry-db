"""招投标解析测试。重点是金额——差一个量级就是一万倍脏数据。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingest import tender  # noqa: E402

NOTICE_HTML = """<html><body>
<h1>某文旅集团机器人表演服务采购项目中标公告</h1>
<table>
<tr><td>项目名称</td><td>某文旅集团机器人表演服务采购项目</td></tr>
<tr><td>项目编号</td><td>WL-2026-0211-003</td></tr>
<tr><td>采购人</td><td>某文旅集团有限公司</td></tr>
<tr><td>采购代理机构</td><td>某招标咨询有限公司</td></tr>
<tr><td>中标供应商</td><td>杭州宇树科技股份有限公司</td></tr>
<tr><td>中标金额</td><td>480.00万元（人民币）</td></tr>
<tr><td>公告日期</td><td>2026年02月11日</td></tr>
</table>
<p>联系电话：0571-88888888</p>
</body></html>"""

NOTICE_TEXT_YUAN = """机器人租赁服务项目成交公告
项目编号：JQ-2026-118
采购单位：某市文化旅游发展中心
成交供应商：深圳市具深科技有限公司
成交金额：1234567.89元
发布日期：2026-03-05
"""

NOTICE_CN_UPPER = """人形机器人本体采购中标公示
招标人：某职业技术学院
中标单位：上海智元新创技术有限公司
中标金额：人民币壹佰贰拾叁万肆仟元整
公示日期：2026/4/9
"""

NOTICE_NO_AMOUNT = """某项目资格预审公告
项目名称：具身智能训练场建设项目
采购人：某区科技局
公告日期：2026年5月
"""


def check(name: str, got, want=None, cond=None) -> bool:
    ok = cond if cond is not None else got == want
    print(f"  {'OK  ' if ok else 'FAIL'} {name}" + ("" if ok else f" — 得到 {got!r}，期望 {want!r}"))
    return bool(ok)


def main() -> int:
    ok = True

    print("=== 万元公告（HTML 表格）===")
    t = tender.parse(NOTICE_HTML)
    ok &= check("项目名称", t.project, "某文旅集团机器人表演服务采购项目")
    ok &= check("项目编号", t.project_no, "WL-2026-0211-003")
    ok &= check("采购人", t.buyer, "某文旅集团有限公司")
    ok &= check("中标人", t.winner, "杭州宇树科技股份有限公司")
    # 480 万元必须是 4_800_000 而不是 480
    ok &= check("金额已按万元换算", t.amount_value, 4_800_000.0)
    ok &= check("币种", t.amount_currency, "CNY")
    ok &= check("日期", t.date, "2026-02-11")
    ok &= check("日期精度", t.date_precision, "day")
    ok &= check("无金额告警", t.warnings, cond=not any("金额" in w for w in t.warnings))

    print("\n=== 元为单位、带千分位 ===")
    t2 = tender.parse(NOTICE_TEXT_YUAN)
    ok &= check("金额原样不放大", t2.amount_value, 1_234_567.89)
    ok &= check("中标人", t2.winner, "深圳市具深科技有限公司")
    ok &= check("日期", t2.date, "2026-03-05")

    print("\n=== 中文大写金额 ===")
    t3 = tender.parse(NOTICE_CN_UPPER)
    ok &= check("壹佰贰拾叁万肆仟 = 1234000", t3.amount_value, 1_234_000.0)
    ok &= check("日期", t3.date, "2026-04-09")

    print("\n=== 无金额公告 ===")
    t4 = tender.parse(NOTICE_NO_AMOUNT)
    ok &= check("金额留空而非填 0", t4.amount_value, None)
    ok &= check("给出金额告警", t4.warnings, cond=any("金额" in w for w in t4.warnings))
    ok &= check("只到月的日期", t4.date, "2026-05")
    ok &= check("精度为 month", t4.date_precision, "month")

    print("\n=== 中文数字单元 ===")
    for raw, want in [("壹佰贰拾叁万肆仟", 1_234_000.0), ("贰拾万", 200_000.0),
                      ("壹亿", 100_000_000.0), ("伍仟", 5000.0), ("叁佰万", 3_000_000.0)]:
        ok &= check(f"cn_number({raw})", tender.cn_number(raw), want)
    ok &= check("看不懂返回 None", tender.cn_number("abc"), None)

    print("\n=== 主体匹配（工商全名 → registry 常用名）===")
    orgs = [
        {"id": "unitree", "zh": "宇树科技", "en": "Unitree", "aliases": ["杭州宇树科技股份有限公司"]},
        {"id": "agibot", "zh": "智元机器人", "en": "AgiBot", "aliases": ["上海智元新创技术有限公司", "智元"]},
        {"id": "jushen", "zh": "具深科技", "en": "Jushen", "aliases": ["机时租", "具深"]},
    ]
    ok &= check("宇树全名命中", [h["id"] for h in tender.match_orgs("杭州宇树科技股份有限公司", orgs)], ["unitree"])
    ok &= check("智元全名命中", [h["id"] for h in tender.match_orgs("上海智元新创技术有限公司", orgs)], ["agibot"])
    ok &= check("具深全名命中", [h["id"] for h in tender.match_orgs("深圳市具深科技有限公司", orgs)], ["jushen"])
    ok &= check("陌生公司无命中", tender.match_orgs("某不相关建筑工程有限公司", orgs), [])

    print("\n通过" if ok else "\n有失败项")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
