---
license: apache-2.0
language:
- en
- zh
tags:
- automatic-speech-recognition
- asr
- speech-recognition
- streaming-asr
- speech
- audio
- multimodal
- voxtral
- chinese
- english
- code-switching
library_name: transformers
pipeline_tag: automatic-speech-recognition
base_model: mistralai/Voxtral-Mini-4B-Realtime-2602
---

# X2Streaming-ASR-4B (zh/en)

**Wait when uncertain, emit when ready:** append-only streaming speech recognition for Chinese, English, and Chinese–English code-switching.

This checkpoint is **X2Streaming-ASR-4B** fine-tuned from [Voxtral Mini Realtime](https://huggingface.co/mistralai/Voxtral-Mini-4B-Realtime-2602) with a learned commit policy (LISTEN / DECODE every 80 ms). Output is **append-only**—committed text is never rolled back.

| | |
| --- | --- |
| **Architecture** | `VoxtralRealtimeForConditionalGeneration` |
| **Parameters** | ~4B (26-layer text decoder, 32-layer audio encoder) |
| **Precision** | bfloat16 |
| **Audio** | 16 kHz mono; 128 mel bins; ~80 ms streaming frames (12.5 Hz) |
| **Languages** | `zh`, `en`, `cs` (code-switching) |
| **Inference code** | [X-Square-Robot/X2Streaming-ASR](https://github.com/X-Square-Robot/X2Streaming-ASR) |

Paper: [X2Streaming-ASR (arXiv:2609.08672)](https://arxiv.org/abs/2609.08672)

---

## Model description

X2Streaming-ASR keeps the causal audio encoder, adapter, and decoder-only LM of Voxtral Realtime, but replaces fixed delay with a learned **when to commit** decision:

1. **LISTEN** — For each new ~80 ms audio step, predict *Wait* if context is ambiguous, or *Emit* when ready.
2. **DECODE** — After *Emit*, generate text for the new audio until EOS, then return to LISTEN.
3. **Reuse history** — Incremental encoding and LM KV-cache reuse; no full-audio re-encoding each step.

On evaluated benchmarks (see the [project README](https://github.com/X-Square-Robot/X2Streaming-ASR)), mean emission latency is on the order of **32–109 ms (zh)** and **12–85 ms (en)** after each character/word ends, with competitive CER/WER versus streaming baselines.

### Config summary (this repo)

| Component | Key settings |
| --- | --- |
| Text LM | 26 layers, hidden 3072, 32 heads, 8 KV heads, vocab 131072, sliding window 8192 |
| Audio encoder | 32 layers, hidden 1280, 32 heads, sliding window 750 |
| Streaming | `downsample_factor`: 4, `audio_length_per_tok`: 8, `default_num_delay_tokens`: 6 |
| Processor | `VoxtralRealtimeProcessor`, 16 kHz, hop 160, win 400 |

Files in this repository: `config.json`, `params.json`, `processor_config.json`, `generation_config.json`, `tekken.json`, and weight shards.

---

## Quick start (recommended)

Weights alone are not enough for adaptive streaming—you need the **[X2Streaming-ASR](https://github.com/X-Square-Robot/X2Streaming-ASR)** inference stack (Transformers or vLLM).

### 1. Install

Linux, **Python 3.11**, and a CUDA GPU are recommended.

```bash
git clone https://github.com/X-Square-Robot/X2Streaming-ASR.git
cd X2Streaming-ASR

conda create -n x2streamingasr python=3.11 -y
conda activate x2streamingasr
pip install -r requirements.txt
```

### 2. Download this model

```bash
pip install -U huggingface_hub

# Optional mirror
export HF_ENDPOINT=https://hf-mirror.com

huggingface-cli download x-square-robot/X2Streaming-ASR-4B-1009 --local-dir ./X2Streaming-ASR-4B-1009
export MODEL_PATH="$(pwd)/X2Streaming-ASR-4B-1009"
```

Or clone from the Hub:

```bash
git lfs install
git clone https://huggingface.co/x-square-robot/X2Streaming-ASR-4B-1009
export MODEL_PATH=/path/to/X2Streaming-ASR-4B-1009
```

### 3. Streaming and offline inference

```bash
# Adaptive streaming (append-only commits)
python infer.py \
  --config configs/infer.yaml \
  --model_path "$MODEL_PATH" \
  --language zh \
  --audio /path/to/audio.wav

# Full-context offline
python infer.py \
  --config configs/infer_offline.yaml \
  --model_path "$MODEL_PATH" \
  --language en \
  --audio /path/to/audio.wav
```

> **Set `--language` to match your audio:** `zh` (Chinese), `en` (English), `cs` (code-switching). One tag applies to the whole run.

### 4. JSONL batch

Input lines use `audio`, `wav`, or `wav_path`:

```bash
python infer.py \
  --config configs/infer.yaml \
  --model_path "$MODEL_PATH" \
  --language en \
  --input_file audio.jsonl \
  --output_file results.jsonl
```

### 5. Web demo

```bash
BACKEND=transformers MODE=adaptive LANGUAGE=zh REPO_ID="$MODEL_PATH" bash demo/run.sh
```

Open `http://localhost:7860`.

---

## Training note

This release supports **Chinese and English** recognition with the learned streaming commit policy described in the paper. Weights are initialized from [Voxtral Mini Realtime](https://huggingface.co/mistralai/Voxtral-Mini-4B-Realtime-2602) and trained with the multi-stage recipe in [X2Streaming-ASR (arXiv:2609.08672)](https://arxiv.org/abs/2609.08672).

For full methodology and benchmarks, see the [paper](https://arxiv.org/abs/2609.08672) and the [code repository](https://github.com/X-Square-Robot/X2Streaming-ASR).

---

## License

Model weights: **Apache License 2.0** (same as upstream [Voxtral-Mini-4B-Realtime-2602](https://huggingface.co/mistralai/Voxtral-Mini-4B-Realtime-2602)). See the code repo for `MODEL_LICENSE.md` and attribution requirements.

---

## Citation

```bibtex
@article{lin2026x2streaming,
  title={X2Streaming-ASR: wait when uncertain, emit when ready for streaming ASR},
  author={Lin, Zhiwei and Fu, Kaiqi and Wen, Rime and Liu, Zehan and Qin, Shawn and Gan, Roy and Wang, Hao and Wang, Qian},
  journal={arXiv preprint arXiv:2609.08672},
  year={2026}
}
```

---

## 简介（中文）

**X2Streaming-ASR-4B** 是面向中文、英文及中英混合的**极低延迟、结果不可回退**的流式语音识别模型，权重基于 [Voxtral Mini Realtime](https://huggingface.co/mistralai/Voxtral-Mini-4B-Realtime-2602) 微调。

- 每约 **80 ms** 在 **LISTEN（等待）** 与 **DECODE（发射）** 间决策；已输出文本**不会回改**。
- 音频 **16 kHz**；请通过 [X2Streaming-ASR 代码库](https://github.com/X-Square-Robot/X2Streaming-ASR) 运行 `infer.py` 或 Web Demo。
- 使用时务必设置 **`--language`**：`zh` / `en` / `cs`。
- 论文：[arXiv:2609.08672](https://arxiv.org/abs/2609.08672)
