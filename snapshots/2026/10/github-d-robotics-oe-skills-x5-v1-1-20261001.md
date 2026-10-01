<p align="center">
  <b>中文</b> | <a href="README.en.md">English</a>
</p>

> 面向 D-Robotics X5 OpenExplorer（OE）工具链的 Agent Skills 集合。覆盖 OE Mapper PTQ、Plugin QAT、Runtime、板端 Python API 与诊断，将路径知识、阶段依赖和验证流程模块化，支持 Agent 按流程完成从浮点模型到板端部署的端到端优化。

# 功能介绍

* **工具链路由编排**：`x5-router` 作为顶层入口，按 `skill-index.json` 的 `routing_policy`、`intents`、`accepts` 和 `handoffs` 选择子 Skill；通用量化默认优先 PTQ

* **端到端部署流程**：覆盖「量化 → 编译 → 板端推理 → 性能/精度评估」完整链路，全链路部署规范优先于单步 Skill 的默认行为

* **环境检测**：默认检查 X5 OE Docker 工具链；只有显式设置 `--execution-mode host` 才使用宿主机 CLI；按需探测开发板和 Python/CUDA/PyTorch 环境

* **精度调优**：QAT 适配与导出、PTQ 量化构建、混合精度调优、训练-部署一致性 debug、Cosine Similarity

* **性能分析**：Perfetto trace 抓取与分析、`hb_perf` 性能瓶颈定位、板端 BPU/DDR/内存资源监控

# 快速开始

## 安装

### 安装 skills

```python
# 直接对你的Agent说
安装当前仓库中的 `agent-setup.md`。
```

当前发布版本：`v1.1.0`。

OE 官方强烈建议使用 Docker。量化方式未指定且模型为 ONNX/Caffe 时，先走 PTQ；只有明确要求 QAT 或 PTQ 评测确认无法达到目标时才考虑 QAT。详见 [OE X5 环境部署手册](https://developer.d-robotics.cc/oe_x5_doc/cn/oe_mapper/source/env_install/env_deploy.html) 和 [PTQ/QAT 简介](https://developer.d-robotics.cc/oe_x5_doc/cn/oe_mapper/source/faststart/ptq_qat_overview.html)。

QAT 环境探测使用 X5 GPU image 和 Docker `--gpus all` 检查 `torch.cuda.is_available()`。这只确认 CUDA 设备在容器内可见，不代表训练过程已验证。

### 本地文档检索

本 Pack 不依赖远程 MCP 文档服务。补充参考从环境变量或工作区相对位置发现本地 X5 OpenExplorer 文档包。

安装后可直接运行：

```bash
python .drobotics-x5/scripts/search_local_docs.py --query "X5 hb_mapper makertbin"
```

X5 使用 `OE_DROBOTICS_DOC_ROOT`（兼容 `OE_X_SERIES_DOC_ROOT`）。未设置时脚本会从工作区相对目录发现。更多规则见 `.drobotics-x5/docs/local-document-retrieval.md`。

## 使用

| **任务场景**    | **提示词**                                                                                                        | **调用skill**                      |
| ----------- | -------------------------------------------------------------------------------------------------------------- | -------------------------------- |
| 模型延时实测      | 帮我在开发板`xx.xx.xx.xx`上测试一下`xxx.bin`的延时                                                                           | x5-runtime-perf-eval           |
| ONNX 模型 PTQ 部署 | 把 X5 ONNX 浮点模型量化部署，校准数据在`{calib_data}`，使用`{OE_docker}` | x5-ptq-deploy |
| 明确要求 Plugin QAT | 请对这个 X5 可训练 PyTorch 模型执行 Plugin QAT，验证集为`{dataset}` | x5-qat-deploy |
| 编写bin评测代码   | 帮我评测一下`xxx.bin`的精度，calib评测代码为`val.py`，开发板`xx.xx.xx.xx`。若网络延迟较高，减少评测帧数到100                                      | x5-bpu-python-api                 |
| 编写bin部署代码   | 我有四个小模型，放在`{model_path}`，这几个模型间没有数据依赖，可同时推理，帮我写一下部署代码，测试使用开发板`xx.xx.xx.xx`                                  | x5-runtime-cpp-infer          |

# 目录结构

```text
OE-Skills-X5/
├── README.md                # 本文件
├── agent-setup.md           # Agent 安装指引文档
├── setup.sh                 # 安装脚本，将 x5/ 资源铺设到目标项目 .drobotics-x5/
├── LICENSE                  # Apache 2.0
├── x5/                      # 资源目录（安装时复制到目标项目）
│   ├── X5.md                # 工作区规则和使用说明
│   ├── VERSION              # 当前版本号
│   ├── skill-index.json     # Skill 索引（模块、路径、描述、触发条件）
│   ├── docs/                # X5 工具链离线文档
│   ├── scripts/             # 验证与文档检索脚本
│   ├── platforms/           # X5 平台资产（schemas, evals, assets, scripts）
│   │   └── x5/
│   └── skills/              # X5 Skill 集合
│       └── x5/
│           ├── x5-router/   # 顶层路由 Skill
│           ├── x5-environment-*/  # 环境检测与安装
│           ├── x5-ptq-*/    # PTQ 量化
│           ├── x5-qat-*/    # Plugin QAT
│           ├── x5-runtime-*/# Runtime 推理
│           ├── x5-board-monitor/
│           ├── x5-bpu-python-api/
│           └── x5-*-diagnostics/ # 诊断
```

# Skills 介绍

### 顶层路由

`x5-router` 是 X5 工具链入口，处理 PTQ/QAT 量化编译、板端部署、性能精度评估等请求，并路由到对应子 Skill。

| Skill                    | 功能           | 触发场景                                   |
| ------------------------ | ------------ | -------------------------------------- |
| x5-router                | 顶层路由入口       | 任何 X5 工具链相关请求的分流                  |

### Environment 模块

| Skill           | 功能               | 触发场景                                  |
| --------------- | ---------------- | ------------------------------------- |
| x5-environment-setup | X5 OE 包环境配置 | 首次使用 X5 工具链时 |
| x5-environment-probe  | 环境探测与版本检查     | 确认 OE 包、Python、板端版本     |
| x5-environment-install | OE 包本地安装     | 环境缺失时按需触发         |

### PTQ 模块（onnx 量化）

| Skill                        | 功能                     | 触发场景                                       |
| ---------------------------- | ---------------------- | ------------------------------------------ |
| x5-ptq-deploy         | PTQ 部署总入口 | 模型转换、模型量化、PTQ              |
| x5-model-preflight     | 模型预检           | 量化前模型结构检查             |
| x5-calibration-data-prepare | 校准数据准备           | PTQ 校准数据集准备 |
| x5-ptq-config-authoring    | PTQ 配置编写           | 编写 `hb_mapper` YAML 配置            |
| x5-ptq-compile   | PTQ 编译          | `hb_mapper makertbin` 生成 `.bin`     |

### Plugin QAT 模块（pytorch 量化）

| Skill                        | 功能                     | 触发场景                                       |
| ---------------------------- | ---------------------- | ------------------------------------------ |
| x5-qat-deploy         | QAT 部署总入口 | QAT 量化部署              |
| x5-qat-adaptation         | 浮点 PyTorch 模型 QAT 工具适配 | 为模型适配`horizon_plugin_pytorch`              |
| x5-qat-training             | QAT 训练       | QAT 训练与收敛调优                   |
| x5-qat-compile    | QAT 编译到 `.hbm/.hbir`          | QAT 模型导出与编译             |

### Runtime 模块（板端推理）

| Skill                          | 功能                           | 触发场景                                             |
| ------------------------------ | ---------------------------- | ------------------------------------------------ |
| x5-runtime-deploy        | Runtime 部署总入口              | 板端推理部署 |
| x5-runtime-cpp-infer        | C++ 推理代码生成              | BPU SDK C/C++ 推理接口用法             |
| x5-runtime-perf-eval         | 板端性能评测 | 模型性能测试、benchmark、吞吐/延迟对比 |
| x5-board-monitor               | 板端资源监控与采集                    | BPU 占用率、DDR 带宽、内存使用                 |
| x5-bpu-python-api          | 板端 BPU Python API          | `hbm_runtime` / `HB_HBMRuntime` Python 推理    |

### Diagnostics 模块

| Skill                        | 功能                      | 触发场景                                                                                       |
| ---------------------------- | ----------------------- | ------------------------------------------------------------------------------------------ |
| x5-model-diagnostics     | 模型诊断 | 模型结构/格式/兼容性检查 |
| x5-accuracy-diagnostics  | 精度诊断 | 精度不达标、精度回退分析 |
| x5-consistency-diagnostics    | 训练-部署一致性诊断 | QAT 训练正常但板端掉点 |
| x5-performance-diagnostics  | 性能诊断 | 延迟/带宽/BPU 利用率/瓶颈分析 |

# 免责声明

感谢您关注 OE-Skills X5 项目，我们希望这些技能和知识能帮助您更好地进行 X5 OpenExplorer 开发。

在使用之前，请您了解：

* 本目录中的 Agent Skills 内容仅供技术参考和学习使用，不代表其适用于任何生产环境或关键业务系统。

* Agent自动生成的代码及其他产物，其正确性、完整性受模型能力、skill能力、用户提示词等多种因素影响，请开发者务必自己审核产物的安全性、兼容性和正确性。作者及贡献者不对因使用本内容导致的任何直接或间接损失承担责任。

* 本内容可能涉及第三方依赖或接口调用，相关权限及合规性需由开发者自行核实。

* 除非另有明确约定，本目录所有内容均基于开源协议发布，不提供任何形式的技术支持或担保。
