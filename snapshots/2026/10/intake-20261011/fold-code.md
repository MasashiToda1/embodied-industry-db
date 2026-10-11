# FoldNet++

Official code for **FoldNet++: a Large-Scale Synthetic Dataset for Robotic T-Shirt Folding and Unfolding**.

- **Project:** https://pku-epic.github.io/FoldNetXX/
- **Dataset:** https://huggingface.co/datasets/GalaxyGeneralRobotics/FoldNetXX

## Requirements

- A CUDA GPU with 48 GB of memory is recommended (24 GB cards may OOM).
- [uv](https://docs.astral.sh/uv/) for dependency management.

## Installation

```bash
# Install dependencies
uv sync

# Download the dataset (tar shards), then unpack into storage/release
HF_TOKEN=hf_your_token uv run hf download GalaxyGeneralRobotics/FoldNetXX --repo-type dataset --local-dir storage/release_tar
uv run python script/unpack_tar.py -i storage/release_tar -o storage/release

# Download pretrained backbones (VAE, PaliGemma, ResNet) into storage/pretrained
HF_TOKEN=hf_your_token uv run python script/prepare_ckpt.py

# Link the pi0 checkpoint used for pretraining
mkdir -p storage/pretrained/openpi
ln -s ../../release/ckpt/pi0.safetensors storage/pretrained/openpi/pi0.safetensors
```

`HF_TOKEN` is your Hugging Face access token; it is required for gated repos such as `google/paligemma-3b-mix-224`.

## Usage

### Dataset visualization

See [`example/visualize_data.ipynb`](example/visualize_data.ipynb).

### Training

Pretraining:

```bash
SWANLAB_API_KEY=your_api_key bash example/pretrain.sh
```

Finetuning:

```bash
SWANLAB_API_KEY=your_api_key bash example/finetune.sh
```

Both scripts auto-detect the number of GPUs on the node. For multi-node training, set `WORLD_SIZE`, `RANK`, `MASTER_ADDR`, and `MASTER_PORT` before launching.

## Repository structure

```
script/                 entry-point scripts
  train_vla.py          VLA training (launched with torchrun)
  unpack_tar.py         unpack the downloaded dataset tars
  prepare_ckpt.py       download pretrained backbones
example/                runnable examples
  pretrain.sh           pretraining launch script
  finetune.sh           finetuning launch script
  visualize_data.ipynb  dataset visualization notebook
src/foldnetxx_net/      main package
  config.py             model and data configs
  dataset/              data loading and preprocessing
  model/                VLA and diffusion-policy models
  server/               policy inference agents for deployment
  train/                training loop utilities
  utils/                args, logging, file management
storage/                datasets, checkpoints, pretrained weights (git-ignored)
```

## Citation

```bibtex
@inproceedings{
chen2026foldnetxx,
title={FoldNet++: a Large-Scale Synthetic Dataset for Robotic T-Shirt Folding and Unfolding},
author={Yuxing Chen and Zhiyuan Wei and Bowen Xiao and Zhizheng Zhang and He Wang},
booktitle={10th Annual Conference on Robot Learning},
year={2026},
url={https://openreview.net/forum?id=JMcC5JoPKD}
}
```
