# LinkerBot Arm ROS2

English | [简体中文](README_zh.md)

Control left and right LinkerBot A7, A7 Lite, and P7 arms through ROS2 topics and services, using the standalone `linkerbot-arm` SDK. Supports Ubuntu 22.04 / Humble / Python 3.10 and Ubuntu 24.04 / Jazzy / Python 3.12.

## Getting Started

1. [Installation and Build](docs/en/INSTALLATION.md): create the matching ROS Python environment and install the latest SDK from `main`.
2. [Connecting and Starting](docs/en/getting_started.md): configure CAN, choose a model, and launch one or both arms.
3. [Topics and Joint Control](docs/en/topics.md): read state and publish seven-joint targets.

The [Developer User Manual](docs/en/environment_setup.md) covers configuration, lifecycle services, feedback timestamps, calibration, troubleshooting, and [Docker validation](docs/en/testing.md).

The ROS2 package and Python import remain `linker_arm_ros2`. Install the latest SDK and Transport from `main` using this repository's [source manifest](requirements/source-versions.txt). The default configuration automatically enables and homes at startup; follow the first-session guide to disable automatic enabling initially.

## Development and Validation

Humble/Jazzy share the node, launch files, and configuration. See [Testing and Docker Validation](docs/en/testing.md) for checks. Tests without hardware do not validate physical motion, stopping, or calibration.

Source: [linker-bot/linkerbot-arm-ros2-sdk](https://github.com/linker-bot/linkerbot-arm-ros2-sdk).

## Contributing and license

English and Chinese contributions are welcome. Follow the
[Linkerbot contribution guide](https://github.com/linker-bot/.github/blob/main/CONTRIBUTING.md).
Report vulnerabilities privately using the
[organization security policy](https://github.com/linker-bot/.github/blob/main/SECURITY.md).

Licensed under the [MIT License](LICENSE).
