# dexevt-mxlab

基于 [MotrixLab](https://github.com/Motphys/MotrixLab) 的 Dex-EVT 人形机器人强化学习项目，包含**平地行走**与**全身动作跟踪（Whole-Body Tracking，WBT）**任务。

仓库提供机器人模型与资产、任务实现和 FastSAC 训练配置，同时展示如何通过 MotrixLab 的插件机制接入自定义机器人与环境。

原始项目与机器人资产来自 [Open-X-Humanoid/xMimic](https://github.com/Open-X-Humanoid/xMimic)，本项目基于其内容适配 MotrixLab，感谢原作者的开源贡献。

## 成果展示

| 平地行走 · Flat walking | 全身动作跟踪 · WBT dance |
| --- | --- |
| ![平地行走策略回放](docs/media/dexevt-walk-flat.gif) | ![WBT dance 策略回放](docs/media/dexevt-wbt-dance.gif) |
| [观看 MP4 · 12 秒](docs/media/dexevt-walk-flat.mp4) | [观看 MP4 · 16 秒](docs/media/dexevt-wbt-dance.mp4) |
| 10,000 训练迭代 · 20.48M 环境步 | 20,000 训练迭代 · 40.96M 环境步 |
| 训练耗时 250.7 秒 | 训练耗时 592.3 秒 |

训练使用 RTX 5090、Ryzen 9 9950X 和 2,048 个并行环境。视频为最终 checkpoint 的单环境回放。

### 训练曲线

![TensorBoard 训练回报曲线](docs/media/training-mean_return.svg)

![TensorBoard 训练 episode 长度曲线](docs/media/training-mean_ep_len.svg)

曲线记录各任务 seed=1 训练时的平均 episode 回报和长度，横轴为环境步数。视频录制与绘图命令见[素材说明](docs/media/README.md)。

## 快速开始

### 安装

环境要求：**Linux x86_64、Python 3.10 / 3.11、支持 CUDA 12.8 的 NVIDIA 驱动**。

安装 [uv](https://docs.astral.sh/uv/) 后，在仓库根目录执行：

```bash
uv sync --locked
source .venv/bin/activate
```

默认使用 Python 3.10；使用 Python 3.11 时执行 `uv sync --locked --python 3.11`。项目依赖 MotrixLab 0.4.0，PyTorch 使用 CUDA 12.8 构建。

以下命令均在仓库根目录、已激活的环境中运行。

### 查看机器人与环境

```bash
mxlab view robot=dexevt
mxlab view env=dexevt-walk-flat
mxlab view env=dexevt-wbt-dance
```

`view env=...` 使用随机动作预览环境；训练策略使用下文的 `play` 命令回放。

### 训练

| 任务 | 环境 ID | 训练配置 |
| --- | --- | --- |
| 平地行走 | `dexevt-walk-flat` | `dexevt-walk-flat/motrix.fastsac` |
| 舞蹈动作跟踪 | `dexevt-wbt-dance` | `dexevt-wbt-dance/motrix.fastsac` |

```bash
# 平地行走
mxlab train task=dexevt-walk-flat/motrix.fastsac

# 舞蹈动作跟踪
mxlab train task=dexevt-wbt-dance/motrix.fastsac
```

使用 `key=value` 覆写参数，例如调整并行环境数量：

```bash
mxlab train task=dexevt-walk-flat/motrix.fastsac num_envs=256
```

checkpoint、配置和 TensorBoard 日志保存在 `runs/` 下。查看训练曲线：

```bash
tensorboard --logdir runs
```

需要额外保存 JSONL 指标时，在训练命令前加上 `MOTRIX_METRICS_JSONL=1`：

```bash
MOTRIX_METRICS_JSONL=1 mxlab train task=dexevt-walk-flat/motrix.fastsac
```

### 回放、录制与导出

训练完成后，自动查找对应环境的最新训练运行并回放：

```bash
mxlab play env=dexevt-walk-flat
mxlab play env=dexevt-wbt-dance
```

指定 checkpoint、录制视频或导出 ONNX：

```bash
mxlab play policy=/path/to/run/checkpoints/latest.pt
mxlab play env=dexevt-walk-flat num_envs=1 record_video=true record_seconds=12 record_width=960 record_height=720
mxlab export-onnx run_dir=/path/to/run output=policy.onnx
```

录制的视频保存在对应训练目录的 `play_video.mp4`。回放使用本地训练得到的 checkpoint。

## 项目结构

```text
configs/task/                  # FastSAC 训练配置
src/dexevt_mxlab/
├── robots/
│   ├── dexevt.py              # 机器人配置
│   └── assets/dexevt/         # URDF 与 mesh
├── envs/
│   ├── common/               # 共享场景与资源
│   ├── walk/                 # 平地行走任务
│   └── wbt/                  # 动作跟踪任务与参考动作数据
└── registration.py           # 环境与机器人插件注册
docs/media/                    # 回放视频、训练曲线与绘图工具
tests/                         # 插件与资源契约测试
```

### 接入自定义任务

- **机器人**：在 [robots](src/dexevt_mxlab/robots/) 中定义模型、驱动和默认姿态。
- **任务**：在 [envs](src/dexevt_mxlab/envs/) 中组合观测、动作、奖励和终止条件，任务逻辑放在各自的 `mdp/` 中。
- **注册**：通过 [pyproject.toml](pyproject.toml) 的环境与机器人 entry point 接入自动发现。
- **训练配置**：在 [configs/task](configs/task/) 中复用框架算法配置，设置任务参数。

训练、回放和导出统一使用 `mxlab`。从其他目录启动训练时，可显式指定配置目录：

```bash
mxlab train --config-dir /path/to/dexevt-mxlab/configs task=dexevt-walk-flat/motrix.fastsac
```

更多用法参见 [MotrixLab 文档](https://motrixlab.readthedocs.io)。

## 开发

```bash
ruff check .
ruff format --check .
pytest
```

## 许可

代码采用 [Apache-2.0](LICENSE) 许可证。机器人模型、动作数据及纹理的许可独立于代码许可；公开分发前需确认其来源与授权。
