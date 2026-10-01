# RP_Hand 6DOF

`roboparty_dexhand` 是面向 Linux 的 RP_Hand 6DOF 灵巧手 C++/Python
控制库，通过外部配置的 SocketCAN CAN-FD 接口进行通信。库提供统一的
`HandDriver` 工厂接口、运动控制和反馈读取能力。

已安装 ARM64 软件包的硬件验收流程见 [VALIDATION.md](VALIDATION.md)。

## 项目用途

使用本库可以在机器人应用中创建 RP_Hand 驱动、发送关节运动目标并读取
灵巧手反馈。日常使用顺序是先在系统中配置 CAN-FD，再按需完成一次反馈
周期配置，然后初始化驱动、控制关节，最后显式释放驱动资源。

## 支持范围

- Linux x86-64 与 AArch64；
- RP_Hand 6DOF，CAN-FD，CANopen node ID 为 `1..127`；
- Python 模块 `dexhand_py` 与 C++ 头文件 `include/hand_driver.hpp`；
- 一个进程使用一个活动的厂商 SDK 实例。

本部署只支持 RP_Hand 6DOF。唯一公开支持的模型值为
`RP_HAND_6DOF=0`。为保持 pybind 兼容性，RP_Hand 品牌发布前的枚举表示
仍被保留；同一个数值别名的 `.name`、`str()` 和 `repr()` 可能显示品牌发布
前的规范标识符。这不表示安装了过时的软件包；普通代码应使用
`HandModel.RP_HAND_6DOF`，需要数值时使用 `.value`。

## 安装

在 Debian 系统上安装 ARM64 软件包。先将目标 `.deb` 放在当前目录；下面
的命令会安全地解析一个匹配当前目录的包文件，再交给 `apt`：

```bash
(
  shopt -s nullglob
  deb_candidates=(./roboparty-dexhand_*_arm64.deb)
  if (( ${#deb_candidates[@]} != 1 )); then
    printf 'expected exactly one ARM64 package, found %d\n' \
      "${#deb_candidates[@]}" >&2
    exit 1
  fi
  sudo apt install "${deb_candidates[0]}"
)
```

文件名中的版本字段由实际构建版本决定，例如当前仓库版本是
`roboparty-dexhand_0.4.1-1_arm64.deb`；这里的版本字段就是通常所说的
`<version>`。安装后可使用已安装的 `roboparty-dexhand-config` 命令。
Debian 打包配置的安装前缀是 `/opt/roboparty`，并依赖
`roboparty-base (>= 1.0.0)`；运行 Python 前请先加载 RoboParty 基础环境。
如果当前 shell 没有该环境提供的路径设置，可显式执行：

```bash
setup_dexhand_debian() {
  local install_prefix="/opt/roboparty"
  local module module_dir
  local -a modules=()

  while IFS= read -r -d '' module; do
    modules+=("$module")
  done < <(find "$install_prefix" -type f -name 'dexhand_py*.so' -print0)
  if (( ${#modules[@]} != 1 )); then
    printf 'expected exactly one dexhand_py module, found %d\n' \
      "${#modules[@]}" >&2
    return 1
  fi

  module_dir="$(dirname -- "${modules[0]}")"
  export PATH="$install_prefix/bin:$PATH"
  export CMAKE_PREFIX_PATH="$install_prefix${CMAKE_PREFIX_PATH:+:$CMAKE_PREFIX_PATH}"
  export PYTHONPATH="$module_dir${PYTHONPATH:+:$PYTHONPATH}"
}
if setup_dexhand_debian; then
  python3 -c 'from dexhand_py import HandDriver, HandModel; print(HandModel.RP_HAND_6DOF.value)'
fi
unset -f setup_dexhand_debian
```

## Linux CAN-FD 设置

CAN-FD 接口由系统或部署脚本在库外配置。下面以 `can0` 为例，设置名义
速率 1 Mbps、数据速率 5 Mbps、采样点和同步跳转宽度后启动接口：

```bash
sudo ip link set can0 down
sudo ip link set can0 type can \
  bitrate 1000000 sample-point 0.8 sjw 4 \
  dbitrate 5000000 dsample-point 0.75 dsjw 2 fd on
sudo ip link set can0 txqueuelen 10000
sudo ip link set can0 up
ip -details -statistics link show can0
```

将命令中的 `can0` 替换为实际连接灵巧手的物理接口。库只使用已存在的
SocketCAN 接口，永远不会替应用配置速率、采样点、队列长度或接口状态。

## 首次配置反馈频率

新手、替换手、恢复出厂设置的手，或当前配置未知的手，需要完成一次
反馈周期配置；普通每次启动不需要重复执行。操作前先停止其他手控制进程，
然后执行：

```bash
roboparty-dexhand-config feedback-period apply --interface can0 --node-id 1 --milliseconds 20 --save
```

只给灵巧手本体断电再上电，然后执行查询：

```bash
roboparty-dexhand-config feedback-period show --interface can0 --node-id 1
```

查询结果中六个轴的 raw value 都必须是 `200`。如果有轴需要改变，
`apply --save` 会写入六个目标值并保存；如果六个轴已经都是 `200`，CLI
会报告 `result=already-compliant`，不会重复写入或保存。无论哪种结果，
都要给灵巧手本体断电再上电，然后运行上面的 `show` 进行确认。`20 ms`
表示两个反馈类型各自以 `50 Hz` 发送，因此合计约为 `100` 帧/秒。正常的
`init_hand()` 永远不会写入或修改持久化反馈周期参数。

## Python 使用

下面示例使用已安装的模块。它会将六个关节移动到有限的目标位置，读取
全部位置，再回到零位并再次读取。示例显式跳过回零，只适用于已经知道
参考/零位且工作空间已清空的手。新手或参考状态未知时，不要绕过回零，
请改用正常回零流程（例如 `init_hand(True, True, 5.0)`）。这不是所有启动
场景下都最安全的通用配置。真实硬件会产生运动；运行前确认手的周围没有
人员或障碍物，并准备好立即断电或停止运动。

`home_wait_time=5.0` 是最大超时，不是固定等待。驱动收到回零后的新鲜
`0x50` 位置反馈和 `0x5A` 状态反馈后，会检查六轴均已停止、无报警且接近
零位，并立即返回；超时则初始化失败并禁用电机。仅软件进程重启、手本体
没有掉电且零位可信时，可用 `init_hand(True, False, 0.0)` 快速恢复，不应
重复执行回零。

```python
import time

from dexhand_py import HandDriver, HandModel


CAN_INTERFACE = "can0"
TARGET_POSITION = 1200
TARGET_VELOCITY = 2000


def read_positions(hand, label):
    positions = [hand.get_now_position(joint) for joint in range(1, 7)]
    values = " ".join(
        f"joint{joint}={position}"
        for joint, position in enumerate(positions, start=1)
    )
    print(f"{label}: {values}")


hand = HandDriver.create_hand(
    "RP_Hand", "canfd", CAN_INTERFACE, HandModel.RP_HAND_6DOF, 1
)
initialized = False
try:
    if not hand.init_hand(True, False, 0.0):
        raise RuntimeError("init_hand failed")
    initialized = True

    hand.check_health()
    total, active = hand.get_dof()
    if active != 6:
        raise RuntimeError(f"unexpected active DOF: {active} (total={total})")
    alarms = [hand.get_now_alarm(joint) for joint in range(1, 7)]
    if any(alarm != 0 for alarm in alarms):
        raise RuntimeError(f"nonzero joint alarms: {alarms}")

    hand.set_move_no_home(1)
    for joint in range(1, 7):
        hand.set_target_position(joint, TARGET_POSITION)
        hand.set_position_velocity(joint, TARGET_VELOCITY)
    hand.move_motors(0)
    time.sleep(1.0)
    read_positions(hand, "target")

    for joint in range(1, 7):
        hand.set_target_position(joint, 0)
        hand.set_position_velocity(joint, TARGET_VELOCITY)
    hand.move_motors(0)
    time.sleep(1.0)
    read_positions(hand, "zero")
finally:
    if initialized:
        try:
            hand.set_move_no_home(0)
        finally:
            hand.deinit_hand()
    else:
        hand.deinit_hand()
```

## 选择 CAN 接口

`interface` 字符串决定 Linux 将数据发送到哪个 SocketCAN 接口。使用
`can0`、`can1`、`can2` 或 `can3` 时，只需把工厂参数或上面示例中的
`CAN_INTERFACE` 改成对应名称；库不会自动探测或选择端口。端口必须已经
连接到目标灵巧手并完成 CAN-FD 配置。

## 双手使用

支持的双手部署方式是每只手使用一个 OS 进程。厂商 SDK 每个进程只支持
一个活动实例，接收回调也是进程级资源；每个进程应传入自己负责的接口和
node ID。例如，应用脚本自行提供这两个参数时可以这样启动：

```bash
# 左手进程：物理接口 can0，node ID 1
python3 left_hand_control.py --interface can0 --node-id 1

# 右手进程：物理接口 can1，node ID 2
python3 right_hand_control.py --interface can1 --node-id 2
```

两个进程各自调用 `HandDriver.create_hand()` 并传入分配好的接口和 node ID。
`roboparty_deploy` 不会替应用自动选择 `can0`/`can1`，接口分配应由部署
配置和应用参数明确完成。

## C++ 使用

最小生命周期示例只使用公共头文件中的接口。它会初始化（包括正常回零）、
检查状态并释放驱动，不设置目标位置，也不调用 `move_motors()`。真实硬件
会启用并回零；运行前确认工作空间已清空。对于参考/零位未知的手，使用
这里的正常回零流程，不要照搬 Python 示例中的 no-home 方式：

```cpp
#include <hand_driver.hpp>

int main() {
    auto hand = HandDriver::create_hand("RP_Hand", "canfd", "can0", HAND_RP_HAND_6DOF, 1);

    int result = 1;
    try {
        if (hand->init_hand(true, true, 5.0)) {
            hand->check_health();
            int total = 0;
            int active = 0;
            hand->get_dof(total, active);
            bool alarms_clear = true;
            for (int joint = 1; joint <= 6; ++joint) {
                if (hand->get_now_alarm(joint) != 0) alarms_clear = false;
            }
            result = (active == 6 && alarms_clear) ? 0 : 1;
        }
    } catch (...) {
        hand->deinit_hand();
        throw;
    }

    hand->deinit_hand();
    return result;
}
```

## 主要 API

以下是 `HandDriver` 的公共 Python/C++ API。C++ 方法使用 `hand->method()`，
Python 方法使用 `hand.method()`。

- 创建与生命周期：`create_hand()`、`init_hand(enable_motors, home_motors,
  home_wait_time)`、`deinit_hand()`。工厂参数依次为
  `hand_type`、`interface_type`、`interface`、`hand_model`、
  `canfd_node_id`；本部署使用 `"RP_Hand"`、`"canfd"` 和
  C++ 模型常量 `HAND_RP_HAND_6DOF`；Python 使用
  `HandModel.RP_HAND_6DOF`。注意：对已初始化的驱动，重复
  `init_hand()` 仅在参数完全一致时幂等返回 `true`；参数不同
  （例如先以 `enable_motors=false` 初始化、再请求 `true`）会返回
  `false`，此时应先 `deinit_hand()` 再重新初始化。
  `home_wait_time` 是回零确认的最大超时；满足反馈条件会提前返回，传入
  `0.0` 则保留不等待、不验证回零结果的兼容行为。
- 枚举名称按语言区分：Python 使用 `HandCommType.CANFD` 和
  `HandModel.RP_HAND_6DOF`；C++ 使用 `HandCommType::CANFD` 和
  `HAND_RP_HAND_6DOF`。RP_Hand 品牌发布前版本中的标识符仍保持源码兼容，
  但新代码应使用上述公共名称。
- 运动执行：`move_motors(finger_id=0)`、`stop_motors(finger_id=0)`、
  `home_motors(finger_id=0)` 的默认 `finger_id` 是 `0`，表示广播到全部
  关节。`set_enable(finger_id, enable)` 必须显式传入 `finger_id`，但传入
  `0` 仍表示广播；`set_move_no_home(enable)` 没有 `finger_id`，只接受
  `1`（允许未完成回零时运动）或 `0`（要求先完成回零）。
- 目标参数：`set_target_position(finger_id, position)`（编码器计数）、
  `set_target_angle(finger_id, angle)`（角度）、
  `set_position_velocity(finger_id, velocity)`（计数/秒）、
  `set_max_current(finger_id, current)`（mA）。这些方法需要明确的
  `finger_id`，没有默认值；按公共/厂商约定传入 `0` 表示广播到全部关节。
  本手册示例仍显式使用关节 `1..6`，以便逐关节检查和控制。
- 反馈与状态：`get_now_position(finger_id)`、`get_now_angle(finger_id)`、
  `get_now_status(finger_id)`、`get_now_current(finger_id)`、
  `get_now_alarm(finger_id)`、`clear_alarm(finger_id)`。`clear_alarm(0)`
  清除全部关节报警；其他读取方法按指定关节返回缓存值。
- 设备信息与健康：Python 中 `total, active = hand.get_dof()` 返回总关节数
  和活动关节数；C++ 中使用 `int total, active; hand->get_dof(total, active);`。
  `get_can_name()` 返回接口名，`check_health()` 在驱动故障时抛出异常。

## 必须遵守的运行注意事项

- 启动控制程序前，先在库外配置并拉起目标 SocketCAN CAN-FD 接口；node ID
  必须与实际灵巧手一致，并避免同一总线上出现冲突的 node ID。
- 首次或配置未知的手必须先完成 20 ms 反馈周期配置并确认六个 raw value
  都为 `200`；配置命令执行期间不要运行其他手控制进程。
- `init_hand()` 返回 `false` 或抛出异常时，不要继续发送运动命令。运动前
  根据实际机构确认目标位置、速度、负载和安全边界。
- 每个成功创建的驱动都必须显式调用 `deinit_hand()`；不要把 Python 对象
  销毁或 C++ 智能指针析构当作清理替代方案。
- 双手使用时保持一手一进程，并在每个进程中明确传入自己的 interface 和
  node ID。

## 从源码构建

需要 CMake 3.15 或更新版本，以及 Python 3、pybind11、spdlog 和 fmt。仓库
已包含对应架构的底层 SDK 文件。配置、编译和安装：

```bash
cmake -S . -B build -DPython3_EXECUTABLE=/usr/bin/python3
cmake --build build --parallel
cmake --install build --prefix "$PWD/install"
```

安装后，C++ 使用 `include/hand_driver.hpp`，Python 扩展位于前缀下的
`lib/pythonX.Y/site-packages`（`X.Y` 由构建时 Python 版本决定）。使用下列
函数让当前交互 shell 同时找到 C++ package config、CLI 和 Python 模块；函数
要求前缀下恰好有一个 `dexhand_py*.so`，成功后环境变量会保留在当前 shell，
且不会手写 Python 版本号：

```bash
setup_dexhand_install() {
  local install_prefix="$PWD/install"
  local module module_dir
  local -a modules=()

  while IFS= read -r -d '' module; do
    modules+=("$module")
  done < <(find "$install_prefix" -type f -name 'dexhand_py*.so' -print0)
  if (( ${#modules[@]} != 1 )); then
    printf 'expected exactly one dexhand_py module, found %d\n' \
      "${#modules[@]}" >&2
    return 1
  fi

  module_dir="$(dirname -- "${modules[0]}")"
  export PATH="$install_prefix/bin:$PATH"
  export CMAKE_PREFIX_PATH="$install_prefix${CMAKE_PREFIX_PATH:+:$CMAKE_PREFIX_PATH}"
  export PYTHONPATH="$module_dir${PYTHONPATH:+:$PYTHONPATH}"
}
if setup_dexhand_install; then
  python3 -c 'from dexhand_py import HandDriver, HandModel; print(HandModel.RP_HAND_6DOF.value)'
fi
unset -f setup_dexhand_install
```

应用仍须在库外准备好实际的 SocketCAN 接口。

## License

RoboParty 编写的源代码采用 GPL-3.0。仓库内捆绑的厂商 SDK 头文件和二进制
文件保留其自身的许可与再分发边界；相关说明请参阅
[`thirdparty/README.md`](thirdparty/README.md)。
