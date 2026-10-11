---
license: cc-by-nc-4.0
language:
- en
task_categories:
- robotics
size_categories:
- 100M<n<1B
viewer: false
---

# Dataset Card for FoldNet++ Dataset

This dataset is the official release of the [FoldNet++](https://pku-epic.github.io/FoldNetXX/) dataset.

## Dataset Details

### Dataset Description

This dataset contains ~120K synthetic demonstration episodes of robotic T-shirt folding and unfolding, as well as URDFs and pretrained checkpoints.

Each episode includes three camera views (5Hz) and an action trajectory (in both qpos and eef forms).

### Dataset Sources

- **Code:** [https://github.com/GalaxyGeneralRobotics/FoldNetXX](https://github.com/GalaxyGeneralRobotics/FoldNetXX)
- **Project:** [https://pku-epic.github.io/FoldNetXX/](https://pku-epic.github.io/FoldNetXX/)
- **Paper:** [https://arxiv.org/abs/2609.12433](https://arxiv.org/abs/2609.12433)

## Uses

See the example code in the [FoldNet++ repository](https://github.com/GalaxyGeneralRobotics/FoldNetXX).

**BibTeX:**

```
@inproceedings{
chen2026foldnetxx,
title={FoldNet++: a Large-Scale Synthetic Dataset for Robotic T-Shirt Folding and Unfolding},
author={Yuxing Chen and Zhiyuan Wei and Bowen Xiao and Zhizheng Zhang and He Wang},
booktitle={10th Annual Conference on Robot Learning},
year={2026},
url={https://openreview.net/forum?id=JMcC5JoPKD}
}
```