# RoboParty Capture

机器人板端的 ROS 2 数据采集包，提供 **EGO 双目相机和 IMU 驱动**，将相机、机器人状态及遥操命令录制为 MCAP 文件。

环境：**Ubuntu 24.04 / ROS 2 Jazzy**，使用系统 Python。以下命令均在仓库根目录执行。

## 首次配置

机器人已有录制依赖时无需重复安装，先加载环境并检查 MCAP 插件：

```bash
source /opt/ros/jazzy/setup.bash
/usr/bin/python3 -c "import rosbag2_py; print(rosbag2_py.get_registered_writers())"
```

输出应包含 `mcap`。缺少依赖时，按[依赖安装说明](docs/recording.md#1-检查构建和录制环境)补齐。

安装仓库自带的 EGO SDK，脚本自动选择 ARM64 或 x86_64 并校验归档：

```bash
/usr/bin/python3 scripts/setup_sdk.py
```

首次连接 EGO 时配置 USB 权限：

```bash
sdk_root="$(/usr/bin/python3 scripts/setup_sdk.py --print-root)"
sudo sh "$sdk_root/shared/install_udev_rules.sh"
sudo udevadm control --reload-rules
sudo udevadm trigger
```

完成后，**拔掉 EGO 的 USB 再插回去**，关闭可能占用设备的 EgoViewer。不接 EGO 时跳过 USB 配置；当前构建仍需安装 SDK。

## 构建

```bash
source /opt/ros/jazzy/setup.bash
ROS_SETUP=/opt/ros/jazzy/setup.bash ./scripts/build.sh
```

源码或录制预设更新后重新构建。请在目标机器编译，不要拷贝其他机器的 `build/` 或 `install/`，不要使用 Conda 环境。

构建完成后加载环境；每个新终端也都要执行：

```bash
source /opt/ros/jazzy/setup.bash
source install/hardware/setup.bash
```

## 运行

**连接 EGO，录制全部九路数据：**

```bash
ros2 launch capture_recorder ego_recording.launch.py \
  preset:=all output_dir:="$PWD/recordings/raw"
```

**不使用 EGO，录制其余六路数据：**

```bash
ros2 launch capture_recorder recording.launch.py \
  preset:=no_ego output_dir:="$PWD/recordings/raw"
```

两条命令选一条运行。前者启动 EGO 驱动和录制管理，后者只启动录制管理。机器人和遥操数据源需要另外启动，不要重复启动 EGO 驱动。

| 预设 | 录制内容 |
| --- | --- |
| `all` | EGO 左右图像、EGO IMU、关节状态、机器人 IMU、策略 action、身体参考、左右手命令，共九路 |
| `no_ego` | 除 EGO 三路外的其余六路，保留机器人自身 `/imu` |
| `ego` | 仅 EGO 左右图像和 IMU |

其他预设与配置见[录制配置说明](docs/recording.md#录制真实话题与-yaml-配置)。

## 开始与停止录制

启动后**不会自动录制**。在 `roboparty_teleop` 中开启 `recording.enabled` 后，可通过网页或 PICO **B 开始、Y 停止并保存**。

teleop 与采集端需加载一致的 `capture_recorder` 接口，使用相同 `ROS_DOMAIN_ID`，DDS 网络可互通；跨机连接不要设置 `ROS_LOCALHOST_ONLY=1`。

也可以另开终端，加载上述环境后手动调用：

```bash
# 开始；每段使用新的 request_id，task 为本次任务名
ros2 service call /recording/start capture_recorder/srv/StartRecording \
  "{request_id: 'recording-001', task: '拿杯子'}"

# 停止并等待保存完成
ros2 service call /recording/stop capture_recorder/srv/StopRecording '{}'
```

数据保存在 `recordings/raw/<任务名_时间_后缀>/`。**先停止录制并等待保存成功，再 Ctrl+C 退出 launch。** 缺少话题不阻止录制，保存成功不表示九路数据全部齐全。

查看状态和已保存的数据：

```bash
ros2 topic echo /recording/status capture_recorder/msg/RecordingStatus
# Ctrl+C 退出状态查看后，将下面的目录名替换为本段实际目录
ros2 bag info "recordings/raw/<任务名_时间_后缀>/bag"
```

拷贝数据和 Rerun 离线查看由 `roboparty_teleop` 提供，见其 `docs/offline_workflow_zh.md`。拷贝时保留完整 session 目录。

## EGO 取数检查

保持包含 EGO 的 launch 运行，另开终端加载环境后执行：

```bash
ros2 run ego_driver read_samples.py --output sample_output --timeout 15 \
  --ros-args -r __ns:=/ego
```

成功时保存左右各一张 JPEG，并打印图像尺寸、加速度和角速度；缺少数据会超时退出。两张图像不保证同步，消息时间戳为主机接收时间。

只检查相机、不需要录制管理时，可单独运行 `ros2 launch ego_driver ego.launch.py`。相机参数见 [ego.yaml](src/ego_driver/config/ego.yaml)，调整方式见[相机参数说明](docs/recording.md#相机参数)。

## 常见问题

- **找不到 EGO 或 USB 权限不足**：检查连接，安装 USB 规则后重新插拔，关闭其他占用相机的程序。
- **SDK 校验失败**：使用仓库配套归档，不要绕过校验或随意替换 SDK。
- **缺少 ROS 包或 MCAP 插件**：按[依赖安装说明](docs/recording.md#1-检查构建和录制环境)安装，在新终端重新加载环境。
- **B/Y 无法控制录制**：确认录制管理已启动、teleop 已启用录制功能，两端接口、ROS domain 和网络配置一致。能 SSH 登录不代表 ROS 服务可互通。

## 详细文档

- [配置与录制参考](docs/recording.md)：依赖、完整预设、服务接口、保存格式、回放与数据拷贝。
- [驱动接口](docs/ego_driver.md)：消息、单位、时间和坐标约定。
- [无设备模拟验证](docs/mock.md)：开发用取数、录制与回放。
- [开发记录](docs/development.md)：设计决策与验证状态。目前已确认机器人 Jazzy 录制依赖可用，完整构建、取数与录制验收仍待完成。
