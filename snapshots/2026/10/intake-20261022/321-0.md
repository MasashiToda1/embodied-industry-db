# BeingBeyond D1 EDU SDK — Jetson Orin NX

<p align="center"><img src="bb_d1_edu.png" width="400" alt="BeingBeyond D1 EDU"></p>

用于 Jetson Orin NX 的 ARM64 二进制 SDK、示例和安装说明。
SDK 版本 **0.2.0**，提供 CPython **3.8 / 3.9 / 3.10 / 3.11** wheel。
默认运行环境为 Ubuntu 22.04、Python 3.10。

已验证设备：Jetson Orin NX 8GB、Ubuntu 22.04.5、L4T R36.4.3、内核 `5.15.148-tegra`。
CPython 3.8 / 3.9 / 3.10 / 3.11 均已通过软件验证。
Python 3.10 的示例 **1（灵巧手及触觉窗口）、2（头臂舵机）、3（双目相机窗口）**
已通过真机/GUI 验证；3.8 / 3.9 / 3.11 的真机/GUI 尚未实测。
跨 Python 版本的真机/GUI 验证结果不能由 3.10 的结果直接推定。
示例 0、4～10 和其他选配功能尚未测试，不属于本次已验收范围。

运动示例会使能并控制真实机器人。运行前清空运动空间，保持实体急停可触及。

- [Python 版本选择与安装](docs/PYTHON_VERSIONS.md)
- [PCAN-USB 驱动与重启恢复](lib/pcan/README.md)
- [发布说明及已知限制](docs/RELEASE_NOTES.md)
- [第三方组件与许可证](THIRD_PARTY_NOTICES.md)

## 1. 文件内容

```text
Beingbeyond_D1_edu_nx/
  README.md
  LICENSE
  THIRD_PARTY_NOTICES.md
  .gitignore / .gitattributes
  SHA256SUMS
  requirements-jetson-py{38,39,310,311}.lock.txt
  lib/
    beingbeyond_d1_edu_sdk-0.2.0-cp*-cp*-linux_aarch64.whl
    dependencies/py38/     ECOS wheel、对应源码和许可证
    pcan/                  内核模块、对应源码和许可证
    dex-retargeting/        可选库、模型和许可证，未在 NX 验收
  examples/                D1 示例及辅助模块
  tools/                   不访问硬件的安装与 IK 验证
  docs/                    版本选择、发布说明
  avp_teleop/               未验收的仿真遥操作参考
  utils/                   工具脚本，部分会操作真实硬件
```

SDK 四个核心编译为 AArch64 `.so`，wheel 不含核心 `.pyx` 或生成的 C/C++。
Python 封装和示例仍为明文。这是二进制形式的源码保护，不是密码学加密或不可逆向保证。
SDK 私有构建源码和本地开发环境不属于本发行内容。
PCAN/ECOS 的公开源码归档属于其各自的配套发布材料。

## 2. 新 NX 安装（默认 Python 3.10）

以下假定用户名为 `nvidia`，仓库目录为 `/home/nvidia/Beingbeyond_D1_edu_nx`。
如果仓库名称、用户名或路径不同，请相应替换；可在克隆时显式指定目录名。
本包需要联网安装其余依赖，不是完整离线安装包。

先确认目标架构、解释器和文件完整性：

```bash
uname -m
/usr/bin/python3.10 --version
cd /home/nvidia/Beingbeyond_D1_edu_nx
sha256sum -c SHA256SUMS
```

预期架构为 `aarch64`。不能在 x86 安装这些 ARM64 wheel，也不能更改文件名来改变 ABI。
确认系统包安装方案后，补齐依赖并创建**新的**运行环境：

```bash
sudo apt-get update
sudo apt-get install python3.10-venv libgl1 libglib2.0-0 v4l-utils usbutils
mkdir -p /home/nvidia/d1_edu_deploy
/usr/bin/python3.10 -m venv /home/nvidia/d1_edu_deploy/venv-py310
/home/nvidia/d1_edu_deploy/venv-py310/bin/python -m pip install \
  -r /home/nvidia/Beingbeyond_D1_edu_nx/requirements-jetson-py310.lock.txt
/home/nvidia/d1_edu_deploy/venv-py310/bin/python -m pip install --no-deps \
  /home/nvidia/Beingbeyond_D1_edu_nx/lib/beingbeyond_d1_edu_sdk-0.2.0-cp310-cp310-linux_aarch64.whl
/home/nvidia/d1_edu_deploy/venv-py310/bin/python -m pip check
```

如果该 venv 已存在，先核对并复用，不要盲目重建。
不要使用 sudo pip、替换系统 Python 或改动 ROS/CUDA 环境。
示例 1～3 不需要 Isaac Gym、PyTorch、MediaPipe、PyBullet 或 dex-retargeting。
Python 3.8/3.9/3.11 应使用各自的 wheel 和锁定文件，详见版本选择说明；
不要执行 `pip install lib/*.whl`。Python 3.8 安装时还需指定随附 ECOS 的 find-links 目录。

## 3. 无硬件验证

以下命令只验证安装和数值计算，不打开串口、CAN 或相机，不发送运动命令：

```bash
cd /home/nvidia/Beingbeyond_D1_edu_nx
/home/nvidia/d1_edu_deploy/venv-py310/bin/python tools/check_sdk_binary.py \
  --wheel lib/beingbeyond_d1_edu_sdk-0.2.0-cp310-cp310-linux_aarch64.whl \
  --runtime --expected-prefix /home/nvidia/d1_edu_deploy/venv-py310
/home/nvidia/d1_edu_deploy/venv-py310/bin/python tools/check_sdk_ik.py
/home/nvidia/d1_edu_deploy/venv-py310/bin/python examples/4_control_d1.py --help
```

检查覆盖 ELF/ABI、核心打包、安装来源、URDF/网格、FK、QP 和 SDK 单步 IK。
`--help` 或软件验证成功不等于示例 4 的实际运动已通过。
Python 运行后出现的 `__pycache__` 是本地缓存，不应提交；重新校验不会要求它们存在。

## 4. 设备、权限与 CAN

机器人正常供电后，分别连接 USB 串口、PCAN-USB 和 USB 相机。
三条链路互相独立，连接控制器不代表已连接相机。

| 项目 | 验证设备的设置 |
| --- | --- |
| 手部 CAN | PCAN 提供的 `can1`，1 Mbps |
| 头臂串口 | `/dev/ttyACM0`，1 Mbps |
| 相机 | `/dev/v4l/by-id/usb-SunplusIT_Inc_SPCA2100_PC_Camera-video-index0` |
| 相机采集请求 | MJPG，1280×480，30 FPS；每眼 640×480 |

接口名和节点编号可能因设备和插入顺序变化，必须先核对：

```bash
lsusb
ls -l /dev/ttyACM0 /dev/serial/by-id/ /dev/v4l/by-id/
id -nG
ip -details -statistics link show can1
```

验证设备的原生 `can0` 属于 NVIDIA `mttcan`，不是 USB PCAN。
驱动加载、接口确认和 1 Mbps 配置见 [PCAN 说明](lib/pcan/README.md)。
**附带驱动没有自动加载/开机拉起配置，重启或拔插后需要检查并手动恢复。**
`.ko` 必须与目标内核 ABI 匹配，不能仅凭 ARM64 架构相同就加载。

缺少串口/视频权限时，确认后将运行用户加入对应组：

```bash
sudo usermod -aG dialout,video nvidia
```

注销桌面并重新登录使组权限生效。旧终端不一定获得新组权限；
只需临时处理串口权限时，可在该终端运行 `newgrp dialout`。
无需将设备改成 chmod 777，也不建议用 sudo 启动 GUI 示例。

## 5. 依次运行已验收的示例

在 NX 本地桌面终端执行，每项退出后再运行下一项，不要同时启动多份控制程序：

```bash
cd /home/nvidia/Beingbeyond_D1_edu_nx/examples
/home/nvidia/d1_edu_deploy/venv-py310/bin/python 1_control_hand.py
/home/nvidia/d1_edu_deploy/venv-py310/bin/python 2_control_head_arm.py
/home/nvidia/d1_edu_deploy/venv-py310/bin/python 3_show_vision.py
```

- 示例 1 使用 `can1`，执行手部动作并显示触觉窗口。
- 示例 2 使用 `/dev/ttyACM0`，使能头臂舵机并执行预设运动。
- 示例 3 通过 USB/V4L2 显示双目相机；不是 CSI/Argus 管线。

窗口中的 `q` 用于退出，不代替实体急停。普通 SSH 不自动拥有桌面 GUI 显示能力。

常见问题：串口打开失败先检查节点、当前会话 dialout 权限和占用；
相机打开失败先检查 USB 枚举、by-id 路径、video 权限与占用，
不要在设备尚未枚举时只修改为 `/dev/video0`。

## 6. 已知边界与选配功能

- 示例 4 默认仍为 `can0`。若后续单独测试本机整机联动，应显式使用 `--hand-can can1`，
  并先核对全部设备和运动范围；本发行没有改变其控制逻辑或宣称整机联动已验收。
- 示例 0、4～10、`avp_teleop/`、`utils/` 为额外参考，不保证其全部设备、仿真与依赖可在 NX 使用。
- 附带 dex-retargeting 的安装描述为 Python `>=3.7,<3.11`，且未在 NX 验收；
  SDK 的四版本支持矩阵不自动涵盖该可选库。不要在已验收 venv 中直接安装全部选配依赖。
- 采集参数为请求值，不是相机持续帧率、延迟或丢帧性能承诺。
- 更换 Python 小版本、JetPack、发行版/glibc 或内核时需重新验证。

依赖锁定文件不含下载哈希、系统包或全部第三方 wheel。各 SDK 校验值见
[版本说明](docs/PYTHON_VERSIONS.md)，全部发布文件的相对路径校验见 `SHA256SUMS`。
