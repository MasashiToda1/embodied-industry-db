# Piper 机械臂在d1 上的控制指南

## 硬件拓扑

```
D1 Orin NX (d1)
    │
    ├── can0 (板载 mttcan)    → d1 电机控制
    └── can1 (USB-CAN gs_usb) → Piper 机械臂
          └── USB 路径: 1-2.3:1.0
```

| 接口 | 驱动 | 用途 | CAN ID |
|------|------|------|--------|
| `can0` | `mttcan` (板载) | d1 电机 | 10C, 10D, 10E, 10F, 118 |
| `can1` | `gs_usb` (USB) | Piper | 12B, 128, 129, 12A, 251-2A8 |

## 首次启动

### 1. 确认 USB-CAN 适配器已识别

```bash
ip link show type can
```

应看到 `can0` 和 `can1` 两个接口。如果只有 `can0`：

```bash
# 检查 USB 设备树，确认适配器是否被识别
cat /sys/kernel/debug/usb/devices | head -30

# 如果看不到 gs_usb 设备，检查是否插紧
# 加载驱动（通常自动）
sudo modprobe gs_usb
```

### 2. 激活 CAN 接口

# can1 (Piper，通过 USB-CAN)
```
sudo ip link set can1 down
sudo ip link set can1 type can bitrate 1000000
sudo ip link set can1 up
```

### 3. 验证 Piper 在线

```bash
candump can1
```

应看到帧不断刷新。

---

## 键盘控制

### 依赖安装

```bash
pip3 install piper_sdk pynput
```

### 运行关节空间控制

```bash
cd piper_sdk
python3 piper_ctrl_moveJ_keyboard.py
```

**按键映射：**

| 按键 | 关节 | 方向 | 按键 | 关节 | 方向 |
|------|------|------|------|------|------|
| Q | J0 | +1° | A | J0 | -1° |
| W | J1 | +1° | S | J1 | -1° |
| E | J2 | +1° | D | J2 | -1° |
| R | J3 | +1° | F | J3 | -1° |
| T | J4 | +1° | G | J4 | -1° |
| Y | J5 | +1° | H | J5 | -1° |
| Z | 夹爪 | +5mm | X | 夹爪 | -5mm |

**功能键：** 空格(夹爪开关) / 1(归零) / 2(Home) / 3(抓取) / 0(紧急归零) / ESC(退出)

**长按机制：** 按住控制键超过 0.3 秒进入连续运动模式（15Hz），松开立即停止。

### SSH 远程控制（d1 无键盘时）

```bash
python3 piper_ctrl_moveJ_keyboard_ssh.py
```

此版本不需要 `pynput`，直接读取 SSH 终端按键。按键表同上，按住不放终端自动重复 -> 连续运动。Ctrl+C 退出。

### D1 遥控器控制

参照 `DDTRobot/airbot_joy` 的 ROS 2 Joy 映射，可通过 D1/TITA 遥控器控制 Piper：

```bash
cd piper_control
source /opt/ros/humble/setup.bash
source /opt/d1_ros2/namespace.sh
ros2 topic list | grep joy


# 确认轴向和模式正确后连接 can1
python3 example/teleop/betafpv_piper_teleop.py 
```

运行前在遥控器菜单选择 `use-sdk mode`为`true`。完整模式表和参数见
`piper_control/CONTROL_README.md`，分阶段实机测试流程见
`piper_control/BETAFPV_PIPER_TEST_README.md`。

---
### 一键启动
```
cd piper_D1_adaption
./start_piper_teleop.sh 
```

## 常见问题

**Q: `ip link show type can` 只有 can0，没有 can1？**

A: USB-CAN 适配器没插紧或没插对。重新拔插，用 `cat /sys/kernel/debug/usb/devices` 确认设备树中出现了 `gs_usb`。

**Q: `candump can1` 没有 Piper 帧？**

A: Piper 没上电或 CAN 线松了。检查 Piper 电源和 CAN 端子连接。

**Q: 键盘脚本报 `CAN socket can1 does not exist`？**

A: 脚本里写死了 `can0`，但 Piper 在 `can1` 上。执行：
```bash
sed -i 's/"can0"/"can1"/g' piper_sdk/piper_ctrl_moveJ_keyboard.py
```

## 接口速查表

| 接口 | 类型 | 用途 |
|------|------|------|
| `can0` | 板载 CAN | d1 电机控制 |
| `can1` | USB-CAN | Piper 机械臂 |
