<div align="center">

# Toward Real-Time VLAs:<br>Stage-Aware Two-Step Flow Denoising and System-Level Evaluation

**Magiclab Robotics**

[📄 Paper](main.pdf) · [🇨🇳 中文文档](README_zh-CN.md) · [🔌 Integration](client/integration/README.md)

[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![JAX](https://img.shields.io/badge/Policy-JAX%20%7C%20TensorRT-76B900)](https://developer.nvidia.com/tensorrt)
[![Robot](https://img.shields.io/badge/Robot-Agilex%20Piper-111827)](https://global.agilex.ai/product/piper)
[![License](https://img.shields.io/badge/License-Apache--2.0-2ea44f)](LICENSE)

</div>

<p align="center">
  <img src="assets/paper/figure5-framework.png" alt="Distributed real-time VLA inference and execution framework" width="100%">
</p>

## 📖 Overview

This repository provides a distributed runtime for deploying and evaluating real-time VLA policies on two Agilex Piper arms. It separates observation acquisition, policy inference, action publication, and robot control so low-rate model updates can coexist with high-rate physical execution.

The accompanying paper measures the complete timing path from camera and proprioception to robot motion, introduces stage-aware Flow Matching denoising, and compares real-time execution strategies on long-horizon bimanual garment folding.

- **End-to-end timing:** measure camera, proprioception, model, transport, scheduling, and robot-response latency in one runtime.
- **Stage-aware Flow Matching:** combine a long first-stage update with terminal refinement using the non-uniform schedule `1 → 0.3 → 0`.
- **Practical execution:** deploy VLA policies on two Agilex Piper arms with independent observation, inference, publication, and control rates.
- **Reproducible evaluation:** compare real-time execution methods with shared interfaces, action provenance, and hardware-free mock tests.

## 🚀 News

- **[2026/09/30]** 🔥 Source code released, including the paper, deployment scripts, integration guides, and hardware-free mock tests.

## 🛠️ Installation

The runtime is tested with **Python 3.11**. We recommend [uv](https://docs.astral.sh/uv/) for creating the virtual environment and resolving the pinned project dependencies. The JAX checkpoint backend requires a CUDA-compatible GPU and a matching CUDA runtime; TensorRT deployments additionally require a compatible TensorRT installation. The hardware client is optional and only needs the extra CAN and camera dependencies when running on a physical Piper platform.

```bash
uv sync --python 3.11
. .venv/bin/activate
```

If you plan to connect the runtime to physical Agilex Piper arms, install the robot-client dependencies below. They provide the Piper SDK and camera interfaces; the hardware-free mock workflow does not require them.

```bash
uv pip install -r client/requirements_inference.txt
sudo apt update
sudo apt install -y can-utils ethtool
```

## 📦 Policy backends

| Backend | Configuration | Use |
| --- | --- | --- |
| JAX checkpoint | `policy.type: checkpoint` | Research and standard Flow Matching inference |
| TensorRT engine | `policy.type: tensorrt` | Optimized deployment with CUDA/TensorRT |
| Default policy | `policy.type: default` | Use a built-in policy configuration |

For checkpoints, `policy.config` must match the model architecture and training transforms. Normalization statistics are loaded from:

```text
/path/to/checkpoint/assets/<asset_id>/norm_stats.json
```

## 🚀 Quick start

### Start the policy server

Edit `server/config.yaml` to select the transport, listening port, default language instruction, and policy backend. For a checkpoint deployment, set `policy.config` to the model architecture used during training and point `policy.dir` to the exported checkpoint directory. If the checkpoint contains multiple asset bundles, use `asset_id` to select the matching normalization statistics.

```yaml
transport: websocket
port: 8000
default_prompt: fold the sleeve

policy:
  type: checkpoint
  config: pi05_flatten_fold_normal
  dir: /path/to/checkpoint
  asset_id: OpenDriveLab-org/Kai0
```

After saving the configuration, launch the policy server. The server loads the selected checkpoint, opens the configured transport endpoint, and waits for client observation requests:

```bash
./scripts/run_server.sh --config server/config.yaml
```

Use `./scripts/run_server.sh --dry-run` to inspect the resolved command.

### Start the Piper client

Before starting the client, update `client/config_agilex.yaml` with the policy-server address, CAN interface names, RealSense serial numbers, initial arm pose, and runtime rates. `inference_rate` controls how often the policy receives a new observation; `publish_rate` controls how often commands are sent to the robot:

```yaml
server:
  host: 127.0.0.1
  port: 8000

inference:
  execution_mode: async
  async_mode: temporal_smoothing
  chunk_size: 50
  publish_rate: 30
  observation_rate: 30
  inference_rate: 3
  prompt: fold the sleeve
```

Run a hardware check before motion:

```bash
./scripts/run_client.sh --config client/config_agilex.yaml --check-hardware
./scripts/run_client.sh --config client/config_agilex.yaml --log-level INFO
```

> ⚠️ Start at reduced speed, verify the emergency stop, and stay outside the robot workspace.

### Run without hardware

```bash
./scripts/run_client_mock.sh
uv run pytest test packages server/openpi
```

## ⚙️ Real-time execution modes

- **`naive`** — Asynchronous inference beside robot execution.
- **`temporal_smoothing`** — Blend the previous chunk tail with the new prefix.
- **`temporal_ensembling`** — Aggregate overlapping action predictions.
- **`rtc`** — Constrain generation with committed actions.
- **`legato`** — Learned native action continuation.
- **`ttrtc`** — Training-time latency-aware continuation.
- **`vlash`** — Future-state-aware action alignment.

Select a mode with `inference.async_mode`; parameters live under `inference.modes.async.<mode>`.

## 🔌 Deployment

### 🌐 WebSocket

Use WebSocket when the GPU policy server and the robot client run on separate hosts. Set the server port below, then point the client configuration to the server machine's reachable IP address. This mode is convenient when the robot computer handles sensors and control while a separate workstation handles policy inference:

```yaml
transport: websocket
port: 8000
```

### 🧠 Shared memory

Use shared memory when the policy server and robot client run on the same host. The Unix socket path must be accessible to both processes and should be removed or changed if another service already uses it. Shared memory avoids network serialization and is intended for low-latency local deployment:

```yaml
transport: shared_memory
shared_memory_socket_path: /tmp/openpi_policy.sock
```

### ⚡ TensorRT

Build a TensorRT engine from an existing ONNX model when the target GPU and CUDA/TensorRT runtime are fixed. The generated engine is hardware and precision dependent, so build it on a machine that matches the intended deployment environment. Use FP16 for the common CUDA deployment path, or select another precision supported by the model and GPU:

```bash
.venv/bin/python scripts/build_trt_engine.py \
  --onnx /path/to/model.onnx \
  --engine /path/to/model_fp16.engine
```

Configure `policy.type: tensorrt`, `engine`, `assets_dir`, `asset_id`, `device`, and `precision`.

## 🗂️ Integrations

Client records are written to `client/inference_records/` by default. The `recording` section controls model I/O, video, action CSV, runtime events, and timing metadata.

- [Collection integration](client/integration/README.md)
- [Inference Service TCP API](docs/INFERENCE_SERVICE_TCP_API.md)
- [Piper XH timeline integration](docs/PIPER_XH_TIMEAXIS_INTEGRATION.md)

```bash
cd client
python run_inference_service.py --config config_agilex.yaml --list-modes
python run_inference_service.py --config config_agilex.yaml --mode temporal_smoothing
```

## 🌐 VLA / WAM ecosystem

This runtime sits between an action-generating policy and a physical robot.

- **VLA policies:** [OpenPI](https://github.com/Physical-Intelligence/openpi), [OpenVLA](https://github.com/openvla/openvla), [π₀ / π₀.₅](https://www.physicalintelligence.company/download/pi0.pdf) — open-source vision-language-action policies for action generation and robot control.
- **Robot learning:** [LeRobot](https://github.com/huggingface/lerobot) — shared datasets, robot abstractions, training tools, and evaluation interfaces.
- **World–Action Models:** [OpenWAM](https://github.com/OpenWAM-Official/OpenWAM), [OpenWAM project](https://openwam.stanford.edu/) — future-state and video-conditioned modeling for predictive robot action.

## 📁 Repository

```text
client/                  robot runtime, configs, integrations, tools
server/                  policy server and model implementations
packages/openpi-client/  WebSocket and shared-memory clients
scripts/                 launchers, CAN helpers, TensorRT tooling
docs/                    API and integration notes
test/                    mock fixtures and tests
assets/paper/            paper figures used in this README
main.pdf                 paper
```

## 📝 Citation

```bibtex
@article{wu2026closing,
  title  = {Toward Real-Time VLAs: Stage-Aware Two-Step Flow Denoising and System-Level Evaluation},
  author = {Wu, Di and Shen, Rongtian and Liu, Ping and Shen, Yan and Yin, Zhenhan and Zuo, Shun and Chen, Xuhua and Zheng, He and Zhang, Lingfeng and Zhang, Jianglin and Zhang, Tao},
  year   = {2026}
}
```

## 📜 License

[Apache License 2.0](LICENSE)
