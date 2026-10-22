# wuji-mujoco

[![MuJoCo](https://img.shields.io/badge/MuJoCo-3.11.0-silver.svg)](https://mujoco.readthedocs.io/)
[![Python](https://img.shields.io/badge/python-3.11-blue.svg)](https://docs.python.org/3/whatsnew/3.11.html)
[![Linux platform](https://img.shields.io/badge/platform-linux--64-orange.svg)](https://pixi.prefix.dev/latest/reference/pixi_manifest/#platforms)
[![License](https://img.shields.io/badge/license-Apache--2.0-yellow.svg)](https://opensource.org/licenses/Apache-2.0)

Simulation demo for MuJoCo 3.11.0. This repository provides a minimal example for loading and controlling the Wuji Hand (hand2) in MuJoCo simulator. Loads MJCF models from the description submodule and plays pre-recorded trajectories in a loop. Both left and right hands are supported.

**Get started with [Quick Start](#quick-start).**

## Simulation preview

<h3 align="center">Right hand</h3>

<p align="center">
  <img src="assets/right.gif" width="854" alt="Right hand simulation">
</p>

## Repository Structure

```text
├── assets/                    // Right-hand simulation GIF
│   └── right.gif
├── data/                      // Pre-recorded trajectory data
│   └── wave.npy
├── wuji_description/          // Submodule: hand models (MJCF, meshes)
├── run_sim.py                 // Main simulation script
├── pixi.toml                  // Environment and simulation task
├── pixi.lock                  // Locked dependency versions
└── README.md
```

## Quick Start

### Prerequisites

- Linux x86_64 and [Pixi](https://pixi.sh) (tested with 0.72.0).

### Installation

Clone the repository and install the dependencies:

```bash
git clone --recurse-submodules https://github.com/wuji-technology/wuji-mujoco.git
cd wuji-mujoco
pixi install
```

### Running

```bash
# Right hand
pixi run sim --side right

# Left hand
pixi run sim --side left
```

The script loads the right-hand model by default and plays the trajectory from `data/wave.npy` in a loop. Use `--side left` to load the left hand. Close the simulation window to stop.

### Initialize Models

```bash
git submodule update --init --recursive
```

## License

Apache-2.0, see [LICENSE](LICENSE) and [NOTICE](NOTICE). Contact: [support@wuji.tech](mailto:support@wuji.tech).
