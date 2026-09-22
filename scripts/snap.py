#!/usr/bin/env python3
"""抓一个公开页面存成快照，打印落盘路径。批量入库时给 agent 用。

    python3 scripts/snap.py URL --date 2026-03-15 --tag unitree-h2

复用 intake.snapshot 的落盘逻辑（文件名只留 ASCII，同内容复用）。
httpx 拿不到正文（403 / 反爬 / 纯前端渲染）时退到本机 Chrome 把渲染后的 DOM 存下来。
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def via_chrome(url: str) -> str:
    out = subprocess.run(
        [CHROME, "--headless=new", "--disable-gpu", "--no-sandbox", "--virtual-time-budget=8000",
         "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/128 Safari/537.36",
         "--dump-dom", url],
        capture_output=True, text=True, timeout=90)
    return out.stdout


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--date", required=True, help="事件日期 YYYY-MM-DD 或 YYYY-MM，决定落在哪个月目录")
    ap.add_argument("--tag", required=True, help="ASCII 标识，一般是 <org>-<主题>")
    ap.add_argument("--browser", action="store_true", help="直接用 Chrome 渲染，不先试 httpx")
    args = ap.parse_args()

    from ingest import wechat

    html = ""
    if not args.browser:
        try:
            import httpx
            r = httpx.get(args.url, timeout=30, follow_redirects=True,
                          headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/128 Safari/537.36",
                                   "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"})
            if r.status_code == 200 and len(r.text) > 2000:
                html = r.text
            else:
                print(f"httpx {r.status_code} / {len(r.text)} 字节，退到 Chrome", file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            print(f"httpx 失败：{e}，退到 Chrome", file=sys.stderr)
    if not html:
        html = via_chrome(args.url)
    if len(html) < 500:
        print("页面内容过短，未存快照", file=sys.stderr)
        return 1

    host = re.sub(r"^www\.", "", re.sub(r"^https?://", "", args.url).split("/")[0]).split(".")[0]
    art = wechat.Article(title=args.tag, html=html, url=args.url, account_id=args.tag)
    path = wechat.save_snapshot(ROOT, art, args.date, prefix=host[:12])
    # 顺手给个正文长度，agent 好判断抓到的是不是提示页
    body = re.sub(r"<[^>]+>", " ", html)
    body = re.sub(r"\s+", " ", body)
    print(path)
    print(f"正文约 {len(body)} 字符", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
