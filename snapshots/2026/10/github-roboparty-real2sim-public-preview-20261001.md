# GPT-6 Astra Real2sim workflow

**简体中文** | [English](README_EN.md)

**让图像、家具规格和结构证据共同约束可编辑的仿真场景。**

面向具身智能与机器人研发团队的社区工作流：在具备工具调用能力的 GPT-6 Astra 环境中完成观察、空间推理、建模决策和预览审查，再由 Python、Blender 与 MuJoCo 执行拟合、场景构建、渲染、仿真及检查。

仓库提供阶段协议、执行器、工具脚本和已验证案例配方；模型访问由使用者的 Agent 环境提供。冻结案例可直接用脚本复跑，不需要重新调用语言模型。本项目由 Roboparty 维护，是第三方研究工程项目，非 OpenAI 官方发布。

![原始实拍与 Blender 重建：左为原图，右为重建](docs/example/figures/source_comparison.jpg)

[约 17 秒对比预览](docs/example/figures/comparison_preview.mp4) · [真实动力学演示](docs/example/figures/dynamics_A.mp4) · [完整案例](docs/example/EXAMPLE_WALKTHROUGH.md) · [当前验收结果](docs/example/RESULTS.md)

## 家具尺寸与详细型号能增强什么

单图中尺寸、深度和遮挡结构存在歧义。工作流允许把有来源的实测尺寸、厂家规格和精确型号交给 Agent，与图像观测共同约束建模：

| 补充信息 | 如何参与重建 | 预期价值 |
|---|---|---|
| 有来源的长、宽、高或局部尺寸 | 在核对图像对应、单位和测量定义后加入尺度及形状约束 | 减少绝对尺度与比例猜测，帮助相机/物体联合拟合 |
| 品牌、精确型号、代次与配置 | 核对腿型、靠背、连接方式和规格图，区分相似外观与真实同款 | 缩小结构解释范围，减少错误部件关系和随意补全 |
| 经过核实的准确同款 3D 资产 | 由执行 Agent 检查版本、单位、使用条件和几何后，走同款辅助分支 | 有机会减少重新建模工作，保留可追溯的资产来源 |
| 不能核实的型号或不一致的规格 | 保留候选与冲突，回退独立建模 | 避免把“看起来像”当成同款，或用错误目录尺寸拉偏模型 |

**当前状态：这些是 Agent 引导的规格使用机制与增强方向。仓库有尺寸先验拟合函数和分支约定，但没有自动 SKU 搜索服务、通用同款资产导入器或完整自动许可核验。当前实拍案例使用常见尺寸先验，B 全部回退 A，没有验证厂家尺寸或同款资产的量化增益。**

我们不报告未经对照实验支持的“精度提升百分比”。详见 [尺寸与型号增强说明](docs/FURNITURE_SPEC_ENHANCEMENT.md)，包括输入要求、实现状态及建议的对照方法。

## 这个工作流的特点

- **完整、可编辑的结构**：把家具作为共享坐标下的部件装配，检查连接、支撑与落地；房间保留四墙、地面、顶面和灯具，隐藏部分记录假设。
- **源图证据绑定到当前模型**：观察文件、部件、模型版本和审核工件关联；已实现的几何门槛可阻断错归属、断连接、漏审和失效证据。
- **分别审查几何、材质与光照**：逐物体和多视角检查与全图外观分开，避免仅靠总体亮度评分判断家具结构。
- **真实数值执行与格式重载**：案例包含 MuJoCo 铰链、薄片布料、体积柔体，以及 GLB/USD 实际重载；工程一致性与现实准确度分别报告。
- **可追溯修订**：保留失败候选、输入输出哈希和阶段修订记录，方便复查、恢复和研究对照。

这些特点不等于任意场景都能一键高精度重建。GLB 偏心主点需要附加内参，跨格式着色可能简化；物理试验只覆盖已记录的参数与时间窗口。完整状态见 [能力与边界](public_contract/CAPABILITIES.md) 和 [已知实现限制](KNOWN_LIMITATIONS.md)。

## 首版已验证内容

- A/B 各 18 个阶段通过执行与审核，独立冻结配方复跑完成。
- 6 项真实网格测试情形与 8 项合同测试符合预期：断腿、错横杆、非预期穿插、错误归属、旧源图点、漏审和错误版本/证据会被拒绝。
- 观察记录直接绑定部件生成；结构审计检查实际求值网格，审核绑定当前模型和证据哈希。
- 新加载试验运行 4000 步、约 2 秒，求解器警告为零；接触容差、物性先验和形变结果单独记录。
- 单张照片没有独立尺度/物性真值；桌面角点仍有约 10.23 px 最大拟合差异。

这些是随仓库附带的历史运行证据；执行下方测试会产生新的检查结果，不会自动冒充新一次人工视觉审核。

## 目录

| 路径 | 内容 |
|---|---|
| `workflow/r2s/` | 执行器、阶段依赖、证据合同、结构检查、渲染、导出与仿真 |
| `public_contract/` | 任务模板、主 Prompt 和 Agent 执行约定 |
| `case/` | 本照片的观察、参数拟合、建模和物理实现 |
| `tools/` | 初始化、续跑、提交、复跑和测试入口 |
| `tests/fixtures/` | 合同回归测试数据，不是真实视觉验收图 |
| `inputs/` | 当前案例的授权原图 |
| `docs/example/` | 示例说明、结果、选定证据和预览 |

## 运行合同测试

Python 3.10+。以下合同检查使用 Python 标准库，无需下载模型权重：

```bash
export PYTHONPATH="$PWD/workflow"
python tools/test_structure_contract.py
```

PowerShell：

```powershell
$env:PYTHONPATH = Join-Path $PWD 'workflow'
python tools/test_structure_contract.py
```

## 复跑当前案例

在远端独立环境安装 `requirements-replay.txt`，准备 Blender 4.5.3、MuJoCo 3.13.0、FFmpeg 和离屏渲染条件。本案例原图哈希固定，替换照片需要重新观察与建模。

```bash
export R2S_PYTHON=/path/to/venv/bin/python
export R2S_BLENDER=/path/to/blender-4.5.3/blender
export R2S_GPU=0
export R2S_CPU=1
export PYTHONPATH="$PWD/workflow"
"$R2S_PYTHON" tools/rebuild_artifacts.py --output "$PWD/replay_runs/my_replay"
```

输出目录必须不存在。新版入口使用模型版本 4；脚本保留的旧分支只供历史复现，缺少新结构合同的模型不能通过当前验收。

完整流程、正式 Agent 阶段、实际网格错误注入和续改方式见 [复跑说明](docs/example/REPLAY.md)。

## 生成链路与后续接入

观察与部件归属 → 整件几何约束 → 建模 → 实际网格与局部视觉检查 → 材质/光照 → 动力学 → 导出重载。

- [本次链路修订](docs/example/PIPELINE_CHANGES.md)
- [对应代码补丁](docs/example/PIPELINE_PATCH.diff)
- [Astra 及其他后端参考](docs/INTEGRATIONS.md)

第三方 Astra 工作流、SAM 3D、VGGT 等目前是待评估接入方向；本仓库没有声称已经安装或同图实测这些后端。

## 文件与许可范围

本仓库提交源码、说明、原图、主要 JSON 审计和小型预览。大型模型、完整轨迹、原始高分辨率审核图和归档保留在远端资产存储，不进入 Git 历史。详见 [ARTIFACTS.md](ARTIFACTS.md)。

源码、项目自有文字文档及机器可读元数据采用 [MIT License](LICENSE)。示例照片与派生图片/视频单独适用 [媒体说明](MEDIA_NOTICE.md)，不因源码 MIT 自动取得相同的复用许可。第三方依赖保留其自身许可，见 [依赖与来源说明](THIRD_PARTY_NOTICES.md)。

[来源与授权记录](PROVENANCE.md) · [首个公开预览版说明](docs/releases/public-preview-20260925.md)
