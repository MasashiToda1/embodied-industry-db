#!/usr/bin/env python3
"""给主体补 Hugging Face 组织账号。

填了 accounts.huggingface，watch.py 才能自动发现这家的新模型和数据集。
HF 是精度最高的源：许可、模态、标签都是结构化字段，发布方就是主体本身。

**宁可不填也不能填错**：填错了盯梢会盯着别家公司，产出的候选比没有更糟。
所以只在 HF 组织的 fullname 与本库记的名字能对上时才写，其余一律列为待定。

用法：
    python3 scripts/resolve_hf.py              # 只看结果
    python3 scripts/resolve_hf.py --write      # 确认后写入
"""

from __future__ import annotations

import argparse
import re
import sys
import time
import unicodedata
from pathlib import Path

import httpx
import yaml

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "Mozilla/5.0 (compatible; embodied-industry-db)"}


MIN_STEM = 6      # 短于这个长度不做包含匹配，四五个字母乱撞的概率太高

# 这些主体在 HF 上有一堆组织（云、模型、研究各一个），
# 自动挑一个必然挑错，留给人工填。
MULTI_ORG = {"阿里巴巴", "百度智能云", "腾讯机器人实验室", "华为 CloudRobo",
             "字节跳动 Seed", "小米机器人", "蚂蚁灵波", "英伟达", "Meta FAIR Robotics",
             "Google DeepMind Robotics", "微软研究院机器人团队", "地平线"}


def canon(s: str) -> str:
    """归一化到只剩小写字母数字，方便比对。

    「Unitree Robotics」和「unitreerobotics」要能对上。
    Robotics / Technology 这类后缀不携带识别信息，可以剥，
    但**剥完短于 MIN_STEM 就不剥** —— BrainCo 剥掉 co 只剩 brain，
    会去撞 braincode（一个 MIT 的脑机项目），那就成了盯错公司。
    """
    s = unicodedata.normalize("NFKC", s or "").lower()
    s = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", s)
    for suffix in ("robotics", "robot", "technologies", "technology", "tech",
                   "intelligence", "inc", "ltd", "official"):
        if s.endswith(suffix) and len(s) - len(suffix) >= MIN_STEM:
            s = s[: -len(suffix)]
            break
    return s


def search_orgs(q: str) -> list[dict]:
    try:
        r = httpx.get("https://huggingface.co/api/quicksearch",
                      params={"q": q, "type": "org"}, timeout=15, headers=UA)
        if r.status_code != 200:
            return []
        return r.json().get("orgs", []) or []
    except Exception:  # noqa: BLE001
        return []


def org_fullname(slug: str) -> str:
    try:
        r = httpx.get(f"https://huggingface.co/api/organizations/{slug}/overview",
                      timeout=15, headers=UA)
        return r.json().get("fullname", "") if r.status_code == 200 else ""
    except Exception:  # noqa: BLE001
        return ""


def has_content(slug: str) -> int:
    """这个组织到底发过东西没有。空壳组织填了也没用。"""
    n = 0
    for kind in ("models", "datasets"):
        try:
            r = httpx.get(f"https://huggingface.co/api/{kind}",
                          params={"author": slug, "limit": 5}, timeout=15, headers=UA)
            if r.status_code == 200:
                n += len(r.json())
        except Exception:  # noqa: BLE001
            pass
    return n


def judge(org: dict, names: list[str]) -> tuple[bool, str]:
    """名字能不能对上。对不上就不填。

    **以全名为准，slug 只在没有全名时兜底。** slug 容易前缀撞车：
    BrainCo 的 brainco 正好是 braincode 的前缀，而那个组织其实叫
    「Programming in the brain project - MIT」，跟强脑毫无关系。
    全名对不上就说明认错了，不管 slug 多像。
    """
    slug = org.get("name") or org.get("id") or ""
    full = org.get("fullname") or ""
    target = canon(full) if full else canon(slug)
    if not target:
        return False, "HF 组织没有可比对的名字"

    ok, why = name_matches(target, names)
    return (True, why) if ok else (False, f"名字对不上（HF: {full or slug}）")


# 前缀匹配后允许出现的剩余部分。机构名 = 公司名 + 这些后缀的组合：
# AgiBot World / Astribot Developers / Fourier Co Ltd / PAL Robotics SL / Harmonic Drive LLC
BENIGN_SUFFIXES = (
    "robotics", "robots", "robot", "developers", "developer", "dev", "labs", "lab",
    "research", "official", "hq", "inc", "llc", "ltd", "sl", "se", "ag", "gmbh", "co",
    "corp", "technologies", "technology", "tech", "ai", "group", "world", "open", "oss",
    "org", "team", "community", "embodied", "intelligence", "git", "opensource",
    "machinelearning", "ml",      # Toyota Research Institute Machine Learning（TRI-ML）
)


def _benign_remainder(rest: str) -> bool:
    """剩余部分能不能全部由公司后缀拼出来。CJK 全放行（psibot灵初智能）。"""
    if not rest:
        return True
    if re.fullmatch(r"[\u4e00-\u9fff]+", rest):
        return True
    changed = True
    while rest and changed:
        changed = False
        for s in BENIGN_SUFFIXES:
            if rest.startswith(s):
                rest = rest[len(s):]
                changed = True
                break
    return rest == ""


def name_matches(target: str, names: list[str]) -> tuple[bool, str]:
    """比对归一化后的名字。resolve_github 也用这个。

    包含匹配要求是**前缀**而不是任意子串：机构显示名通常以公司名开头
    （AgiBot World、Astribot Developers、Cloudminds Robot Inc）。
    任意子串会出事——「Booster Robotics」剥掉后缀剩 booster，
    嵌进「Rock 'Em Robotics Booster Club」（一个中学社团）就匹上了。

    前缀之后的**剩余部分必须是公司后缀**。否则 jushen 会匹上 jushenzhidao
    （具身智道，另一家）、magiclab 匹上 magiclabnyc（纽约的）、
    original 匹上 originalvoices、pudu 匹上 puduroboticstürkiye（经销商）。
    这条同时堵住了 Generalist-AI-for-Healthcare 这类「X for Y」衍生组织。
    """
    for n in names:
        cn = canon(n)
        if len(cn) < 3:
            continue
        if cn == target:
            return True, f"精确匹配 {n}"
        if len(cn) >= MIN_STEM and target.startswith(cn) and _benign_remainder(target[len(cn):]):
            return True, f"前缀匹配 {n} ↔ {target}"
    return False, "名字对不上"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 家，调试用")
    args = ap.parse_args()

    paths = sorted((ROOT / "registry/orgs").glob("*.yaml"))
    if args.limit:
        paths = paths[: args.limit]

    matched: list[tuple[Path, dict, str, str, int]] = []
    unsure: list[tuple[str, str]] = []
    nothing: list[str] = []

    for p in paths:
        doc = yaml.safe_load(p.read_text()) or {}
        if ((doc.get("accounts") or {}).get("huggingface")):
            continue
        names = doc.get("names") or {}
        if names.get("zh") in MULTI_ORG:
            unsure.append((f"{names.get('zh')}（{doc['id']}）",
                           "HF 上有多个组织，自动挑必然挑错，留人工填"))
            continue
        queries = [x for x in (names.get("en"), names.get("zh"), *(names.get("aliases") or [])) if x]
        if not queries:
            continue

        found = None
        for q in queries[:2]:          # 英文名和中文名各试一次就够
            for org in search_orgs(q)[:4]:
                ok, why = judge(org, queries)
                if ok:
                    slug = org.get("name") or org.get("id")
                    found = (slug, why)
                    break
            time.sleep(0.15)
            if found:
                break

        label = f"{names.get('zh')}（{doc['id']}）"
        if not found:
            nothing.append(label)
            continue
        slug, why = found
        n = has_content(slug)
        time.sleep(0.15)
        if n == 0:
            unsure.append((label, f"{slug} 组织存在但没发过东西，先不填"))
            continue
        matched.append((p, doc, slug, why, n))

    print(f"=== 匹配上且有产出 {len(matched)} 家 ===")
    for _, doc, slug, why, n in matched:
        print(f"  {(doc.get('names') or {}).get('zh'):<16} → {slug:<24} {n} 个产出  {why}")
    if unsure:
        print(f"\n=== 存疑 {len(unsure)} 家（未填）===")
        for label, why in unsure:
            print(f"  {label}  {why}")
    print(f"\n=== 没找到 {len(nothing)} 家 ===")
    print("  " + "、".join(nothing[:40]) + (" …" if len(nothing) > 40 else ""))

    if args.write:
        for p, doc, slug, _, _ in matched:
            doc.setdefault("accounts", {})["huggingface"] = slug
            p.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False),
                         encoding="utf-8")
        print(f"\n已写入 {len(matched)} 家。跑一次 make lint。")
    else:
        print("\n（未写盘。确认无误后加 --write）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
