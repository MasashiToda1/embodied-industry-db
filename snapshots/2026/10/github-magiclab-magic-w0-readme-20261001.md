<div align="center">

<img src="assets/magic-w0-color-logo-v2.png" alt="Magic-W0" width="520">

# Magic-W0: A Structured World–Action Foundation Model for Physical Intelligence

*Magic-Lab Team · Magiclab Robotics Inc.*

<a href="https://embodied.magiclab.top/works/wam/magic-w0/index.html"><img src="https://img.shields.io/badge/Website-Project_Page-blue" alt="Project Homepage"></a> <a href="https://github.com/MagiclabRobotics/Magic-W0"><img src="https://img.shields.io/badge/Repository-GitHub-black?logo=github" alt="GitHub Repository"></a> <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green" alt="MIT License"></a>
<br>
<a href="https://huggingface.co/Flyfish101/Magic-W0"><img src="https://img.shields.io/badge/%F0%9F%A4%97_Model-HuggingFace-yellow" alt="Model on HuggingFace"></a>

[Update News](#update-news) · [Abstract](#abstract) · [Key Features](#key-features) · [Getting Started](#getting-started)

</div>

<a name="update-news"></a>

## 📣 Update News

- **[2026-09-30]** Added the project overview. Code and pretrained checkpoints are coming soon.

<a name="abstract"></a>

## 📖 Abstract

Magic-W0 learns structured world transitions and continuous robot actions from diverse embodied experience. It represents the current scene, action-induced 3D motion, and task-relevant future semantics, and couples world prediction with action generation through layer-aligned interaction. Pretrained on approximately 2.014M effective action episodes and 2.61M visual-language samples, it achieves 99.05% average success on LIBERO and 94.6% across five real-robot tasks after downstream fine-tuning.

<p align="center">
  <img src="assets/figure1-v9.gif" alt="Magic-W0 overview: diverse embodied data, a unified action interface, structured world modeling, and robot manipulation" width="100%">
</p>

<a name="key-features"></a>

## ✨ Key Features

- 🌍 **World–action modeling:** learn geometry, motion, future semantics, and continuous control together.
- 🤖 **Cross-embodiment data:** use a shared 34D state–action interface with masks for missing dimensions.
- ⚡ **Teacher-free policy execution:** use Track4World and DINOv3 supervision during training without running these teachers at inference.
- 🛠️ **Configurable training workflows:** adapt YAML recipes for pretraining, fine-tuning, and distributed execution.
- 🔍 **Checkpoint diagnostics:** check inference contracts and evaluate generated actions and world representations.

<a name="getting-started"></a>

## 🚀 Getting Started

Code and pretrained weights are coming soon. Setup and usage instructions will be added alongside the source release.

### Installation

Requires Linux, Python 3.11, and CUDA-enabled PyTorch. These steps apply once the source code is released.

```bash
git clone https://github.com/MagiclabRobotics/Magic-W0.git
cd Magic-W0
conda create -n magic-w0 python=3.11 -y
conda activate magic-w0

# Install a PyTorch build compatible with your CUDA environment first.
python -m pip install -r requirements.txt
python -m pip install -e '.[multimodal]'
```

### Model Checkpoints

Model weights: [🤗 Hugging Face](https://huggingface.co/Flyfish101/Magic-W0).

### Data Preparation

Coming soon: supported data formats, custom dataset configuration, and normalization instructions.

### Training and Fine-tuning

Coming soon: training configurations, single-node and multi-node launch commands, fine-tuning, and checkpoint resumption.

### Inference and Deployment

Coming soon: a minimal inference example, observation preparation, action decoding, and robot integration instructions.

### Evaluation

Coming soon: checkpoint diagnostics, benchmark setup, and evaluation commands.

## 🙏 Acknowledgements

We thank the Hugging Face and LeRobot communities for their infrastructure and tooling. Magic-W0 builds on Qwen3.5, Track4World, Depth Anything 3, DINOv3, and FAST. We also thank the LIBERO and RoboDojo teams for their evaluation benchmarks.

## 📚 Citation

If you find Magic-W0 useful for your research, please cite the project:

```bibtex
@misc{magiclab2026magicw0,
  title        = {Magic-W0: A Structured World--Action Foundation Model for Physical Intelligence},
  author       = {Chen, Xuhua and Yin, Zhenhan and Zhang, Yuan and Zhang, Tao and others},
  year         = {2026},
  howpublished = {GitHub repository},
  url          = {https://github.com/MagiclabRobotics/Magic-W0}
}
```

## 📜 License

Released under the **MIT License**. See [LICENSE](LICENSE) for the full terms.
