# LinkerBot Arm Python SDK

English | [简体中文](README_zh.md)

All four arm models use `CANTransport` by default. Set
`LINKERBOT_ARM_TRANSPORT=dispatcher` to explicitly use the low-level backend.
Both backends require the [current transport source](requirements/transport.txt).
Arm calls remain unchanged; failed connections require closing and recreating the arm. See the
[backend guide](docs/TRANSPORT.md) for installation, recovery and validation scope.

Python SDK for **A7, A7lite, P7 and H75** robotic arms, with joint control, feedback and
forward/inverse kinematics. Requires Python 3.10+. Install `linkerbot-arm` and import `linkerbot_arm`.

## Installation

The base SDK requires NumPy >=1.24, SciPy >=1.10, Pydantic 2.x and
`linkerbot-transport[can]`. The source repository is
[linker-bot/linkerbot-arm-python-sdk](https://github.com/linker-bot/linkerbot-arm-python-sdk),
with `main` as its default branch. The distribution and import names remain
`linkerbot-arm` and `linkerbot_arm`. To obtain and install the source from GitHub, run:

```bash
git clone --branch main https://github.com/linker-bot/linkerbot-arm-python-sdk.git
cd linkerbot-arm-python-sdk
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --force-reinstall --no-deps -r requirements/transport.txt
python -m pip install -e '.[kinetix]'
```

See the [installation guide](docs/INSTALLATION.md) for environment configuration.

All four arm constructors require Pinocchio; the current validation baseline is 4.1.0.
The `kinetix` extra declares `pin>=4.1.0` for pip dependency installation. SDK kinematics
are available with the base package when compatible Pinocchio is already present;
install it with `python -m pip install -e .`.
ROS2 environments should install the base package and compatible system Pinocchio.
See the [ROS2 guide](docs/ROS2.md) for the validated Jazzy combination and deployment lock.

## Quick start

[Configure CAN](docs/zh/src/reference/can.md), connect and power the arm, then run:

```python
from linkerbot_arm import A7

with A7(side="left", interface_name="can0") as arm:
    print(arm.get_angles())  # Seven joint angles in radians
    print(arm.get_pose())  # TCP pose
```

Replace `A7` with `A7lite`, `P7` or `H75` for other models, and use `side="right"` for a right arm.
Construction opens CAN, checks the motors and reads their initial state. The context manager closes the connection.
P7 also checks the PTM mode of joints 6 and 7. When necessary it enters Rest,
writes and saves the Flash mode, then verifies the readback; an existing PTM configuration skips writes.
Set velocity and acceleration explicitly before moving. See the [P7 reference](docs/zh/src/reference/p7/README.md).

P7 `move_j()` and `move_p()` use host-side joint acceleration/deceleration profiles.
External `_set_angles()` commands are velocity- and acceleration-limited: the first cycle holds
feedback positions, and periodic input is required to approach the target. `blocking=False`
still sends the complete host trajectory synchronously. A7lite software stops remain latched
until explicit `enable()` or successful PP `home()` recovery; cancellation or failure keeps the stop.
PP/CSP hold zero speed limits and replace pending targets with cached feedback; MIT holds use
at least Kp=20 and Kd=1. These commands do not confirm a physical stop.
`close()` waits for motion parameter restoration before closing CAN and does not disable motors.
P7 `move_l()` constrains the TCP path and does not guarantee per-joint profile limits near singularities.
See the [behavior migration notes](docs/MIGRATION.md#运动与停止行为).

H75 supports PP/CSP and brakes on joints 1/2. Use `get_currents()` for amperes;
torque conversion is unavailable. Check the upstream scaling defaults against your motor and firmware.

## Documentation

- [Installation](docs/INSTALLATION.md)
- [A7 API](docs/zh/src/reference/a7/README.md)
- [A7lite API](docs/zh/src/reference/a7lite/README.md)
- [P7 API](docs/zh/src/reference/p7/README.md)
- [H75 API](docs/zh/src/reference/h75/README.md)
- [CAN](docs/zh/src/reference/can.md)
- [Feedback freshness and lightweight state reads](docs/FEEDBACK.md)
- [ROS2](docs/ROS2.md)
- [Migration from the legacy SDK](docs/MIGRATION.md)
- [Changelog](CHANGELOG.md)

See [Development checks](DEVELOPMENT.md) for project-specific development and testing.

## Contributing and license

English and Chinese contributions are welcome. Follow the
[Linkerbot contribution guide](https://github.com/linker-bot/.github/blob/main/CONTRIBUTING.md).
Report vulnerabilities privately using the
[organization security policy](https://github.com/linker-bot/.github/blob/main/SECURITY.md).

Licensed under the [MIT License](LICENSE).
