#!/usr/bin/env python3
"""给主体补 GitHub 组织账号。

GitHub 比 HF 宽：除模型外还有 SDK、部署工具、仿真环境、URDF，
对技术轴的信息量更大。比如 LightwheelAI/usd2mjcf 这个仓直接说明
光轮在用 MuJoCo —— 这种信号 HF 上看不出来。

匹配规则与 resolve_hf 共用：**以组织显示名为准，不看 slug**。
那条规则是踩出来的，见 resolve_hf.py 里的注释。

⚠️ 未认证的 GitHub API 每小时只有 60 次，176 家根本跑不完。
   本脚本会读 `gh auth token`，有 token 时额度是 5000/小时。

用法：
    python3 scripts/resolve_github.py            # 只看结果
    python3 scripts/resolve_github.py --write    # 确认后写入
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

import httpx
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from resolve_hf import MULTI_ORG, canon, name_matches  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.github.com"


def token() -> str:
    try:
        return subprocess.run(["gh", "auth", "token"], capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def headers(tok: str) -> dict:
    h = {"User-Agent": "embodied-industry-db", "Accept": "application/vnd.github+json"}
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


def search_orgs(q: str, h: dict) -> list[dict]:
    try:
        r = httpx.get(f"{API}/search/users", params={"q": f"{q} type:org", "per_page": 5},
                      timeout=20, headers=h)
        if r.status_code != 200:
            return []
        return r.json().get("items", []) or []
    except Exception:  # noqa: BLE001
        return []


def org_detail(login: str, h: dict) -> dict:
    try:
        r = httpx.get(f"{API}/orgs/{login}", timeout=20, headers=h)
        return r.json() if r.status_code == 200 else {}
    except Exception:  # noqa: BLE001
        return {}


def judge(login: str, display: str, names: list[str]) -> tuple[bool, str]:
    """以显示名为准，没有显示名才退到 login。理由见 resolve_hf.judge。"""
    target = canon(display) if display else canon(login)
    if not target:
        return False, "没有可比对的名字"
    ok, why = name_matches(target, names)
    return (True, why) if ok else (False, f"名字对不上（GitHub: {display or login}）")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    tok = token()
    h = headers(tok)
    print(f"GitHub API {'已认证（5000/小时）' if tok else '⚠️ 未认证（60/小时，跑不完）'}\n")

    paths = sorted((ROOT / "registry/orgs").glob("*.yaml"))
    if args.limit:
        paths = paths[: args.limit]

    matched, unsure, nothing = [], [], []
    for p in paths:
        doc = yaml.safe_load(p.read_text()) or {}
        if (doc.get("accounts") or {}).get("github"):
            continue
        names = doc.get("names") or {}
        zh = names.get("zh") or doc["id"]
        if zh in MULTI_ORG:
            unsure.append((zh, "GitHub 上有多个组织，留人工填"))
            continue
        queries = [x for x in (names.get("en"), *(names.get("aliases") or [])) if x]
        if not queries:
            continue

        found = None
        for q in queries[:2]:
            for item in search_orgs(q, h)[:4]:
                login = item.get("login", "")
                detail = org_detail(login, h)
                ok, why = judge(login, detail.get("name") or "", queries)
                time.sleep(0.1)
                if ok:
                    found = (login, why, detail.get("public_repos", 0))
                    break
            time.sleep(0.3)
            if found:
                break

        if not found:
            nothing.append(zh)
            continue
        login, why, repos = found
        if repos == 0:
            unsure.append((zh, f"{login} 组织存在但没有公开仓，先不填"))
            continue
        matched.append((p, doc, login, why, repos))

    print(f"=== 匹配上且有公开仓 {len(matched)} 家 ===")
    for _, doc, login, why, repos in matched:
        print(f"  {(doc.get('names') or {}).get('zh'):<18} → {login:<24} {repos} 仓  {why}")
    if unsure:
        print(f"\n=== 存疑 {len(unsure)} 家（未填）===")
        for zh, why in unsure:
            print(f"  {zh}  {why}")
    print(f"\n=== 没找到 {len(nothing)} 家 ===")
    print("  " + "、".join(nothing[:40]) + (" …" if len(nothing) > 40 else ""))

    if args.write:
        for p, doc, login, _, _ in matched:
            doc.setdefault("accounts", {})["github"] = login
            p.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False),
                         encoding="utf-8")
        print(f"\n已写入 {len(matched)} 家。跑一次 make lint。")
    else:
        print("\n（未写盘。确认无误后加 --write）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
