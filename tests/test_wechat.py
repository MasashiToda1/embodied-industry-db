"""微信解析器测试。用合成 HTML，不打网络。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingest import wechat  # noqa: E402

# 仿真微信页面：元数据在 JS 变量里、正文 section 深嵌套、图片走 data-src
SAMPLE = """<!DOCTYPE html><html><head>
<meta property="og:title" content="某公司发布新一代人形机器人">
</head><body>
<h1 class="rich_media_title" id="activity-name">
   某公司发布新一代人形机器人
</h1>
<span class="rich_media_meta rich_media_meta_text" id="js_name">某公司机器人</span>
<em id="publish_time" class="rich_media_meta">2026年09月18日 09:30</em>
<script>
  var ct = "1789707000";
  var nickname = "某公司机器人";
  var user_name = "gh_abc123";
</script>
<div class="rich_media_content" id="js_content">
  <section><section><p>本次发布的机型采用自研关节模组。</p></section></section>
  <section><p>训练在 Isaac Lab 完成，评测使用 MuJoCo 做 sim2sim 对齐。</p></section>
  <h2>技术参数</h2>
  <section><section><span>全身自由度 29，含腰部 3 自由度。</span></section></section>
  <ul><li>整机重量 35kg</li><li>续航 2 小时</li></ul>
  <p>\u200b\u200b</p>
  <img data-src="https://mmbiz.qpic.cn/foo.jpg" src="data:image/gif;base64,R0lGOD">
</div></body></html>"""

BLOCKED = """<html><body><div class="weui-msg">
<h2 class="weui-msg__title">该内容已被发布者删除</h2></div></body></html>"""


def check(name: str, cond: bool, detail: str = "") -> bool:
    print(f"  {'OK  ' if cond else 'FAIL'} {name}{' — ' + detail if detail and not cond else ''}")
    return cond


def main() -> int:
    ok = True
    print("=== 正常文章 ===")
    art = wechat.parse(SAMPLE, "https://mp.weixin.qq.com/s/abc")

    ok &= check("标题", art.title == "某公司发布新一代人形机器人", art.title)
    ok &= check("公众号名", art.account == "某公司机器人", art.account)
    ok &= check("公众号 id", art.account_id == "gh_abc123", art.account_id)
    # ct=1789707000 → 2026-09-18 CST，JS 时间戳优先于可见文本
    ok &= check("发布日期取自 ct 时间戳", art.published == "2026-09-18", art.published)
    ok &= check("日期依据 stated", art.published_basis == "stated", art.published_basis)
    ok &= check("正文含自研关节", "自研关节模组" in art.body)
    ok &= check("正文含 Isaac Lab", "Isaac Lab" in art.body)
    ok &= check("标题层级转成 ##", "## 技术参数" in art.body)
    ok &= check("列表转成 -", "- 整机重量 35kg" in art.body)
    ok &= check("图片取 data-src", art.images == ["https://mmbiz.qpic.cn/foo.jpg"], str(art.images))
    ok &= check("零宽字符已清", "\u200b" not in art.body)
    ok &= check("嵌套 section 未重复", art.body.count("自研关节模组") == 1, str(art.body.count("自研关节模组")))
    ok &= check("整体可用", art.ok)

    print("\n=== 无 ct 变量，退化到可见日期 ===")
    no_ct = SAMPLE.replace('var ct = "1789707000";', "")
    art2 = wechat.parse(no_ct)
    ok &= check("从「2026年09月18日」解出", art2.published == "2026-09-18", art2.published)

    print("\n=== 已删除页面 ===")
    art3 = wechat.parse(BLOCKED)
    ok &= check("识别出提示页", any("已被发布者删除" in w for w in art3.warnings), str(art3.warnings))
    ok &= check("判定不可用", not art3.ok)

    print("\n=== 无日期时给出告警 ===")
    art4 = wechat.parse("<html><body><h1 id='activity-name'>标题</h1>"
                        "<div id='js_content'><p>" + "正文内容。" * 20 + "</p></div></body></html>")
    ok &= check("提示需人工填日期", any("取不到发布时间" in w for w in art4.warnings), str(art4.warnings))

    print("\n通过" if ok else "\n有失败项")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
