<div align="center">

<h1>Unitas: A 3D-Native World Action Model for Embodied Manipulation</h1>

<p>
<span><a href="https://robbinw.github.io/" rel="noopener noreferrer" target="_blank">Ruixiang Wang</a><sup>1,2*</sup></span>, &nbsp; <span><a href="https://yysu.site/" rel="noopener noreferrer" target="_blank">Yongyi Su</a><sup>3*†</sup></span>, &nbsp; <span>Wenlve Zhou<sup>3</sup></span>, &nbsp; <span>Bo Yue<sup>1,2</sup></span>, &nbsp; <span>Hengyan Liu<sup>1,2</sup></span>, &nbsp; <span>Dekun Lu<sup>2</sup></span><br>
<span>Yuxin Tian<sup>1,2</sup></span>, &nbsp; <span>Yihan Fang<sup>1,2</sup></span>, &nbsp; <span>Zerui Wu<sup>2</sup></span>, &nbsp; <span>Xing Hu<sup>2</sup></span>, &nbsp; <span>Jietao Chen<sup>2</sup></span>, &nbsp; <span>Yong Guo<sup>2</sup></span><br>
<span>Ziyan He<sup>2</sup></span>, &nbsp; <span>Junbin Yuan<sup>4</sup></span>, &nbsp; <span>Guiliang Liu<sup>1</sup></span>, &nbsp; <span>Xiaofen Xing<sup>5</sup></span>, &nbsp; <span><a href="http://kuijia.site/" rel="noopener noreferrer" target="_blank">Kui Jia</a><sup>1,2</sup></span>
</p>

<p>
<sub>
<sup>1</sup> CUHK-SZ &nbsp; <sup>2</sup> DexForce &nbsp; <sup>3</sup> FSU &nbsp; <sup>4</sup> SYSU &nbsp; <sup>5</sup> SCUT<br>
<sup>*</sup> Equal contribution &nbsp; <sup>†</sup> Correspondence to &lt;suyongyi@fosu.edu.cn&gt;
</sub>
</p>

<p>
  <a href="https://dexforce.com/technical-report/#/unitas-wam"><img src="https://img.shields.io/badge/UNITAS-Project_page-4285F4?style=plastic&amp;logo=googlechrome&amp;logoColor=white" alt="UNITAS Project page"></a>
  <a href="https://arxiv.org/abs/2610.12099"><img src="https://img.shields.io/badge/Paper-arXiv-B31B1B?style=plastic&amp;logo=arxiv&amp;logoColor=white" alt="Paper: arXiv"></a>
  <img src="https://img.shields.io/badge/Checkpoints-Coming_soon-FFD21E?style=plastic&amp;logo=huggingface&amp;logoColor=white" alt="Checkpoints: Coming soon">
  <img src="https://img.shields.io/badge/Dataset-Coming_soon-FFD21E?style=plastic&amp;logo=huggingface&amp;logoColor=white" alt="Dataset: Coming soon">
</p>


</div>

## Overview

<div align="center">
  <img src="assets/overview.png" alt="UNITAS overview: diverse embodiments and a shared world-coordinate interface for observations, action flow, and scene dynamics" width="100%">
</div>

**UNITAS** is a 3D-native world action model for embodied manipulation. It unifies observations, actions, and scene dynamics in a shared metric 3D frame within each interaction, using a common representation across robot embodiments and human hands.

### Highlights

- **One physical space.** Observations, actions, and scene dynamics share a metric 3D world-coordinate frame.
- **A common motion representation.** Point trajectories represent robot motion, human hand motion, and scene dynamics.
- **Complementary capabilities.** The framework supports robot-action generation and action-conditioned scene prediction.
- **Strong results with 1.7B parameters.** Success rates reach **99.8%** on LIBERO, **89.1%** on LIBERO-Plus, **56.2%** on VLABench, and **92.94% / 93.04%** on RoboTwin Clean / Randomized. Moving ADE is **35% lower** than PointWorld on RoboTwin scene prediction.

## Release Plan

We are preparing the following releases:

- [ ] Model checkpoints and inference code
- [ ] Training code
- [ ] Training dataset
