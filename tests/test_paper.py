"""论文解析测试。不打网络，用合成 Atom 与文本。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ingest import paper  # noqa: E402

ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
 <entry>
  <id>http://arxiv.org/abs/2601.01234v1</id>
  <updated>2026-01-20T10:00:00Z</updated>
  <published>2026-01-15T08:30:00Z</published>
  <title>Whole-Body Humanoid Loco-Manipulation via Hierarchical Reinforcement Learning</title>
  <summary>We present a hierarchical policy for bipedal humanoid loco-manipulation.
  A high-level planner emits task-space targets while a low-level tracker produces joint
  torques. Policies are trained in Isaac Lab with domain randomization over 4096 parallel
  environments, then validated in MuJoCo for sim-to-sim consistency before deployment on a
  Unitree G1. We additionally collect teleoperation demonstrations with a VR controller and
  use behavior cloning to warm-start the planner.</summary>
  <author><name>Wei Zhang</name></author>
  <author><name>Li Chen</name></author>
  <link href="http://arxiv.org/abs/2601.01234v1" rel="alternate" type="text/html"/>
 </entry>
</feed>"""

ABS_HTML = """<html><head>
<meta name="citation_arxiv_id" content="2602.05678">
</head><body>
<h1 class="title">Title: Tactile-Guided Bimanual Manipulation with Diffusion Policy</h1>
<div class="authors"><a>Alice Wu</a><a>Bob Li</a></div>
<blockquote class="abstract">Abstract: We study bimanual manipulation using tactile
sensing and a diffusion policy trained on real-robot data collected via teleoperation.</blockquote>
<div class="dateline">Submitted 8 February 2026</div>
</body></html>"""


def check(name, got, want=None, cond=None):
    ok = cond if cond is not None else got == want
    print(f"  {'OK  ' if ok else 'FAIL'} {name}" + ("" if ok else f" — 得到 {got!r}，期望 {want!r}"))
    return bool(ok)


def main() -> int:
    ok = True
    kw = paper.load_keywords(ROOT)

    print("=== arXiv Atom ===")
    p = paper.parse_atom(ATOM)
    ok &= check("标题", p.title.startswith("Whole-Body Humanoid"), cond=p.title.startswith("Whole-Body Humanoid"))
    ok &= check("arXiv 编号", p.arxiv_id, "2601.01234")
    ok &= check("发表日期用 published 不是 updated", p.published, "2026-01-15")
    ok &= check("作者数", len(p.authors), 2)
    ok &= check("链接", p.url, "http://arxiv.org/abs/2601.01234v1")
    ok &= check("整体可用", p.ok, True)

    print("\n=== 轴抽取（同一篇同时命中多条轴）===")
    axes = paper.extract_axes(p.title + " " + p.abstract, kw)
    got = {f: sorted(x["value"] for x in v) for f, v in axes.items()}
    # 只命中 rl。标题里的「Whole-Body Humanoid」是在描述机器人，不是声称用了
    # whole-body control，所以 wbc 关键词故意保持 "whole-body control" 的精度不放宽。
    ok &= check("运控路线只命中 rl，不被 Whole-Body 误触", got.get("control_route"), ["rl"])
    ok &= check("模型形态", got.get("model_form"), ["hierarchical", "il"])
    ok &= check("仿真栈 = Isaac Lab + MuJoCo", got.get("sim_stack"), ["isaac-lab", "mujoco"])
    ok &= check("本体形态", got.get("embodiment_form"), ["humanoid-biped"])
    ok &= check("采集方式", got.get("data_acquisition"), ["sim-generated", "teleop"])
    snip = next(x["snippet"] for x in axes["sim_stack"] if x["value"] == "mujoco")
    ok &= check("候选带原文片段", "MuJoCo" in snip, cond="MuJoCo" in snip)

    print("\n=== abs 页面 HTML ===")
    p2 = paper.parse_abs_page(ABS_HTML)
    ok &= check("标题去掉 Title: 前缀", p2.title, "Tactile-Guided Bimanual Manipulation with Diffusion Policy")
    ok &= check("arXiv 编号", p2.arxiv_id, "2602.05678")
    ok &= check("日期", p2.published, "2026-02-08")
    axes2 = paper.extract_axes(p2.title + " " + p2.abstract, kw)
    got2 = {f: sorted(x["value"] for x in v) for f, v in axes2.items()}
    ok &= check("触觉模态", got2.get("data_modality"), ["tactile"])
    ok &= check("双臂形态", got2.get("embodiment_form"), ["dual-arm-stationary"])
    ok &= check("模仿学习", got2.get("model_form"), ["il"])

    print("\n=== 纯文本来料 ===")
    p3 = paper.load("Some Robot Paper\nWe train with PPO in Isaac Gym on a quadruped.")
    ok &= check("标题", p3.title, "Some Robot Paper")
    ok &= check("提示需手填链接", any("手填原文链接" in w for w in p3.warnings),
                cond=any("手填原文链接" in w for w in p3.warnings))

    print("\n=== 作者归属 vs 摘要提及（别把用的硬件当成作者）===")
    orgs_ap = [{"id": "unitree", "zh": "宇树科技", "en": "Unitree", "aliases": ["Unitree Robotics"]}]
    # 摘要里出现 Unitree G1 说的是用了谁家硬件；作者串里没有宇树，所以不能判为宇树的论文
    ok &= check("作者串不含宇树 → 无归属", paper.match_orgs(" ".join(p.authors), orgs_ap), [])
    ok &= check("摘要含宇树 → 仅作提及",
                [h["id"] for h in paper.match_orgs(p.abstract, orgs_ap)], ["unitree"])

    print("\n=== 主体匹配与短名防误命中 ===")
    orgs = [
        {"id": "unitree", "zh": "宇树科技", "en": "Unitree", "aliases": ["Unitree Robotics"]},
        {"id": "nvidia", "zh": "英伟达", "en": "NVIDIA", "aliases": []},
        {"id": "1x-technologies", "zh": "1X Technologies", "en": "1X Technologies", "aliases": ["1X"]},
    ]
    hits = [h["id"] for h in paper.match_orgs("deployment on a Unitree G1 with NVIDIA Jetson", orgs)]
    ok &= check("命中宇树与英伟达", sorted(hits), ["nvidia", "unitree"])
    # 「1X」只有两个字符，出现在 "1x speed" 这类文本里会误命中，必须被 min_len 挡掉
    hits2 = [h["id"] for h in paper.match_orgs("we replay the motion at 1x speed", orgs)]
    ok &= check("短名 1X 不误命中", hits2, [])

    print("\n通过" if ok else "\n有失败项")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
