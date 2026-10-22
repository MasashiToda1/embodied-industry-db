# PN → RP1.3.2：GMR / mink 实时重定向

读取 PN 人体骨架，通过标准 T-pose、RP1 CAD 几何适配和每周期一次 mink IK，生成固定 50 Hz 的 ROS 2 reference。Viser 显示实际机器人模型、原始 PN 和处理后的目标；查看器不控制机器人。

仓库已带实时接收所需的 PN Python 接口、Linux x86_64 / ARM64 动态库、当前使用的 RP1.3.2 MJCF 及其必需网格、固定版本的 GMR 最小运行源码，以及与当前工作区数值一致的默认标定。默认保留经用户授权的派生人体骨长，姿态仍采用解析标准 T-pose；旧中性尺寸标定另存为可选项。克隆后安装 Python/ROS 依赖并配置 PN 网络即可运行，无需再下载模型或 GMR，也无需先从真人录制生成标定。旧备份、Windows DLL、其它机器人、真人原始录制和虚拟环境不随仓库分发。

已验证环境为 **Ubuntu 22.04 / Linux x86_64、Python 3.10、ROS 2 Humble**，IK 可在 CPU 上运行。ARM64 库已经纳入，但 ARM64 的完整运行流程未实测；当前启动和依赖说明面向上述 x86_64 环境。依赖版本固定在 `requirements*.txt`，不打包虚拟环境。

**许可状态：项目自有代码许可证暂未选定。GMR 保留原 MIT 声明；PN SDK 和 RP1 模型的原件中尚未找到明确再分发许可，不能视为由本项目授予开源许可。** 具体来源和边界见 [THIRD_PARTY](docs/THIRD_PARTY.md)。

## 一键安装环境

在 Ubuntu 22.04 / ROS 2 Humble 上，克隆后进入仓库根目录运行：

```bash
./install.sh
```

它创建 `.venv-ik`、`.venv-ros`，安装固定版本的 Python 依赖，最后检查依赖、模型、SDK、ROS 导入与一次标准 T-pose 离线 IK。安装过程不询问 PN 地址，不创建或修改 `.env` 或 YAML，不连接设备、不播放 demo，也不改 retarget 参数或标定。可以重复运行以补齐依赖；`./run.sh setup` 是同一安装流程的备用入口。

若系统尚无 venv/ensurepip、编译工具或 ROS 消息包，先运行 `./install.sh --system-deps`；该选项显式调用 apt，需要 `sudo`，ROS apt 源需先按[官方步骤](https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html)配置。默认安装不执行提权、不修改系统网络。

无显示需求用 `./install.sh --no-viser`。关闭显示的选择会供后续运行工具沿用；需要补装显示依赖并恢复显示，用 `./install.sh --viser`。`--python /path/to/python3.10` 可指定 IK 环境的 Python，`--print-plan` 只显示安装计划。

## 安装后的可选操作

环境安装和网络配置是分开的。接 PN 前，在 `mocapapi_python/rp1/publish.yaml` 的 `pn_network` 中填写电脑 PN 网口和 PN-Link 的实际地址；也可运行 `./run.sh configure`，它将 PN 地址/端口写入该 YAML，将 ROS domain 写入 `.env`。运行工具无需手动激活环境：`run.sh` 会切到仓库根目录，读取本地 `.env`，并在存在时受控加载 `/opt/ros/humble/setup.bash`。

```bash
./run.sh configure                  # PN 网络写入 publish.yaml，ROS domain 写入 .env
./run.sh check                      # 检查依赖、SDK、模型、ROS 和一次离线 IK
./run.sh check --offline            # 无需 ROS 的离线环境检查
./run.sh demo                       # 合成回放验证并打开只读 Viser
./run.sh demo --no-viser            # 只完成离线验收，不打开页面
./run.sh start --dry-run             # 连接 PN 和显示，但不创建 ROS publisher
./run.sh start --no-viser            # 正式发布，不启动显示
```

运行入口只读取 `.env` 中的赋值，不执行其中的 shell 命令；所有命令都可加 `--print-plan` 先查看计划。`check` 不打开 PN、不创建 ROS 节点或 publisher。需要使用已有解释器、逐步安装或修改端口时，见[安装说明](docs/INSTALLATION.md)。

当前 GMR 入口和启动工具默认读取上述 `publish.yaml`，网络配置如下；两个 IP 必须与自己的电脑/设备相符。修改后重启 `./run.sh start` 即生效，无需重装环境：

```yaml
pn_network:
  local_ip: 10.42.0.101   # 电脑连接 PN 的网口 IP
  local_port: 8002        # 本机 UDP 接收端口
  server_ip: 10.42.0.202  # PN-Link 设备 IP
  server_port: 8080       # PN-Link 命令端口
```

逐字段优先级为 **显式 CLI > YAML > 旧 PN 网络环境变量 > 旧默认值**；已有 `.env` 中的 `PN_LOCAL_IP` 等不会覆盖 YAML。可用 `./run.sh start --publish-config /path/to/publish.yaml` 选择另一份配置，或用 `./run.sh start --pn-local-ip 10.42.0.101 --pn-server-ip 10.42.0.202` 临时覆盖 IP；CLI 不改保存值。该网络 YAML 功能用于当前 GMR 入口和启动工具，旧 SDK 欧拉角入口仍使用原网络参数方式。程序检查本机绑定地址，不会修改网卡或猜测设备 IP。

`demo` 用 4 秒合成人体骨架完成离线 retarget 和 50 Hz 调度检查，随后打开只读 Viser：[http://127.0.0.1:8890/](http://127.0.0.1:8890/)，按 **Ctrl-C** 退出；它不接设备、不创建 ROS publisher。主动运行 `start` 才会连接 PN；正式启动以 50 Hz 发布待机站姿，按 **N** 采集、**A** 对齐并过渡进入跟随、**X** 回站、**Esc** 退出。

## 手动安装与运行

以下保留底层入口，方便使用已有 Python 环境或逐步排错；采用上面的一键入口时无需重复执行。

### 1. 准备本地依赖

RP1.3.2 入口位于 `assets/robots/rp1_description/mjcf/robot_28dof.teleop.xml`，GMR 运行源码位于 `third_party/GMR/`，PN SDK 位于 `mocapapi_python/`。程序使用仓库内路径；无需安装另一个 GMR checkout，也无需设置外部 SDK 路径。完整系统包、ROS 与分环境安装步骤见 [安装说明](docs/INSTALLATION.md)。

在项目根目录执行：

```bash
cp .env.example .env
# 保留仓库内模型/GMR路径；PN网络在mocapapi_python/rp1/publish.yaml中设置。
set -a; . ./.env; set +a
export PYTHONNOUSERSITE=1

python3.10 -m venv .venv-ik
.venv-ik/bin/python -m pip install -r requirements.txt
```

附带的 GMR 保留当前版本的 `motion_retarget.py`，只精简包入口和机器人注册表。本项目不导入上游的其它机器人、SMPL-X、离线人体数据工具或查看器，因此不需要 Torch、SMPL-X 模型数据或 GMR 的完整环境。固定依赖包含实际 IK 路径所需的 Cython、rich、MuJoCo、mink 和 DAQP。

直接运行 Python 入口时，`.env` 只在上面的显式 shell 命令中加载；运行工具 `run.sh check/start/demo` 会自动读取已有 `.env`。`PN_RP1_SOLVER_PYTHON` 和 `PN_RP1_VISER_PYTHON` 指向求解/显示 Python；ROS 主进程可使用单独的系统 Python 环境。

### 2. 默认标定和合成示例

仓库已提供与附带模型一致的标准标定，直接运行不需要重新生成。先生成一个与设备无关的合成示例：

```bash
.venv-ik/bin/python tools/make_demo_recording.py
```

两份默认配置 `mocapapi_python/rp1/pn_axis_to_rp1_28dof.json` 与 `pn_axis_to_rp1_28dof_current.json` 内容相同，与当前工作区保留相同的人体标量骨长、解析标准 T-pose、pitch 映射、scale 0.78 和求解参数；人体标准根高度为1.0095348389594085 m。发布副本仅移除来源录制路径、哈希和帧数，并将模型路径改为相对路径；默认现在包含个人派生尺寸，不能视为中性尺寸或匿名化数据。原始录制不随包提供，也不从录制挑选近似 T-pose。

直接运行 `./run.sh start` 使用工作区版。旧发布版保留为 `mocapapi_python/rp1/pn_axis_to_rp1_28dof_neutral.json`，人体标准根高度0.91 m、左右大腿/小腿均0.43 m，可显式切换：

```bash
./run.sh start --calibration mocapapi_python/rp1/pn_axis_to_rp1_28dof_neutral.json
```

`tools/prepare_calibration.py` 的 `--template current|neutral` 默认是 `current`；无参数重建保留 current 的人体尺寸和解析标准姿态。使用 `neutral` 必须用 `--output` 指定独立文件，不能覆盖默认别名。若修改模型或 preset，可用此工具重建；自有模型可用 `--model /path/to/robot_28dof.teleop.xml` 指定。细节见 [标定说明](docs/CONFIGURATION.md#生成标定)。

默认 preset 是 `configs/presets/baseline.json`，与最后一版 Viser 对比参数一致：pitch 任务映射、根位移 scale 0.78；髋/膝/腰关节速度 14.24192 rad/s，踝/上肢 21.88648 rad/s；关闭关节加速度限制、IK前脚部支撑处理和腰 pitch 补偿。根线速度/角速度/线加速度/角加速度限制分别为 7.2 m/s、14.4 rad/s、60 m/s²、96 rad/s²。关节角度、速度和 IK 地板约束保留，每周期仍只求解一次 QP。`replay_acc_off.json` 保留同参数的对照入口，`replay_acc100.json` 仅开启 100 rad/s² 关节加速度限制，详见 [配置说明](docs/CONFIGURATION.md)。这套默认参数尚未完成真实机器人动态验证。

合成示例位于 `outputs/demo_pn.npz`：4秒、50 Hz、含终点共201帧，仅让解析人体骨架整体做 XY/yaw 运动。它用于检查格式和安装，不是真人数据、走路样本或重定向质量基准。

### 3. 先离线运行

```bash
.venv-ik/bin/python tools/evaluate_recording.py \
  --config mocapapi_python/rp1/pn_axis_to_rp1_28dof_current.json \
  --source outputs/demo_pn.npz --output-dir outputs/demo_ik

.venv-ik/bin/python mocapapi_python/mocap_rp1_gmr_reference.py \
  --source replay --npz outputs/demo_pn.npz --dry-run --autostart --no-viser \
  --output outputs/demo_reference.jsonl --metrics outputs/demo_metrics.json
```

第一步保存 IK 姿态和运动学诊断；第二步按实际时钟运行发布调度，但不打开 PN、不启动 ROS 发布。`--autostart` 在这里仅用于离线回放。reference 处理为：**IK → 固定高度偏移 → 初始 XY/yaw 对齐 → 2秒过渡 → 50 Hz 输出**，没有发布阶段的第二次约束求解。

打开离线 3D：

```bash
.venv-ik/bin/python mocapapi_python/view_rp1_gmr_3d.py \
  --source final \
  --config mocapapi_python/rp1/pn_axis_to_rp1_28dof_current.json \
  --core outputs/demo_ik/replay.npz --reference outputs/demo_reference.jsonl \
  --port 8890
```

在浏览器打开 [Viser](http://127.0.0.1:8890/)。下拉框切换 IK/reference，面板可控制机器人透明度、原始/缩放/目标骨骼、XY居中和世界轨迹。MuJoCo 在这里计算正运动学，未执行物理仿真。

### 4. 手动接入 live

先按 [安装说明](docs/INSTALLATION.md) 安装 ROS 2 Humble 和消息包。ROS 依赖来自系统包，不应使用 `pip install rclpy` 代替。以下命令在 Bash 执行，并使用与 ROS ABI 匹配的 `/usr/bin/python3`。

```bash
source /opt/ros/humble/setup.bash
set -a; . ./.env; set +a
export PYTHONNOUSERSITE=1
/usr/bin/python3 -m venv --system-site-packages .venv-ros
.venv-ros/bin/python -m pip install -r requirements-live.txt

# publish.yaml 的 pn_network 必须与电脑和PN-Link的实际地址一致。
.venv-ros/bin/python tools/check_environment.py --mode live
python3 tools/start_live.py \
  --output outputs/live_reference.jsonl --metrics outputs/live_metrics.json
```

检查命令加载 SDK 和依赖，并用模型/标定完成一次标准 T-pose 离线 IK；不连接 PN、不创建 ROS 节点或 publisher。底层 `start_live.py` 自动定位仓库内模型、GMR、`.venv-ros` 和 `.venv-ik`，从所选 `--publish-config` 的 `pn_network` 读取网络配置并启动正式桥接；直接调用这个 Python 文件仍需手动加载 ROS 和需要的 `.env` 运行环境变量。`./run.sh start` 已处理这两步。原程序入口与完整参数见 [安装说明](docs/INSTALLATION.md)。

启动桥接后会按 50 Hz 发布待机站姿，**不会自动进入人体跟随**。终端 **N** 开始采集、**A** 对齐并过渡到跟随、**X** 过渡回站、**Esc** 退出。集成 Viser 默认在 [8891](http://127.0.0.1:8891/)，接收与 ROS 相同的已发布向量和另一个最新 PN 显示槽。`python3 tools/start_live.py --no-viser` 可关闭显示。

第一次接设备时可将启动命令加上 `--dry-run`，只接收、求解并显示，不创建 ROS publisher。确认后去掉该选项。需要与现有 tracking 连接时，将 `.env` 的 `ROS_DOMAIN_ID` 设为跟踪端所用值；示例的 217 是测试用值。发布频率可在另一个已加载同 domain 的 ROS 终端检查：

```bash
ros2 topic hz /tracking/current_reference
```

默认正式话题 `/tracking/current_reference` 的消息为 `std_msgs/Float32MultiArray`，35个数：`xyz(m) + qw/qx/qy/qz + 28个关节(rad)`。不要同时启动另一个 PN 客户端或在同一 reference 话题重复发布。

手指使用现有独立话题 `/mocap/hand/{left,right}/poses`（`geometry_msgs/PoseArray`）与 `/mocap/hand/{left,right}/active`（`std_msgs/Bool`），默认50 Hz、QoS `best_effort` / depth 1。GMR和旧欧拉角入口的每手数组现在都只含最多19个指骨位姿，排除手腕；数据为原始PN经单位、坐标和世界位姿转换后的结果（world、米、xyzw），不是机器人手指电机角，也不应用身体重定向或发布后处理。缺失点仍省略，`active` 只表示至少有一个手指位姿。**原20点订阅端须更新索引，重启发布程序后生效**；完整顺序与接口边界见 [手指话题说明](docs/CONFIGURATION.md#独立手指话题)。

当前 `rp1/publish.yaml` 保留固定高度偏移 **−0.04 m**。这是沿世界 Z 整体降低 reference，不是通用的自动落地补偿；脚底也会降低，IK地板约束只保证偏移前结果。接跟踪策略前必须根据自己的模型、训练数据及接口核对高度。运动学 reference 和 Viser 画面不能证明真实机器人动态稳定。

## 测试与更多说明

```bash
python3.10 -m venv .venv-test
.venv-test/bin/python -m pip install -r requirements-test.txt
.venv-test/bin/python tools/check_release.py
.venv-test/bin/python -m pytest
```

`requirements-test.txt` 安装 IK 核心、Viser 和 pytest，不安装 Torch 或 Open3D。测试使用合成数据/mock，并检查附带 RP1/GMR 模型；不连接 PN、不创建 ROS publisher。SDK 实际加载、完整依赖与动作回放由环境检查及上述离线流程验证。

- [安装、模型路径与排错](docs/INSTALLATION.md)
- [配置与 preset](docs/CONFIGURATION.md)
- [数据流、调度与可视化](docs/ARCHITECTURE.md)
- [第三方依赖与许可边界](docs/THIRD_PARTY.md)
- [发布内容与排除项](docs/RELEASE_CONTENTS.md)
