# d1-follow-control

D1 机器人跟随控制包 — 基于 Intel D435i 深度相机与uwb的智能跟随功能。

---

## 安装

### 第一种方式，从源码构建

```bash
git clone <repo-url>
cd d1-follow-control
bash build_deb.sh
```

### 第二种方式，直接安装 deb 包

```bash
sudo apt install ./d1-follow-control_1.0.deb
```

### 卸载

```bash
sudo apt remove d1-follow-control
```

> 后续不需要该功能时建议卸载，此包会占用 SDK mode。

---

## 使用方法

安装完成后，打开 **SDK mode** 即可进入智能跟随模式。

> **请在空旷测试区域测试。** 由于相机视野有限，机器狗周围仍存在较大盲区，存在一定碰撞风险，请自行排查并承担相关风险。

---

## 注意事项

**请勿在玻璃和高反光物体附近测试。**

D435i 使用主动红外结构光 + 双目立体视觉（左右红外相机捕捉 IR 投影图案，通过视差计算深度），以下场景会导致深度数据异常：

| 场景类型 | 原因 | 典型案例 |
|----------|------|----------|
| **玻璃（透明材质）** | IR 光直接穿透，相机捕获的是玻璃后方物体，深度值无效或错误 | 玻璃门、水族箱、透明塑料容器 |
| **强反光物体（镜面/金属抛光面）** | IR 光被镜面反射到其他方向，双目相机无法接收有效反射，深度值偏大或无效 | 镜子、不锈钢表面、光滑瓷砖 |

---

## 参数说明

控制代码位于：`deb-package/opt/d1-follow-control/d1_follow_d435i.py`

### 基础参数

| 参数 | 说明 |
|------|------|
| `self.target_distance` | 目标跟随距离，靠近到该距离后停止 |
| `self.kp_distance` | 跟随速度比例系数，调大加快 / 调小减慢 |
| `self.kp_angle` | 转向速度比例系数，调大加快 / 调小减慢 |
| `self.max_linear_speed` | 最高线速度（m/s） |
| `self.max_angular_speed` | 最高角速度（rad/s） |
| `self.distance_deadzone` | 到位后轻微抖动时，适当加大此值 |
| `self.safe_distance` | 避障安全距离阈值 |
| `self.turning_forward_duration` | 跨越障碍的前行时长，理论值 = （机身长度 + 障碍垂直距离）/ 速度 |
| `self.smooth_alpha` | 平滑系数，控制每帧速度变化比例，避免速度突变（默认 `0.6`） |

### 高速跟随配置（最高 3 m/s）

默认最高速为 1.5 m/s，如需切换至 3 m/s 高速跟随，参考以下配置：

```python
self.target_distance = 1.8
self.max_linear_speed = 3.0
self.max_angular_speed = 3.0
self.safe_distance = 1.6
self.turning_forward_duration = 0.8
```

> - 提高 `target_distance`：避免高速下因惯性停止不及时而发生碰撞。
> - 提高 `safe_distance`：延长避障距离，便于高速下及时避障。
>
> **注意：** 高速模式请在空旷区域测试，路面宽度理论上需大于 `safe_distance × 2`，否则会频繁判断两侧存在障碍并进入避障模式。
