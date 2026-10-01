# r1-7a_sdk
R1 robotic arm low-level control SDK (IM6014 serial bus).

### Prebuild environment
* OS  (Ubuntu 20.04 LTS or higher)
* CPU  (aarch64 and x86_64)
* Compiler  (gcc version 9.4.0)

### Environment Setup

Before building or running the SDK, ensure the following dependencies are installed:

- CMake (version 3.10 or higher)
- GCC (version 9.4.0)
- Make
- pthread

You can install the required packages on Ubuntu 20.04 with:

```bash
apt-get update
apt-get install -y cmake g++ build-essential
```

Serial access usually requires membership in the `dialout` group (or equivalent) for `/dev/ttyUSB*`.

### Build examples

To build the examples inside this repository:

```bash
mkdir build
cd build
cmake ..
make
```

Binaries are written to `bin/`:

- `test_arm_lowlevel` — low-level FOC / stop / home / goto commands
- `calibrate_joints` — joint calibration tool (URDF ↔ motor frame)

### Usage

Default serial port is `/dev/ttyUSB3`, baudrate `6000000`. Joint calibration is loaded from `config/joint_calib.txt` (path relative to the working directory; when run from `bin/`, the default `../config/joint_calib.txt` is used).

**Hold current pose (FOC):**

```bash
cd bin
./test_arm_lowlevel --foc --port /dev/ttyUSB3
```

**Move to URDF zero (home):**

```bash
./test_arm_lowlevel --home --kp 60
```

**Move to a target pose (goto):**

```bash
./test_arm_lowlevel --goto --q 0 0 0 0 0 0 0 --kp 60
```

**Other commands:** `--stop`, `--zero-torque`, `--clear`, `--reset`. Use exactly one command per run. Ctrl-C sends stop (mode 0) and exits for long-running modes.

**Calibrate joints** (pose the arm at the desired URDF zero first):

```bash
./calibrate_joints --port /dev/ttyUSB3 --out ../config/joint_calib.txt
```

Calibration formula: `urdf = dir * scale * motor + offset`.

### Notice

This package drives a 7-DOF R1 arm over one serial bus via the vendored `thirdparty/motor_controller` (IM6014). Public `q` / `dq` / `tau` use the URDF frame; conversion happens at the `ArmMotorBus` edge.
