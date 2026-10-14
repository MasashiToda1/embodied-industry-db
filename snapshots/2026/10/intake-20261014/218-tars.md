# T1 Whole-Body Motion Tracking

[![Python](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![Isaac Lab](https://img.shields.io/badge/IsaacLab-2.3.2-silver)](https://isaac-sim.github.io/IsaacLab)
[![Isaac Sim](https://img.shields.io/badge/IsaacSim-5.x-silver.svg)](https://www.isaacsim.omniverse.nvidia.com/)
[![rsl_rl](https://img.shields.io/badge/rsl__rl-%E2%89%A55.5.0-orange)](https://github.com/leggedrobotics/rsl_rl)
[![License](https://img.shields.io/badge/license-MIT-yellow.svg)](https://opensource.org/license/mit)

**T1 Whole-Body Motion Tracking** is a humanoid whole-body motion-tracking framework built on
[BeyondMimic](https://beyondmimic.github.io/). It is a derivative of the open-source
[`HybridRobotics/whole_body_tracking`](https://github.com/HybridRobotics/whole_body_tracking) repository,
modified for the **T1** humanoid. It reproduces arbitrary reference motions at deployment quality and ships an
end-to-end, sim-to-real-ready pipeline:

- **Train** in Isaac Lab with the vanilla [`rsl_rl`](https://github.com/leggedrobotics/rsl_rl) backend (instead of
  the `isaaclab_rl.rsl_rl` fork shipped with Isaac Lab),
- **Export** a single self-contained ONNX policy (with the reference motion baked in and deployment metadata attached),
- **Validate** the exported policy in a standalone MuJoCo simulator that does **not** require Isaac Lab / Isaac Sim.

## Highlights

- **T1 humanoid task** — a complete `Tracking-Flat-T1-v0` training task: robot PD/action-scale config, 14-keypoint
  anchor-relative observations, DeepMimic-style rewards, and termination/domain-randomization terms.
- **Vanilla [`rsl_rl` (≥ 5.5.0)](https://github.com/leggedrobotics/rsl_rl) backend** — replaces the old
  MOE / history-observation fork used by `isaaclab_rl`, with per-model observation normalization, `obs_groups`
  actor/critic selection, and a thin `TensorDict`-based `VecEnv` wrapper.
- **Automatic ONNX export** — every save interval the runner exports a deterministic ONNX policy whose metadata
  (`joint_names`, PD gains, action scale, observation layout, body/anchor names, reference motion) is the *single source
  of truth* for downstream deployment.
- **Standalone MuJoCo Sim2Sim** — a dependency-light evaluator (`mujoco` + `onnxruntime`) that replays the reference
  motion and the exported policy, and renders keypoint-overlay videos (interactive viewer or offline mp4).

## Requirements

| Component | Version / Note |
|---|---|
| Python | 3.11 |
| Isaac Sim | 5.x |
| Isaac Lab | 2.3.2 (`isaaclab` 0.54.3) |
| [`rsl_rl`](https://github.com/leggedrobotics/rsl_rl) | **≥ 5.5.0** (vanilla, the only RL backend T1 uses) |
| `tensordict` | required by `rsl_rl` ≥ 5.x |
| PyTorch | 2.7 (CUDA) |
| GPU | NVIDIA GPU with a recent driver |

## Installation

### 1. Install Isaac Lab

Install Isaac Lab 2.3.2 and its conda environment following the
[official guide](https://isaac-sim.github.io/IsaacLab/main/source/setup/installation/index.html).

### 2. Install vanilla `rsl_rl` (≥ 5.5.0) — *critical*

Isaac Lab's bundled `isaaclab_rl[rsl-rl]` only installs `rsl-rl-lib==5.0.1`, whereas this repo needs the vanilla `rsl_rl` **≥ 5.5.0** API (`construct_algorithm`, `get_policy()`, `WandbLogWriter`, …). Install it explicitly:

```bash
# From PyPI
python -m pip install -U "rsl-rl-lib>=5.5.0"

# Or from your own clone (more robust offline / behind a proxy)
python -m pip install -e /path/to/rsl_rl --no-deps --no-build-isolation
```

> ⚠️ A stale 2.x `rsl_rl` editable install will shadow the 5.x one — both register the top-level `rsl_rl` package.

### 3. Install this repository

```bash
git clone https://github.com/TARS-AI/whole_body_tracking.git
cd whole_body_tracking
python -m pip install -e source/whole_body_tracking
```

> `--no-deps --no-build-isolation` is only for offline/proxied installs where you skip dependency resolution and build isolation; install `psutil`, `onnxscript`, `wandb>=0.19` by hand then.

### 4. Verify the installation

```bash
python - <<'PY'
import importlib.util, importlib.metadata as m
import rsl_rl

assert "whole_body_tracking" in importlib.util.find_spec("whole_body_tracking").origin
assert m.version("rsl-rl-lib") == "5.5.0"          # or >= 5.5.0

from rsl_rl.utils.wandb_log_writer import WandbLogWriter   # only exists in >= 5.x
from rsl_rl.env import VecEnv
from tensordict import TensorDict
print("OK")
PY
```

## Quick Start

### 1. Prepare a reference motion

Reference motions are `.npz` files storing retargeted joint positions/velocities and body
positions/quaternions/velocities.

- Use a local `.npz` directly with `--motion_file`.

> The body/joint order inside the `.npz` **must** match `robot.body_names` / `robot.joint_names`. If the ordering is
> inconsistent, tracking errors explode and every episode terminates after one step. See
> `data/APT_27dof_train_example.npz` for an example.

### 2. Replay a reference motion (visual check)

Replay a local `.npz` motion on the T1 robot in Isaac Sim for a quick visual check, or record it
headless to an mp4:

```bash
# Interactive viewer (needs a display)
python scripts/replay_npz.py --motion_file data/APT_27dof_train_example.npz

# Headless, record the replay to an mp4
python scripts/replay_npz.py --motion_file data/APT_27dof_train_example.npz \
    --headless --video --video_path data/tmp.mp4 --video_fps 50
```

`--video` enables the offscreen camera sensor and records exactly one full motion pass before
exiting; `--video_path` / `--video_fps` set the output path and frame rate.

### 3. Train

```bash
# Local motion file
python scripts/rsl_rl/train.py --task=Tracking-Flat-T1-v0 \
    --motion_file /path/to/motion.npz \
    --headless --logger wandb --log_project_name my_project --run_name my_run

# Or via the WandB motion registry
python scripts/rsl_rl/train.py --task=Tracking-Flat-T1-v0 \
    --registry_name {org}-org/wandb-registry-motions/my_motion \
    --headless --logger wandb --log_project_name my_project
```

Key flags: `--num_envs`, `--max_iterations`, `--seed`, `--experiment_name`, `--resume`/`--load_run`/`--checkpoint`.
With `--logger wandb`, each save also exports the ONNX policy next to the `.pt` checkpoint under
`logs/rsl_rl/t1_flat/{run}/`.

### 4. Evaluate / export ONNX

```bash
# Play from a WandB run
python scripts/rsl_rl/play.py --task=Tracking-Flat-T1-v0 --num_envs=2 --wandb_path={org}/{project}/{run_id}

# Play a local checkpoint with a local motion
python scripts/rsl_rl/play.py --task=Tracking-Flat-T1-v0 \
    --load_path logs/rsl_rl/t1_flat/{run}/model_xxx.pt --motion_file /path/to/motion.npz

# Export the ONNX only
python scripts/rsl_rl/play.py --task=Tracking-Flat-T1-v0 --load_path ... --export_only
```

### 5. Sim2Sim (MuJoCo, standalone)

`sim2sim.py` has two invocation styles:

**Original per-file usage** — point at each file explicitly:

```bash
python sim2sim/t-deploy_mujoco/sim2sim.py \
    --motion_file /path/to/motion.npz \
    --onnx_load_path /path/to/policy.onnx \
    --xml_path /path/to/t1.xml \
    --env_path logs/rsl_rl/t1_flat/{run}/params/env.yaml \
    --visualize           # or --record_video / --play_reference
```

**Bundle usage** — point at a deployment bundle directory (built by
`scripts/build_bundle.py`, containing `model_*.onnx`, `env.yaml`,
`configs/mjcf/<robot>.xml` and the motion `*.npz`) and it auto-discovers the files:

```bash
# interactive viewer (needs a display)
python sim2sim/t-deploy_mujoco/sim2sim.py logs/upload/<experiment> --visualize

# offline mp4 per motion (headless, MuJoCo EGL backend)
python sim2sim/t-deploy_mujoco/sim2sim.py logs/upload/<experiment> --record_video

# replay the reference motion only (no policy)
python sim2sim/t-deploy_mujoco/sim2sim.py logs/upload/<experiment> --record_video --play_reference
```

This requires only `numpy`, `torch`, `onnxruntime`, `mujoco`, `scipy` and `tqdm` (plus
`imageio` for `--record_video`) — no Isaac Lab / Isaac Sim. The motion `*.npz` must carry
`body_names`/`joint_names` metadata (30 bodies); the legacy APT export (31 bodies, no
names) is not supported. See [`sim2sim/t-deploy_mujoco/`](sim2sim/t-deploy_mujoco/) for
details.

> **Building a bundle with `build_bundle.py`:** edit the four hardcoded values at the top of
> [`scripts/build_bundle.py`](scripts/build_bundle.py) first —
> `feature`, `data1`, `data2` and `upload_motion_file` — the committed defaults point at a stale
> run and a non-existent `data/motion.npz`; the script also depends on `lxml`.

## Project Structure

```
scripts/rsl_rl/                training / evaluation / export entry points
scripts/replay_npz.py          replay a local motion (interactive or headless mp4)
scripts/build_bundle.py         build a deployment bundle under logs/upload/
scripts/train_t1.sh            convenience launcher for T1 training
source/whole_body_tracking/whole_body_tracking/
├── robots/t1.py               T1 PD gains / armature / action scale
├── tasks/tracking/
│   ├── tracking_env_cfg.py    robot-agnostic MDP base config
│   ├── mdp/                   commands / observations / rewards / events / terminations
│   └── config/t1/             T1 env config + PPO config + gym registration
└── utils/                     runner / vec-env wrapper / ONNX exporter
sim2sim/t-deploy_mujoco/       MuJoCo sim2sim evaluation tooling
```

## Citation

This work builds on **BeyondMimic**. Please cite it if you use this code in your research:

```bibtex
@misc{liao2025beyondmimic,
  title         = {BeyondMimic: From Motion Tracking to Versatile Humanoid Control via Guided Diffusion},
  author        = {Qiayuan Liao and Takara E. Truong and Xiaoyu Huang and Yuman Gao and Guy Tevet and Koushil Sreenath and C. Karen Liu},
  year          = {2025},
  eprint        = {2508.08241},
  archivePrefix = {arXiv},
  url           = {https://arxiv.org/abs/2508.08241},
}
```

## Acknowledgements

- [BeyondMimic](https://beyondmimic.github.io/) (HybridRobotics) — the tracking framework this repo is based on.
- [Isaac Lab](https://isaac-sim.github.io/IsaacLab) and [Isaac Sim](https://www.isaacsim.omniverse.nvidia.com/).
- [rsl_rl](https://github.com/leggedrobotics/rsl_rl) (ETH Zurich / NVIDIA) — RL backend.

## License & Third-Party Notices

This project is licensed under the [MIT License](LICENSE), consistent with the upstream
[BeyondMimic](https://github.com/HybridRobotics/whole_body_tracking) repository it derives from.

This codebase also includes components derived from the following open-source projects, whose original
copyright and license headers are retained in their respective source files:

| Component | License | Copyright / Origin |
|---|---|---|
| [BeyondMimic](https://github.com/HybridRobotics/whole_body_tracking) | MIT | HybridRobotics |
| [Isaac Lab](https://isaac-sim.github.io/IsaacLab) | BSD-3-Clause | Isaac Lab Project Developers |
| [rsl_rl](https://github.com/leggedrobotics/rsl_rl) | BSD-3-Clause | ETH Zürich / NVIDIA Corporation |