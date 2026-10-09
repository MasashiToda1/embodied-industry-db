# hightorque_robot C++ 使用文档

## 1. 项目概览

`hightorque_robot` 是一个面向真实硬件的 C++ 电机控制 SDK。应用层负责规划目标和控制周期，SDK 负责把目标发送到对应的 CAN 通道，并将电机反馈整理成可读取的状态。

项目的主要对象及职责如下：

- `CanPort`：核心实现对象，对应一个 CAN 通道，负责命令组织、发送和反馈接收；
- `Robot`：上层封装对象，根据 YAML 配置创建并统一管理多个 `CanPort` 和电机；
- `Motor`：依赖 YAML 中的电机配置，由 `Robot` 根据配置创建；它不包含独立通信实现，只指向一个 `CanPort` 并保存电机 ID，调用时将请求转交给该 `CanPort`。

SDK 内部会持续接收反馈；用户只需按周期设置目标、发送命令并读取状态。

**注意事项：**

- C++11 或更高版本，CMake 3.5+。
- 一块通信板包含 7 个 CAN 通道；SDK 按 CAN 通道组织资源，`canport_id` 表示 CAN 通道编号，不是通信板编号。
- 通信板由 SDK 自动识别和连接，无需在程序中手动指定串口。
- Linux 下若串口权限不足，可直接为对应设备授予读写权限，例如：`sudo chmod a+rw /dev/ttyACMX`（设备编号按实际情况替换）。
- 使用前确认通信板、CAN 通道、电机供电、FDCAN 接线和电机 ID 正确。
- 首次测试应使用低速、小范围目标，并准备独立的急停或断电手段。
- 软件 `stop()` 只能发送正常停止命令，不能替代硬件安全装置。

创建 `Robot` 或 `CanPort` 时会完成设备初始化，因此应在设备准备好后再创建对象。

## 2. 硬件与接线

### 2.1 硬件准备

| ![主控盒子](data/hw_stm32h730_board.png) | ![XT60公口线材](data/hw_xt60_cable.jpeg) | ![XT30(2+2)线材](data/hw_xt30_cable.jpg) |
| --- | --- | --- |
| 主控盒子 | XT60公口线材一根 | XT30(2+2)线材一根 |
| ![高擎新款电机（5036-02）](data/hw_motor_5036_02.png) | ![24-48V直流稳压电源](data/hw_power_supply_24v.jpeg) |  |
| 高擎新款电机（此处为5036-02电机） | 24-48V直流稳压电源一个 |  |

### 2.2 接线

1. **连接电源**

   将24V电源连接至主控盒子上并且上电。

   ![连接电源](data/wiring_connect_power.png)

   上电后红灯常亮，蓝灯闪烁。

   ![上电后红灯常亮、蓝灯闪烁](data/wiring_power_led.png)

2. **将主控盒子与电机连接**

   ![主控盒子与电机连接](data/wiring_board_to_motor.png)

3. **给电机上电**

   1. 按下按键，打开 CAN1-7 的通道供电；
   2. 电机底部供电蓝灯亮起。

   ![给电机上电](data/wiring_motor_power_on.png)

4. **运行 `./motors_run` 后的现象**

   运行 `./motors_run`，电机在位置、速度、加速度模式下以 0.314 rad/s 的速度往复运动。

   ![运行 ./motors_run 现象](data/wiring_motors_run.gif)

## 3. 快速上手与设备检测

先在 **SDK 根目录**（即包含 `CMakeLists.txt` 的目录）完成编译：

```bash
mkdir -p build      # 新建独立构建目录，避免污染源码
cd build
cmake ..            # 生成 Makefile，并自动拉取/编译 serial、yaml-cpp 等依赖
```
![cmake  编译输出](data/1.png)

```bash
make -j4            # 并行编译（-j4 为 4 线程，可按本机 CPU 核数调整）
```

![cmake 与 make 编译输出](data/2.png)


所有示例程序（如 `motors_feedback`、`motors_run` 等）会生成在 `build/` 目录下。编译完成后，**继续在该 `build/` 目录内**进行设备检测。首次使用建议采用仓库默认的单电机配置：`robot_param/robot_config.yaml` 指向 `1dof_params.yaml`。确认电机和机械结构已固定、急停可用后，运行只读反馈示例：

```bash
./motors_feedback
```

该示例不下发运动目标，只主动请求并打印电机反馈。输出类似：

```text
ID:  1, mode: ..., fault: 0, pos: ..., vel: ..., tor: ...
```

重点确认：

- SDK 能自动识别并初始化设备；
- `ID` 与实际电机 ID 一致；
- `fault` 为 `0`；
- `pos` 为有效位置，而不是 `999.0`。

反馈正常后，确认运动范围安全，再运行小范围往复运动示例：

```bash
./motors_run
```

该示例让电机在 `+0.314 rad` 和 `-0.314 rad` 之间往复转动，速度约为 `0.314 rad/s`、加速度约为 `3.14 rad/s²`。发现方向、位置或声音异常时，应立即使用急停或断电。两个示例都可用 `Ctrl+C` 退出。

运行过程中如出现 SDK 报错，请参阅第 11 节。

## 4. 编译与集成

### 方式一：在 SDK 根目录直接构建（含示例）

进入 **SDK 根目录**（即包含 `CMakeLists.txt` 的目录），执行：

```bash
mkdir -p build      # 新建独立构建目录（推荐，避免污染源码）
cd build
cmake ..            # 生成 Makefile，并自动拉取/编译 serial、yaml-cpp 等依赖
make -j4            # 并行编译（-j4 为 4 线程，可按本机 CPU 核数调整）
```

构建完成后，所有示例程序（`motors_run`、`canport_run` 等）会生成在 `build/` 目录下，直接运行即可，例如 `./motors_run`。

> 说明：再次构建无需删除 `build/`，直接重新执行 `make -j4`（CMake 会自动检测改动增量编译）；如需彻底清理，删除 `build/` 目录后重跑上述步骤。

### 方式二：集成到自己的 CMake 工程

```cmake
add_subdirectory(path/to/hightorque_robot)
add_executable(my_robot main.cpp)
target_link_libraries(my_robot PRIVATE hightorque_robot)
```

应用程序包含 `robot.h` 或 `canport.h` 即可使用公共接口；依赖库由 CMake 目标传递。

## 5. 示例程序

示例位于 `example/cpp/`，编译后从 `build/` 运行：

示例按使用层级分为两类：

- `motors_*`：使用 `Robot + Motor`，从 YAML 加载多个 CAN 通道和电机，适合完整机器人配置；
- `canport_*`：直接使用 `CanPort`，在代码中指定一个 CAN 通道及其电机 ID，适合单通道测试或自行管理配置。

两类示例的控制效果基本对应，区别在于电机和 CAN 通道的管理方式。

| 示例 | 说明 |
| --- | --- |
| `motors_feedback`、`canport_feedback` | 查询并打印反馈，不主动下发运动目标 |
| `motors_move_zero`、`canport_set_zero` | 以限制速度和加速度移动到零位置 |
| `motors_run`、`canport_run` | 小范围往复运动 |
| `motors_set_zero`、`canport_move_zero` | 执行电机零位重置流程 |

快速检测建议使用 `motors_feedback` 和 `motors_run`；其他示例应在确认设备和运动范围安全后再使用。

## 6. 机器人配置

`Robot` 初始化需要两个 YAML 文件：

1. **配置索引文件**：通常命名为 `robot_config.yaml`，通过 `param_file` 指向机器人参数文件；
2. **机器人参数文件**：定义机器人名称、CAN 通道数量以及各通道上的电机。

配置索引文件示例：

```yaml
param_file: "multi_params.yaml"
```

`param_file` 使用相对路径时，以配置索引文件所在目录为基准解析。

机器人参数文件示例（2 个 CAN 通道，电机数量分别为 2 和 3）：

```yaml
robot:
  robot_name: "Multi_Channel_Robot"
  canport_num: 2
  canport:
    canport_1:
      canport_id: 1
      motor_num: 2
      motor:
        motor_1:
          id: 1
          name: "left_joint"
        motor_2:
          id: 2
          name: "right_joint"
    canport_2:
      canport_id: 2
      motor_num: 3
      motor:
        motor_1:
          id: 1
          name: "left_arm"
        motor_2:
          id: 2
          name: "right_arm"
        motor_3:
          id: 3
          name: "gripper"
```
![yaml](data/3.png)

主要字段：

| 字段 | 作用 |
| --- | --- |
| `robot_name` | 机器人名称 |
| `canport_num` | CAN 通道数量 |
| `canport_id` | CAN 通道编号，从 1 开始 |
| `motor_num` | 该 CAN 通道的电机数量 |
| `id` | 电机编号，同一 CAN 通道内不可重复 |
| `name` | 电机或关节名称 |

`canport_num` 和 `motor_num` 应与配置内容一致。`Robot` 按 YAML 中 CAN 通道节点的顺序创建 CAN 通道 1、2、3……，因此 `canport_id` 应从 `1` 开始连续填写，并与节点顺序一致。同一 CAN 通道内的电机 ID 不可重复；不同 CAN 通道可以使用相同的电机 ID，因为完整标识是 `(canport_id, id)`。仓库中的 `robot_param/robot_config.yaml`、`1dof_params.yaml` 和 `70dof_params.yaml` 可作为配置参考。正式程序建议显式传入配置文件路径：

```cpp
#include "robot.h"

Robot robot("/path/to/robot_config.yaml");
```

配置加载报错时，请参阅第 11 节的 SDK 错误输出。

## 7. `Robot` 构造与初始化

创建 `Robot` 时会自动完成以下步骤：

1. 读取配置索引文件，并加载 `param_file` 指向的机器人参数文件；
2. 按 YAML 中 CAN 通道节点的顺序创建对应的 `CanPort`；
3. 根据每个通道下的电机配置创建 `Motor`，建立 CAN 通道、电机 ID 和名称的绑定；
4. 自动识别并连接通信设备，初始化 CAN 通道；
5. 获取通信版本，检查通信通道和电机配置；
6. 查询电机固件版本、型号和初始状态。

构造函数完成后，`Robot` 才可以用于控制。建议先使用单通道、单电机配置完成初始化和反馈检测，再逐步增加 CAN 通道和电机数量。

## 8. 接口层次

### 8.1 `CanPort`：按 CAN 通道操作

不使用 YAML 或需要自行管理配置时，可直接创建：

```cpp
#include "canport.h"

CanPort can_port(1, {1, 2});
can_port.pos_vel_acc(1, 0.0f, 0.1f, 0.5f);
can_port.send();
```

第一个参数是 CAN 通道编号，列表是该通道上的电机 ID。

### 8.2 `Robot`：机器人级接口

`Robot` 的职责：

- 根据 YAML 配置创建并封装多个 `CanPort`；
- 统一管理 CAN 通道和电机；
- 根据 YAML 中 CAN 通道节点的顺序，以及电机 `id` 和 `name` 创建并绑定 `Motor`；
- 将控制请求转发到对应的 `CanPort`；
- 提供按 CAN 通道 ID + 电机 ID 的直接访问方式，以及 `robot.motors` 电机集合。

```cpp
Robot robot("/path/to/robot_config.yaml");

// 直接按“CAN 通道 ID + 电机 ID”控制
robot.pos_vel_acc(1, 1, 0.0f, 0.1f, 0.5f);
robot.send();
```

### 8.3 `Motor`：电机级接口

`Motor` 的特点：

- 由 `Robot` 读取 YAML 配置后创建，通道和电机 ID 均来自配置；
- `Motor` 本身不解析 YAML，也不独立管理配置文件；
- 不包含独立的通信或控制实现；
- 指向所属的 `CanPort`，并绑定一个电机 ID；
- 调用接口时，将请求转发给 `CanPort`，由 `CanPort` 完成实际处理和发送；
- 提供位置、速度、力矩、组合控制、停止、制动、软重启和反馈读取接口。

```cpp
Robot robot("/path/to/robot_config.yaml");

for (Motor& motor : robot.motors)
    motor.pos_vel_acc(0.0f, 0.1f, 0.5f);

robot.send();
```

`Robot` 加载配置后，为每个 `motor` 节点生成一个 `Motor` 对象：父级 CAN 通道节点的顺序决定该对象属于哪个 CAN 通道，节点中的 `id` 决定该对象控制哪个电机，`name` 保存为该电机的名称。`robot.motors` 是这些对象按配置顺序组成的集合。

注意：`canport_1`、`motor_1` 等只是 YAML 的组织键名；当前版本以 CAN 通道节点顺序映射通道，因此 `canport_id` 必须与该顺序保持一致，电机则按 `id` 映射。

```cpp
robot.motors[0];  // canport_1.motor_1：CAN 通道 1，电机 ID 1
robot.motors[1];  // canport_1.motor_2：CAN 通道 1，电机 ID 2
robot.motors[2];  // canport_2.motor_1：CAN 通道 2，电机 ID 1
robot.motors[3];  // canport_2.motor_2：CAN 通道 2，电机 ID 2
robot.motors[4];  // canport_2.motor_3：CAN 通道 2，电机 ID 3
```

因此，两种调用方式指向同一个电机：

```cpp
robot.motors[4].position(0.0f);       // 通过 Motor 对象
robot.position(2, 3, 0.0f);            // 通过“CAN 通道 ID + 电机 ID”
robot.send();
```

不同 CAN 通道可以使用相同的电机 ID；完整定位需要同时提供 CAN 通道 ID 和电机 ID。

## 9. 控制与反馈

常用控制接口如下：

| 接口 | 用途 | 说明 |
| --- | --- | --- |
| `position` | 位置控制 | 以最大速度和最大加速度移动到指定位置 |
| `velocity` | 速度控制 | 以最大加速度加速到指定速度 |
| `torque` | 力矩控制 | 纯力矩控制 |
| `vel_acc` | 速度/加速度控制 | 以指定加速度加速到指定速度 |
| `pos_vel_acc` | 位置/速度/加速度控制 | 以指定最大速度和指定加速度，按梯形速度曲线（加速—匀速—减速）移动到指定位置 |
| `pos_vel_MAXtqe` | 带最大力矩限制的位置控制 | 以最大加速度加速到指定速度后，移动到指定位置（全程不超过设置的最大力矩） |
| `pos_vel_tqe_kp_kd` | 位置、速度、力矩及 PID 参数控制 | MIT 模式；输出力矩 = 位置偏差 × Kp + 速度偏差 × Kd + 前馈力矩 |
| `stop` | 停止电机运动 | 三相悬空，电机可自由转动 |
| `brake` | 对电机执行制动 | 三相接地，阻尼刹车 |
| `reset` | 电机软重启，（唯一一个不携带状态查询的指令） |  |
| `motor_zero_pos_reset` | 执行零位重置流程；返回 `0` 表示成功，非 `0` 表示失败 |  |

控制接口先准备当前周期的目标，`send()` 才真正发送。`stop()`、`brake()` 和 `reset()` 同样需要随后调用 `send()`。

三种对象的调用方式不同，但最终都由 `CanPort` 完成实际处理：

| 对象 | 控制调用形式 | 发送方式 | 状态读取 |
| --- | --- | --- | --- |
| `CanPort` | `can_port.pos_vel_acc(id, pos, vel, acc)` | `can_port.send()` | `can_port.get_motor_state(id)` |
| `Robot` | `robot.pos_vel_acc(can_port_id, id, pos, vel, acc)` | `robot.send()`（发送所有 CAN 通道缓存） | `robot.get_motor_state(can_port_id, id)` |
| `Motor` | `motor.pos_vel_acc(pos, vel, acc)` | 通过所属 `CanPort` 准备缓存，再由所属 `Robot` 或 `CanPort` 调用 `send()` | `motor.get_motor_state()` |

`Motor` 不提供独立的 `send()`；它只把 控制报文 转交给所指向的 `CanPort`（缓存）。

停止、制动和软重启的作用范围也不同：
`CanPort::stop()`、`brake()`、`reset()` 作用于该通道全部电机；
带 `id` 参数时作用于单个电机；
`Robot` 的无参版本作用于所有 CAN 通道；
带 `can_port_id` 和 `id` 时作用于指定电机；
`Motor` 版本只作用于自身；

`CanPort::motor_zero_pos_reset()` 和 `Robot::motor_zero_pos_reset()` 返回 `uint8_t` 状态码：`0` 表示成功，非 `0` 表示失败。`Robot` 会完成所有 CAN 通道的重置；任一通道失败时返回失败。

反馈机制与接口：

**除 `reset`（软重启）外，所有控制模式都自带状态查询。** 因此，控制命令发送后即可等待并读取反馈，不需要每个周期另外发送查询命令。

```cpp
robot.pos_vel_acc(1, 1, 0.0f, 0.1f, 0.5f);
robot.send();

motor_state_t* state = robot.get_motor_state(1, 1);
if (state != nullptr) {
    // state->position / velocity / torque
    // state->mode / fault
}
```

`request_motor_state()` 用于不下发控制目标时主动查询反馈，例如只读监控或控制暂停阶段。状态由 SDK 异步更新，应用应在每次读取后及时使用或复制。

三种对象的主动查询范围分别为：`CanPort` 查询所属通道的电机，`Robot` 查询所有 CAN 通道的电机，`Motor` 将请求转交给所属 `CanPort`。

`motor_state_t` 还包含电机名称、型号、固件版本和反馈更新时间等信息。执行 `reset` 后应等待电机重新上线，再通过后续控制命令或 `request_motor_state()` 获取有效反馈。

CAN 通道状态可通过 `get_can_port_state()` 获取，用于判断 FDCAN 是否正常、是否存在错误或警告。

## 10. 单位与控制周期

默认单位为：

| 数据 | 单位 |
| --- | --- |
| 位置 | rad |
| 速度 | rad/s |
| 加速度 | rad/s² |
| 力矩 | N·m |
| `kp` | N·m/rad（力矩/位置） |
| `kd` | N·m/(rad/s)（力矩/速度） |

典型控制循环：

```text
读取上一周期的 motor_state_t（按需）
    ↓
根据反馈计算或规划下一目标
    ↓
调用控制接口并执行 send()
    ↓
SDK 自动查询并异步更新电机反馈
    ↓
进入下一控制周期
```

除 `reset` 软重启外，控制命令本身会携带状态查询，因此常规控制循环不需要额外调用 `request_motor_state()`；该接口仅用于没有控制目标时主动查询反馈。控制周期由应用决定；示例采用约 1 kHz。实际系统应根据电机、通信负载和上层控制器要求选择周期，并持续检查 `fault` 和 CAN 通道状态。

## 11. 退出、错误信息与故障排查

正常退出前：

```cpp
robot.stop();
robot.send();
```

### 11.1 SDK 错误输出

下表集中列出 SDK 在构造初始化和运行过程中输出的常见错误。其中 `%d`、`...` 等内容会替换为运行时的通道号、数量或错误详情。

| 实际输出 | 含义与处理方法 |
| --- | --- |
| `Error: 'robot' is missing in configuration file.` | 参数文件缺少 `robot` 根节点；检查参数文件内容。 |
| `Error: 'robot....' is missing in configuration ...` | 配置字段缺失；检查对应字段及层级。 |
| `Error: Failed to convert '...' to the required type ...` | 配置字段类型错误；检查数字、字符串等 YAML 类型。 |
| `can_port_id err: got ..., must be >= 1` | 直接创建 `CanPort` 时传入的 CAN 通道 ID 小于 1；修正构造参数。 |
| `map_id_name err: got ..., valid range [1, 30]` 或 `map_id_name err: id ..., valid range [1, 30]` | 当前 CAN 通道的电机数量或 ID 超出 `1~30`；修正 `motor_num` 和电机 `id`。 |
| `no comm board serial ports found` | SDK 未找到自动识别的通信设备；检查设备连接、供电和 Linux 串口权限。 |
| `[CanPort%d] serial open err: ...` | 对应设备无法打开；检查 `/dev/ttyACMX` 是否存在并授予读写权限。 |
| `[CanPort%d] not enough serial ports: found ..., need ...` | 配置需要的 CAN 通道数量超过已识别数量；检查设备连接和通道配置。 |
| `[CanPort%d] comm board version too low: ..., require >= v6.0.0` | 通信板版本过低；升级到 `v6.0.0` 或更高版本。 |
| `[CanPort%d] failed to get comm board version` 或 `[CanPort%d] comm init err` | 通信板初始化失败；检查设备状态、连接和供电。 |
| `[CanPort%d] motor fw version/model check err, ...` | 电机版本或型号查询失败；检查电机供电、FDCAN 接线和电机 ID。 |
| `can_port_id err: got ..., valid range [...]` | 调用 `Robot` 时传入了不存在的 CAN 通道 ID；检查通道编号。 |
| `[CanPort%d] motor[%d] not found` | 指定的电机未配置在该 CAN 通道；检查通道 ID 和电机 ID。 |
| `[CanPort%d] serial send err: ...` | 命令发送失败；检查串口设备和连接状态。 |
| `[CanPort%d] FDCAN fault: ..., rx_err: ..., tx_err: ...` | CAN 通道报告错误；检查总线接线、终端电阻、供电和设备状态。 |

运行状态异常时，也可结合以下现象判断：

| 运行现象 | 处理方向 |
| --- | --- |
| `motor_state_t::fault` 非零 | 根据电机错误码检查电机状态。 |
| 位置变为 `999.0f` | 检查反馈是否超时，以及电机供电和 FDCAN 接线。 |
| 控制命令没有效果 | 确认控制接口调用后执行了 `send()`。 |

## 12. ROS 示例

### 12.1 ROS1 包结构与编译

ROS1 示例工作空间位于 `example/ros1/`，包位于 `example/ros1/src/hightorque_robot_ros1_example/`。8 个源文件与 `example/cpp/` 同名，每个文件都是独立的 ROS 节点，并在原有控制逻辑基础上以 100 Hz 发布 `motor_states`。

先在终端中加载 ROS 环境并编译：

```bash
cd /path/to/hightorque_robot/example/ros1
source /opt/ros/noetic/setup.bash
catkin_make
source devel/setup.bash
```

编译只需执行一次；修改代码后重新执行 `catkin_make` 即可。每个 ROS1 工作空间都应单独构建，不要把 ROS2 包放入该工作空间。

### 12.2 启动 ROS Master

ROS1 节点启动前必须先有 ROS Master。打开第一个终端并保持运行：

```bash
source /opt/ros/noetic/setup.bash
roscore
```

再打开第二个终端，加载 ROS 和当前工作空间环境：

```bash
source /opt/ros/noetic/setup.bash
source /path/to/hightorque_robot/example/ros1/devel/setup.bash
```

如果没有启动 `roscore`，运行节点时会看到 `Failed to contact master at [127.0.0.1:11311]`，此时节点无法注册话题。

### 12.3 运行示例

控制示例会访问真实电机，同一时间只运行一个控制节点。确认设备和机械结构安全后，在第二个终端运行：

| 节点 | 作用 |
| --- | --- |
| `rosrun hightorque_robot_ros1_example canport_feedback` | 直接创建 CAN 通道 1，查询电机 ID 1 的反馈 |
| `rosrun hightorque_robot_ros1_example canport_move_zero` | 直接创建 CAN 通道 1，执行电机零位重置流程 |
| `rosrun hightorque_robot_ros1_example canport_run` | 直接控制 CAN 通道 1 的电机 1、2、3，在 ±0.314 rad 间往复 |
| `rosrun hightorque_robot_ros1_example canport_set_zero` | 直接控制 CAN 通道 1 的电机 1、2、3，持续发送零位置目标 |
| `rosrun hightorque_robot_ros1_example motors_feedback` | 从 YAML 加载 `Robot`，只查询所有电机反馈 |
| `rosrun hightorque_robot_ros1_example motors_move_zero` | 从 YAML 加载 `Robot`，以限制速度移动到零位置 |
| `rosrun hightorque_robot_ros1_example motors_run` | 从 YAML 加载 `Robot`，让所有电机在 ±0.314 rad 间往复 |
| `rosrun hightorque_robot_ros1_example motors_set_zero` | 从 YAML 加载 `Robot`，执行所有电机零位重置流程 |

停止节点使用 `Ctrl+C`。示例退出前会调用 `stop()` 和 `send()`；紧急情况仍应使用硬件急停或断电。

### 12.4 配置文件参数

`canport_*` 示例在代码中直接写明 CAN 通道和电机 ID，不读取 YAML。`motors_*` 示例默认使用包安装的 `robot_param/robot_config.yaml`，也可以通过 ROS 私有参数指定入口 YAML：

```bash
rosrun hightorque_robot_ros1_example motors_feedback \\
  _robot_config:=/absolute/path/to/robot_config.yaml
rosrun hightorque_robot_ros1_example motors_run \\
  _robot_config:=/absolute/path/to/robot_config.yaml
```

`robot_config.yaml` 中的 `param_file` 按入口文件所在目录解析，具体 YAML 格式见第 6 节。修改配置后重新启动节点即可生效。

### 12.5 状态话题

8 个 ROS1 示例均发布：

```text
/motor_states
```

消息类型为 `hightorque_robot_ros1_example/MotorState`，每条消息对应一个电机，字段为 `can_port_id`、`id`、`mode`、`fault`、`position`、`velocity` 和 `torque`。

查看状态：

```bash
rostopic list
rostopic info /motor_states
rostopic echo /motor_states
rostopic hz /motor_states
```

其他 ROS 节点只需订阅 `hightorque_robot_ros1_example/MotorState`，即可通过节点间通信获取电机数据，不需要直接访问 SDK。

### 12.6 ROS1 常见问题

| 现象 | 处理方法 |
| --- | --- |
| `Failed to contact master at [127.0.0.1:11311]` | 在另一个终端启动 `roscore`，并确认两个终端都加载了同一 ROS 环境。 |
| `package 'hightorque_robot_ros1_example' not found` | 重新执行 `source /path/to/hightorque_robot/example/ros1/devel/setup.bash`。 |
| `Cannot locate node ...` | 先在 `example/ros1` 下执行 `catkin_make`，确认对应目标构建成功。 |
| 能看到节点但没有 `/motor_states` | 确认节点仍在运行，并检查 `rostopic info /motor_states`；SDK 初始化错误请查看第 11 节。 |
| 节点启动后 SDK 报错 | 按第 11 节的实际 SDK 输出排查通信板、串口、CAN 接线和 YAML 配置。 |

### 12.7 ROS2 包结构与编译

ROS2 示例工作空间位于 `example/ros2/`，包位于
`example/ros2/src/hightorque_robot_ros2_example/`。8 个源文件与
`example/cpp/` 同名，每个文件都是独立的 ROS2 节点；节点以 100 Hz 发布单个电机状态。

在终端中加载 ROS2 环境并直接编译工作空间：

```bash
cd /path/to/hightorque_robot/example/ros2
source /opt/ros/humble/setup.bash   # 按实际 ROS2 发行版替换 humble
colcon build --packages-select hightorque_robot_ros2_example
source install/setup.bash
```

ROS2 工作空间独立编译，不需要把 ROS1 包放入其中，也不会改变项目根目录的普通 CMake 构建。
修改示例代码或消息定义后，重新执行 `colcon build` 并重新加载 `install/setup.bash`。

### 12.8 运行 ROS2 示例

ROS2 不需要启动 ROS1 的 `roscore`。控制示例会访问真实电机，同一时间只运行一个控制节点；运行前确认设备和机械结构安全。

| 节点 | 作用 |
| --- | --- |
| `ros2 run hightorque_robot_ros2_example canport_feedback` | 直接创建 CAN 通道 1，查询电机 ID 1 的反馈 |
| `ros2 run hightorque_robot_ros2_example canport_move_zero` | 直接创建 CAN 通道 1，执行电机零位重置流程 |
| `ros2 run hightorque_robot_ros2_example canport_run` | 直接控制 CAN 通道 1 的电机 1、2、3，在 ±0.314 rad 间往复 |
| `ros2 run hightorque_robot_ros2_example canport_set_zero` | 直接控制 CAN 通道 1 的电机 1、2、3，持续发送零位置目标 |
| `ros2 run hightorque_robot_ros2_example motors_feedback` | 从 YAML 加载 `Robot`，查询所有电机反馈 |
| `ros2 run hightorque_robot_ros2_example motors_move_zero` | 从 YAML 加载 `Robot`，以限制速度移动到零位置 |
| `ros2 run hightorque_robot_ros2_example motors_run` | 从 YAML 加载 `Robot`，让所有电机在 ±0.314 rad 间往复 |
| `ros2 run hightorque_robot_ros2_example motors_set_zero` | 从 YAML 加载 `Robot`，执行所有电机零位重置流程 |

停止节点使用 `Ctrl+C`。示例退出前会调用 `stop()` 和 `send()`；紧急情况仍应使用硬件急停或断电。

### 12.9 ROS2 配置文件参数

`canport_*` 示例在源文件中直接指定 CAN 通道和电机 ID，不读取 YAML。`motors_*` 示例使用
`Robot` 和 `Motor`，默认加载安装到包共享目录的 `robot_param/robot_config.yaml`，也可以通过
ROS2 参数指定入口 YAML：

```bash
ros2 run hightorque_robot_ros2_example motors_feedback --ros-args \
  -p robot_config:=/absolute/path/to/robot_config.yaml
ros2 run hightorque_robot_ros2_example motors_run --ros-args \
  -p robot_config:=/absolute/path/to/robot_config.yaml
```

入口 YAML 及其 `param_file` 引用的详细参数文件按 SDK 的配置规则解析，具体格式见第 6 节。
修改配置后重新启动节点即可生效。

### 12.10 ROS2 状态话题

8 个 ROS2 示例均发布：

```text
/motor_states
```

消息类型为 `hightorque_robot_ros2_example/msg/MotorState`，每条消息对应一个电机，字段为：

| 字段 | 含义 |
| --- | --- |
| `can_port_id` | CAN 通道 ID |
| `id` | 电机 ID |
| `mode` | 电机模式 |
| `fault` | 电机故障码 |
| `position` | 位置 |
| `velocity` | 速度 |
| `torque` | 力矩 |

查看状态：

```bash
ros2 topic list
ros2 topic info /motor_states
ros2 topic echo /motor_states
ros2 topic hz /motor_states
```

其他 ROS2 节点订阅该消息即可通过节点间通信获取电机数据，不需要直接访问 SDK。

### 12.11 ROS2 常见问题

| 现象 | 处理方法 |
| --- | --- |
| `Package 'hightorque_robot_ros2_example' not found` | 重新执行 `source /path/to/hightorque_robot/example/ros2/install/setup.bash`。 |
| `No executable found` 或找不到某个示例 | 在 `example/ros2` 下重新执行 `colcon build --packages-select hightorque_robot_ros2_example`，然后重新加载 `install/setup.bash`。 |
| 找不到 `/motor_states` | 确认节点仍在运行，并检查 `ros2 topic list`；SDK 初始化错误按第 11 节的实际输出排查。 |
| `robot_config` 参数指定后仍无法初始化 | 确认路径是入口 YAML 的绝对路径，且入口文件引用的详细参数文件存在；SDK 报错按第 11 节排查。 |
| 节点启动后 SDK 报错 | 按第 11 节的实际 SDK 输出排查通信板、串口、CAN 接线和 YAML 配置。 |
