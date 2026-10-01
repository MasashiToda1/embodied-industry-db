# di-e2e-mot

[![CI](https://github.com/D-Robotics/di-e2e-mot/actions/workflows/ci.yml/badge.svg)](https://github.com/D-Robotics/di-e2e-mot/actions/workflows/ci.yml)
English | [简体中文](README.zh-CN.md)

Unified end-to-end multi-object tracking: one config system, one model registry and
one state protocol for DETR-family trackers (MOTR, CO-MOT, MOTIP, MeMOTR, SambaMOTR,
DualTemporalMOT, FDTA), plus a path from the research code to a static-shape ONNX graph.

> **⚠️ Work in progress — v0.2.0, partial release.**
> This is not a finished toolkit. **Three of the nine subcommands complete a run**
> (`models`, `export`, and `deploy` with the `tensorrt` backend — the last one
> builds and measures an engine rather than running inference). The Horizon/RDK
> deployment backend is a registered
> placeholder whose three methods raise `NotImplementedError`. Of the seven registered
> variants, **four are unvalidated ports** — none has reproduced upstream numbers, and
> only each one's `PROVENANCE.md` says what it does and does not do. Read
> [What works today](#what-works-today) before you try anything, and
> [Known issues](#known-issues) before you file a bug.

---

## Why this exists

End-to-end (query-based) multi-object tracking is published as a family of research
repositories that do not compose:

- **MOTR** (ECCV 2022) — the ancestor of the line.
- **CO-MOT** (ICLR 2025; arXiv 2023) — bridges end-to-end and non-end-to-end.
- **MOTIP** (CVPR 2025) — reformulates tracking as ID prediction.

Four further end-to-end trackers are ported against the same contract.
**All four are registered unvalidated** — none has reproduced upstream numbers. One
(DualTemporalMOT) stops at the contract layer; the other three each also reached a real
static-shape export plus a 20-frame PyTorch↔ONNX parity gate, and **all three run
end to end from `dimot export`**. FDTA's gate runs against the released checkpoint;
MeMOTR's and SambaMOTR's run on random weights (MeMOTR's checkpoints are unreachable
from this machine, and SambaMOTR's have not been run numerically — that family
additionally carries a known weight-compatibility blocker, recorded in its
`PROVENANCE.md`). Each has a `PROVENANCE.md` recording exactly how far it got:

- **MeMOTR** — <https://github.com/MCG-NJU/MeMOTR> (MIT). Dynamic trunk, fixed-state
  core, real static-shape export, 20-frame parity gate on random weights.
- **SambaMOTR** — <https://github.com/mattiasegu/sambamotr> (MIT). The same bar as
  MeMOTR, plus a 754-tensor name/shape manifest checked against the shipped
  `sambamotr_dab_dancetrack.pth` checkpoint (shapes only — not a numerical run).
- **DualTemporalMOT** — <https://github.com/altkddhfcjs/DualTemporalMOT>.
  Contract layer only, by recorded decision.
- **FDTA** — <https://github.com/Spongebobbbbbbbb/FDTA> (CVPR 2026, arXiv:2512.02392).
  The one of the four whose parity gate runs against the released checkpoint: real
  static-shape export plus a 20-frame PyTorch↔ONNX parity gate.

> **Removed in v0.2.0: DecoderTracker.** v0.1.0 shipped a fourth family — a
> YOLO-based decoder tracker ported from an AGPL-3.0 fork — whose tracker never
> reached parity with its upstream; it is gone. Its reason to exist, the fixed-state
> query memory (FSQM) — a fixed-capacity track state plus a fixed-runtime inference
> core that exports as a static ONNX graph — is not gone with it: that mechanism
> already lives in this toolkit through the CO-MOT and MOTR ports
> (`di_mot/models/comot/fixed_state.py`, `fixed_runtime.py`, `onnx_runtime.py`; the
> MOTR and CO-MOT `StateSpec`s are declared against that fixed-state contract) and
> through MOTIP's own fixed-state port (`di_mot/models/motip/fixed_state.py`,
> `fixed_runtime_tracker.py`). FSQM is those projects' mechanism, carried by their
> ports — not something this toolkit invented.

Each ships its own config format, its own checkpoint dialect, its own naming for the
cross-frame state, and its own idea of what the graph boundary is. Moving any of them
onto a board means re-deriving all of that by hand, and the arithmetic is implicit —
in the upstream code the CO-MOT query layout is a hardcoded expression inside a
submission script.

This project is a **unification layer over the upstream codebases, not a fork of any
one of them**. The upstream repositories are not vendored wholesale: most code is
*ported* (copied and rewritten against a declared contract), and each port is recorded
with a per-file SHA-256 in a `PROVENANCE.md` beside the ported package.
`scripts/port_closure.py` derives the port *surface* — the file list — for the families
it covers. The explicit non-goal is merging the training loops: what is unified is the
interface, not the implementation.

---

## What works today

### CLI

**Three of the nine subcommands complete a run.** (`deploy` completes with the
`tensorrt` backend on a TRT-capable host — engine build and measurement, not
inference; see the Deployment section for its parity caveat.)

| Subcommand | Observed behaviour |
|---|---|
| `models` | ✅ Works. Lists all seven registered `(family, variant)` pairs and an `upstream` column |
| `export` | ✅ **Works** (since 2026-09-29). Five `(family, variant)` pairs have a recipe; all five are run end to end (comot's run: 2026-09-30, random weights) — see below |
| `deploy` | `tensorrt` on a TRT-capable host: engine build + `artifact.json` + `--measure`, exit 0 (fp32 parity passes after a documented graph rewrite; see the Deployment section). `horizon-s100`: reports it is not runnable, exit 1. Exit 2 for an unknown backend, a missing ONNX, or a missing/bad sidecar manifest |
| `train` · `infer` · `eval` · `quantize` · `parity` · `capacity` | `not implemented yet`, exit 1 |

#### `dimot export`

`--family` takes the **registry** family (`dimot models`, column 1); `--variant` is
optional:

```
$ dimot export -c cfg.yaml --family memotr --ckpt ck.pth --output out.onnx
$ dimot export -c cfg.yaml --family motip --variant fdta --ckpt ck.pth --output out.onnx
```

`--family` is **required with no default**: it selects the recipe, and the recipe
decides what the graph looks like. A default would turn "I do not know which family
this is" into "it is <the default>", and the latter quietly exports *another family's
graph* — one that passes the checker. `--variant` defaults to the variant named after
the family, then to "exactly one candidate"; two candidates with no name match fail
hard rather than pick for you — ambiguity is not a default. Both values are resolved
from a table at run time rather than via argparse `choices=`, because that table is
only populated once the family modules are imported.

The "registry family → export-plan family" translation lives in **exactly one place**
(`models/export_recipes.py`):

| family | variant | plan family | run end to end |
|---|---|---|---|
| `comot` | `motr_co` | `motr_family` | ✅ real export + manifest (2026-09-30, random weights; see Known issues) |
| `memotr` | `motr_memotr` | `motr_family` | ✅ real export + manifest |
| `sambamotr` | `motr_sambamotr` | `motr_family` | ✅ real export + manifest |
| `motip` | `motip` | `motip` | ✅ real export + manifest |
| `motip` | `fdta` | `motip` | ✅ real export + manifest |

`dualtemporalmotr` (contract layer only) and `motr` (only `model.py`) have **nothing to
export**; `--family` on either gets a `KeyError` naming `EXPORT_RECIPES`. That is not a
missing implementation, and it is a different message from the one for a mistyped
variant — the two call for opposite next actions.

⚠️ **Weights go into the *core*, not the graph module.** CO-MOT's graph module
`CoMotOnnxBoundary` stores its core as `self.core`, so its `state_dict()` keys all carry
a `core.` prefix — loading an unprefixed checkpoint into the boundary with
`load_state_dict(..., strict=False)` matches **nothing, silently**: `strict=False`
treats "all missing" and "all matched" alike. The contract lives in
`models/export_recipes.py::GraphBuild.checkpoint_target`, and `_cmd_export` honours it.

**Every export here uses random weights.** The upstream checkpoints live on Google
Drive and are unreachable from this machine, so this path verifies **wiring and
staticness**, not numbers; the numerical side is each family's parity gate under
`tests/models/<family>/`. The shipped configuration has been exported for real too
(below), which removes "never exported at the shipped configuration" — not "random
weights".

The **`export_static_core` library function underneath does work** and is covered by
tests that perform a real export of a ported model, asserting the graph carries no
symbolic output dimensions. Before 2026-09-29 that layer was what "the export path is
implemented" meant, with the CLI as the missing part; the CLI part is now in place.

### Library

Implemented and exercised by the test suite:

- `core/registry.py` — model registry keyed by `(family, variant)`; unknown keys fail
  hard, no silent fallback. Registered: `motr/motr`, `comot/motr_co`, `motip/motip`,
  and four ports — `memotr/motr_memotr`, `sambamotr/motr_sambamotr`,
  `dualtemporalmotr/motr_dualtemporalmotr`, `motip/fdta`. Each registration also
  carries an `upstream` flag meaning **"this family has reproduced upstream's
  numbers"**; all four ports are marked `UNVALIDATED` (see each family's
  `PROVENANCE.md` for what was and was not delivered).
- `core/state.py` — declarative cross-frame state (`TrackState` / `StateSpec` /
  `FieldSpec`) with explicit axis polarity and a required identity binding, because the
  families disagree about whether a slot holds an ID or a label.
- `core/layout.py` — validated query-layout and capacity arithmetic
  (`QueryLayout` / `CapacityPolicy` / `DeploymentShape`).
- `core/graphio.py` — the graph I/O naming contract, including the `next_` (MOTR
  family) vs `out_` (MOTIP) output prefixes.
- `core/export_plan.py` — per-family export plan, graph boundary and precision contract.
- `models/export_recipes.py` — registry family → export-plan family + fixed graph
  module (what the CLI's `export` resolves through).
- `deploy/export.py` — the static-shape ONNX export pipeline and the artifact manifest.
- `deploy/parity.py` — a PyTorch ↔ ONNX Runtime per-frame state parity gate.
- `core/checkpoint.py` — readers for three incompatible upstream checkpoint dialects.
- `core/metrics.py`, `eval/evaluator.py` — provenance-carrying metrics and an
  in-process vendored TrackEval.
- `data/spec.py` — dataset layout declarations (DanceTrack, MOT17, SportsMOT, BFT,
  CrowdHuman, BDD100K).

`deploy/parity.py`, `core/metrics.py`, `eval/evaluator.py` and `data/spec.py` have no
CLI path at all yet.

Test suite: **all passing** (`pytest tests -q`; runtime is machine-dependent,
roughly 1–2 minutes; the count drifts with every change — trust
`pytest --collect-only -q`, no number is pinned here).

---

## Install

Python ≥ 3.10.

```bash
git clone https://github.com/D-Robotics/di-e2e-mot.git
cd di-e2e-mot
```

Releases are GitHub-only — there is no PyPI package. To install a tagged release
non-editable:

```bash
git clone --depth 1 --branch v0.2.0 https://github.com/D-Robotics/di-e2e-mot.git
cd di-e2e-mot
pip install .
```

The core package needs only `torch` and `pyyaml`:

```bash
pip install -e .
```

`pyproject.toml` is the single source of dependency truth; there is no `requirements.txt`.
To run the whole test suite from scratch:

```bash
pip install -e ".[dev,motip,onnx]"
python -m pytest tests -q
```

`di_mot.models` registers every family at import time, and that import needs
`accelerate`, `numpy`, `pillow`, `scipy` (all four also in `dev`), `torchvision` (in both
`motr` and `motip`) and `einops` (in both `motip` and `sambamotr`). The deploy and export
tests import `onnx` and `onnxruntime`. Note that the `onnx` extra pulls
`onnxruntime-gpu`: on a CPU-only host, install `onnx` + `onnxscript` + `onnxruntime`
explicitly instead — the same CPU trio the CI workflow installs — because `onnxruntime`
and `onnxruntime-gpu` in one environment are a known conflict.

⚠️ `einops` is on the **registration** chain, not just a family's own: FDTA's
`temporal_adapter.py` keeps upstream's `from einops import ...` verbatim (the port does
not use it). So `pip install -e ".[dev]"` alone leaves `import di_mot.models` — and with
it the whole test suite — failing with `ModuleNotFoundError: einops`. Install
`.[dev,motip]` or `.[dev,motip,sambamotr]`.

Extras: `motr` · `memotr` · `motip` · `sambamotr` · `onnx` · `eval` · `dev`.

---

## Quick start

```bash
$ dimot models
family            variant                upstream
comot             motr_co                yes
dualtemporalmotr  motr_dualtemporalmotr  UNVALIDATED
memotr            motr_memotr            UNVALIDATED
motip             fdta                   UNVALIDATED
motip             motip                  yes
motr              motr                   yes
sambamotr         motr_sambamotr         UNVALIDATED
```

The `upstream` column answers **"has this family reproduced upstream's numbers"**, not
"does it have weights". All four ports answer no — including FDTA, which is the only one
that reached the full exportable-layer bar (real static-shape export plus a 20-frame
PyTorch↔ONNX parity gate against the released checkpoint). See each family's
`PROVENANCE.md`.

`dimot export` accepts both upstream config dialects: a CO-MOT `.args` text file, or a
MOTIP YAML with `SUPER_CONFIG_PATH`; `--set key=value` overrides either — for
**scalar keys only** (bool / int / float / string). List values such as `SEQUENCE_HW`
or `IMAGE_CANVAS` cannot be passed on the command line and must live in the config
file.
⚠️ The **capacity keys differ in case between families** — memotr reads
`fixed_track_capacity` / `g_size`, sambamotr reads `FIXED_TRACK_CAPACITY` / `G_SIZE`
(each family has its own `CAPACITY_KEY_MAP`). `comot`'s graph-boundary layer reads
**native lowercase** shape keys (the uppercase-name translation is deliberately
unimplemented there), and `motip` / `fdta` need `SEQUENCE_HW` (upstream it is each
sequence's own resolution; a static graph has to pin it down).

> There is no `configs/` directory in this repository, and no checkpoint has been
> released. The shortest path from a fresh clone is [`examples/`](examples/README.md):
> `make_random_checkpoint.py` builds a shape-legal random-weight checkpoint for any
> exportable family, and every YAML there was actually exported before it landed —
> four tiny shrunken configs plus `comot-motr_co.yaml`, which is the upstream
> DanceTrack working point at the full, pinned 768×1344 canvas (CO-MOT has no small
> canvas; its example card takes ~14 s / ~169 MB on CPU). In the tests, the fixture
> dicts that exercise `dimot export` live in
> `tests/models/{memotr,sambamotr,fdta,motip}/test_fixed_export.py`,
> `tests/models/test_export_recipes.py` runs the CLI end to end on the memotr one,
> and `tests/deploy/test_export_comot.py` exports the real CO-MOT kernel. The first
> `memotr` / `sambamotr` export downloads the ImageNet ResNet50 backbone (~98 MB)
> through torchvision; `motip` / `fdta` / `comot` need no download.

The fastest first run is the fdta card (`examples/README.md`, card A) — two commands,
CPU-only, no download:

```bash
$ python examples/make_random_checkpoint.py --family motip --variant fdta \
      -c examples/motip-fdta.yaml --out fdta-random.pth
$ python -m di_mot.cli export -c examples/motip-fdta.yaml --family motip \
      --variant fdta --ckpt fdta-random.pth --output fdta.onnx
# -> fdta.onnx + fdta.onnx.json (sidecar manifest; export.literalised_dims == 0)
```

### Shipped-configuration exports (2026-09-29 / 2026-09-30)

Four families have been exported once at their **shipped configuration, random
weights** (the three ported families on 2026-09-29, CO-MOT on 2026-09-30); the
measurements are recorded in each family's `PROVENANCE.md`. What that establishes is
"the shipped size exports and the artifact is static":

| family | wall clock (CPU) | artifact | graph nodes | `literalised_dims` |
|---|---|---|---|---|
| `fdta` | 7.6 s | 27.5 MB | 604 | 0 |
| `memotr` | 14.0 s | 196.9 MB | 11419 | 0 |
| `sambamotr` | 14.0 s | 205.7 MB | 12099 | 0 |
| `comot` | ~14 s | 168.9 MB | 22277 | 11 |

The `comot` row: opset 17, torchscript exporter, pure CPU (the pure-Python
MSDA fallback — no CUDA extension, no download), 50 distinct op types. Its node
count is +296 against the shipped upstream artifact's 21,981 with an identical op
count — that delta is the torch version, which is exactly why the number is
recorded here rather than pinned in a test. `literalised_dims == 11` is structural:
13 outputs, of which only the two rank-1 counters (`next_next_id`,
`next_overflow_count`) come out with a literal batch axis.

---

## Evaluation and data

Evaluation is **library-only today**: the CLI `eval` subcommand is still an exit-1 stub
(see the table in [What works today](#what-works-today)). The two library entrances:

- `di_mot/eval/evaluator.py` — the in-process evaluator over the vendored TrackEval
  (TrackEval has no paper of its own; any reported HOTA number carries the HOTA
  citation — see [Citation](#citation)).
- `scripts/parity_real_data.py` — a standalone, non-pytest gate for **full-sequence,
  per-frame parity on real data** (DanceTrack). Its prerequisites — dataset root,
  seqmap, a real checkpoint and its config — are required arguments with no defaults,
  so it is a manual gate, not part of CI.

Dataset layout declarations for DanceTrack and MOT17 (plus SportsMOT, BFT, CrowdHuman,
BDD100K) live in `data/spec.py`. Official pages:

- MOT17 — <https://motchallenge.net/data/MOT17/>
- DanceTrack — <https://dancetrack.github.io/>

---

## Layout

```
di-e2e-mot/
├── pyproject.toml            # single source of dependency truth
├── LICENSE  NOTICE  THIRD_PARTY.md
├── di_mot/
│   ├── cli.py                # the only entry point
│   ├── core/                 # model-family-agnostic kernel
│   ├── models/               # {motr,comot,motip,memotr,sambamotr,
│   │                         #  dualtemporalmotr,fdta}/ + motr_family.py
│   │                         #  + export_recipes.py + structures/
│   ├── detectors/            # the vendored MSDeformAttn operator only
│   ├── util/                 # ported box/misc/checkpoint helpers
│   ├── data/                 # dataset layout declarations
│   ├── eval/                 # vendored TrackEval + evaluator
│   ├── deploy/               # export, parity, backends
│   └── legacy/               # pre-port scratch, intentionally not registered
├── examples/                 # first-run path: random-checkpoint maker + tiny YAMLs
├── tests/                    # the count drifts with every change; ask pytest
└── scripts/                  # port_closure, scan_leaks, parity, audit
```

### The graph boundary is a first-class fact

The two main families do not share a boundary, and the design says so rather than
pretending otherwise:

- **CO-MOT** — `IMAGE_TO_TRACKS`: the backbone is *inside* the exported graph.
- **MOTIP** — `DETECTIONS_TO_TRACKS`: the detector is *outside*; its five detection
  fields (`scores`, `categories`, `boxes`, `output_embeds`, `det_valid`) are graph
  inputs. The detector's `MultiScaleDeformableAttention` is a custom CUDA op with no
  ONNX expression yet.

A single `(image, state) → (detections, state)` contract would make the MOTIP export
impossible, so `GraphBoundary` is declared per family. The distinction reaches the
manifest too: on a `DETECTIONS_TO_TRACKS` artifact `image_shape` / `padding_mask_shape`
are recorded as `None` — "there is no image in the graph" is a fact to write into the
provenance, not a failure.

### Family-specific export constants

```
MIN_OPSET           {motr_family: 17, motip: 18}
EXPORTER_BY_FAMILY  {motr_family: "torchscript", motip: "dynamo"}
```

Both tables list exactly the two export families. The third table v0.1.0 carried —
`NO_EXPORT_PLAN_YET`, an exemption set holding `decodertracker` — was deleted with the
family; a registered family without an export path is no longer a representable state.

---

## Deployment

Two backends are registered — both consume the ONNX plus the sidecar manifest that
`dimot export` wrote beside it; a missing ONNX, or a missing/bad manifest, exits 2:

- **`tensorrt`** (2026-09-29): runs end to end through ONNX Runtime's
  TensorRT EP — engine build, artifact provenance, and `--measure N` latency
  (p50/p90/mean/std, on all-zero inputs; a fixed frame repeated N times). `dimot
  deploy` reads the plan from the sidecar manifest written by `dimot export`
  (`<onnx>.json`), builds/loads a TRT engine into `--out`'s engine cache, and
  writes `--out/artifact.json` (engine bytes, actual providers, TRT partition
  count, non-TRT node events). What it does **not** do yet: `run()` (actual
  inference) raises `NotImplementedError` — deploy completes convert + engine
  build + measurement, not prediction; and convert is fp32-only this round
  (non-fp32 precision plans raise). On an RTX 4090 host the engine/attribution/
  latency half **passed** acceptance (a 4498-node CO-MOT-topology fixture, opset
  17, fuses into **one** TRT partition with **zero** fallback nodes; p50
  25.67 ms ≈ 39 FPS). The first parity run **failed** on the two detection-head
  outputs (`pred_logits` max-abs 0.635 vs tolerance 0.074, constant across all 20
  frames); the cause was located on 2026-09-30 and it is a TensorRT defect rather
  than a tolerance question: TRT's cumulative layer **ignores the `axis` input of
  ONNX `CumSum`** and always accumulates along the last axis, which silently
  corrupted the detector's sinusoidal positional encoding (axis 1 of a `(1,H,W)`
  mask). `convert()` therefore lowers a graph to an equivalent
  `Transpose → MatMul(lower-triangular) → Transpose` form **before** the engine
  is built — only the nodes whose axis is not the last one, and only after the
  rewrite is shown bit-identical to the original on CPU. `artifact.json` records
  it: `lowerings` (e.g. `["cumsum-axis"]`) plus `source_onnx_path` /
  `source_onnx_sha256` pointing back at the untouched export, while `onnx_path`
  and `onnx_sha256` describe the graph actually handed to the session. The same
  fp32 parity gate then reports `pred_logits` 5.5e-05 and `pred_boxes` 4.1e-06 —
  **260/260 checks pass**. What is still not identical: with a *populated*
  tracking state (the shipped fixture detects nothing, so its three float state
  outputs are identically zero and prove nothing) `next_track_score` differs from
  the CPU reference by 1.4e-07 against a declared tolerance of 0.0 — the same
  0.0-tolerance-does-not-travel issue already recorded for plain ORT-CPU under
  the `comot` entry below. Full numbers:
  [docs/tensorrt-acceptance-2026-09-30.md](docs/tensorrt-acceptance-2026-09-30.md).
  Requires an NVIDIA GPU host with
  TensorRT 10.x (e.g. the `tensorrt` pip wheels; the exact pin is recorded
  outside this repo because the leak gate blocks IP-shaped version strings).
- **`horizon-s100`**: still a placeholder — `convert`/`run`/`measure` all raise
  `NotImplementedError` on their first line:

```
$ dimot deploy -c cfg.yaml --onnx out.onnx --backend horizon-s100 --out pkg/
dimot deploy: backend 'horizon-s100' is not runnable (NOT YET VALIDATED)
```

Ahead of the board work, two things *are* in place because they are
hardware-independent prerequisites: static shapes with literalised output dims,
and the parity gate.

Known blockers on the road to the board, from the design spec:

- CO-MOT's graph uses `GridSample` and `ScatterND`, whose documented BPU support differs
  by part: `ScatterND` is off-BPU on S100/S100P (nash-e/nash-m) and on-BPU with dtype
  and index constraints on the S600 class (nash-p); `GridSample` is on-BPU only under
  quantized-input constraints. Documented concerns, not measured results — the part
  naming follows the table in
  [Target platforms and roadmap](#target-platforms-and-roadmap).

---

## Target platforms and roadmap

The naming axis here is the **board**. The toolchain addresses parts by `march`, and
vendor documents of the same generation use J6 names; this table is where the three
vocabularies meet:

| README / backend name | Board | march (toolchain) | Vendor docs, same generation | Status |
|---|---|---|---|---|
| `horizon-s100` | RDK S100 / S100P | nash-e / nash-m | J6E / J6M | on sale |
| (not registered) | RDK S600 | nash-p | J6P (same march; the vendor has not stated same silicon) | on sale |

Body text in this README sticks to board names; `horizon-s100` is a registered backend
key and is not renamed to follow the board axis.

**Toolchain.** The target toolchain is Horizon OpenExplorer (OE), delivered as Docker
images (Ubuntu 22.04, Python 3.10). There are two public distribution lines — the RDK
S-series public package line (3.7.0 as of 2025-12) and the newer login-gated
vehicle-spec line (3.10.x as of 2026-09) — and their versions drift apart. This repo
names versions only as "line + version + as-of date" and pins no four-segment version,
under the same rule as the TensorRT pin note in [Deployment](#deployment).

**Quantization plan (PTQ first).** S100/S100P start from int8 with sensitive operators
kept in int16; the S600 class prefers fp16 with GEMM-family operators falling back to
int8. Calibration data is real dataset frames **plus the real cross-frame state
distribution** — an all-zero state is a known failure shape, not a neutral default
(vendor guidance: 20–100 calibration samples, kl/max). Acceptance is the existing fp32
parity harness followed by on-board TrackEval task metrics; cosine similarity alone does
not constitute acceptance — that is exactly the shape of the TensorRT lesson in
[Known issues](#known-issues).

**Size feasibility.** The shipped-configuration artifacts measure 27.5–205.7 MB (table
in [Quick start](#quick-start)) against 12–64 GB of board memory — two to three orders
of magnitude of headroom; latency on board is unmeasured. The vendor's published MOTR
reference for the S100P class (vendor name J6M; 65.3 MB main graph + 0.37 ms state subgraph, quantized MOTA
−0.007 vs fp32) says DETR-family MOT on BPU is a direction the vendor itself ships —
those are vendor-published reference numbers, not a commitment from this repository.

**What does not exist yet.** The edge path as a whole: `quantize` is an exit-1 stub (CLI
table in [What works today](#what-works-today)), the `horizon-s100` backend's three
methods raise `NotImplementedError` ([Deployment](#deployment)), and the repository
contains no BPU artifacts. This section is the "not built yet" ledger;
[Known issues](#known-issues) is the "built but defective" ledger. No dates are promised
for anything above.

---

## Known issues

- **The TensorRT backend used to fail the fp32 parity gate on the detection
  heads; the cause was a TensorRT `CumSum` defect, and the backend now works
  around it.** 2026-09-29: `pred_logits` max-abs error 0.635 (tolerance 0.074)
  and `pred_boxes` 0.202 (tolerance 0.011) against the ORT-CPU reference,
  constant across all 20 frames. 2026-09-30: a per-node probe run inside the TRT
  engine located the first divergent tensor — not in the heads but in the
  sinusoidal positional encoding, where TRT's cumulative layer had accumulated
  along the *last* axis for an ONNX `CumSum` that asked for axis 1 (the axis is
  an input tensor in ONNX, and TRT does not read it; the axis=2 and rank-2 nodes
  in the same graph were correct, which is why a single-node reproducer shows
  nothing — the node has to land inside a TRT partition first). `convert()` now
  lowers those nodes to an exactly equivalent lower-triangular MatMul form and
  records it in `artifact.json`; the gate then passes 260/260 with `pred_logits`
  5.5e-05 and `pred_boxes` 4.1e-06. **Still not equal, and not claimed to be**:
  (a) the three float state outputs are declared at tolerance **0.0**, a
  value measured on CUDA — with a genuinely populated state the TRT run differs
  from the ORT-CPU reference by 1.4e-07 on `next_track_score`, the same
  non-transfer of that 0.0 already recorded for ORT-CPU itself under the `comot`
  entry below; (b) the shipped 20-frame acceptance fixture detects nothing, so
  its "bit-exact state path" result is vacuous — the state path was only
  exercised by seeding a state by hand. See
  [docs/tensorrt-acceptance-2026-09-30.md](docs/tensorrt-acceptance-2026-09-30.md)
  for the four-run matrix (shipped vs lowered × cold vs populated state).
- **`comot`'s export path is now exercised, but only on random weights at the wiring
  level.** 2026-09-30: exported end to end with random weights and the upstream
  default configuration (`examples/comot-motr_co.yaml` — the repo's first CO-MOT
  config, since the factory needs the full 53-key upstream vocabulary and `.args`
  files cannot carry its list values). That run also fixed a real defect the old
  stub tests had masked: `CoMotOnnxBoundary` called the kernel with 9 flat state
  tensors while the real kernel's signature is `(image, state_object, padding_mask)`
  — the boundary↔kernel dialect adapter now lives in the boundary, and the stubs in
  `tests/deploy/test_export_comot.py` speak the real kernel dialect. Still **not**
  verified: real trained weights, and ORT parity under the 20-frame
  `CO_MOT_PRECISION` gate (a 3-frame CPU spot check on random weights passed at the
  default threshold; a birth-stress variant showed float state outputs at 1.9e-05
  vs the CUDA-calibrated 0.0 tolerance — CPU numerics, with all int/bool outputs
  bit-exact). Nothing here claims to reproduce upstream's published numbers —
  no real weights have been run.
- **The real CO-MOT model runs on CPU only through the pure-Python MSDA fallback.**
  `MultiScaleDeformableAttention` has no prebuilt CUDA extension (the build script is
  in `di_mot/detectors/ops/`); the Python fallback is what the 2026-09-30 export ran
  on (~14 s, one-time `RuntimeWarning`). `tests/deploy/test_export_comot.py` still
  keeps its minimal `_StubCore`, but for a different reason than before: that stub is
  the regression probe for the symbolic-output-dim defect, and the real kernel now
  crosses the boundary in the same file's real-export test.
- **Every export uses random weights.** The upstream checkpoints are unreachable from
  this machine (Google Drive / poisoned DNS), so no export path has ever run against
  trained weights; numerical conclusions rest on the per-family parity gates. (FDTA is
  the exception: it additionally performed one real forward against the released
  checkpoint, but that is a one-off record, not part of the test suite — see §5.1 of its
  `PROVENANCE.md`.)
- **The repository, distribution and import names disagree.** The repo is `di-e2e-mot`;
  `pyproject.toml` declares `name = "di-mot"`; `--version` prints `di-mot 0.2.0`; the
  import package is `di_mot` and the console script is `dimot`. Three names for one thing.
- **`dimot deploy` exits 1 for a valid backend and 2 for an unknown one.** Deliberate —
  two distinct observations, two distinct codes — but it surprises people.
- **`motr_family` exports ride torch's legacy TorchScript ONNX exporter, which PyTorch
  has deprecated and scheduled for removal.** The official replacement is the
  dynamo/`torch.export`-based exporter — already what the `motip` family uses. Migrating
  `motr_family` before the legacy exporter disappears is a standalone parity project of
  its own; on the torch version this repo currently pins, the existing path works.

---

## Licensing

Apache-2.0. See [`LICENSE`](LICENSE).

This product includes software developed by third parties. [`NOTICE`](NOTICE) lists the
holders; [`THIRD_PARTY.md`](THIRD_PARTY.md) maps each vendored tree to its upstream
project and license. Original upstream copyright headers are preserved verbatim and not
normalised. (v0.1.0 also carried one AGPL-3.0 subtree — the DecoderTracker `_agpl/`
tree; it was removed with the family in v0.2.0, and no AGPL code remains in this
repository.)

`scripts/scan_leaks.py` is a publish gate: it scans the tree for internal paths,
hostnames and RFC 1918 addresses and exits non-zero on a hit. It runs as part of the
test suite.

---

## Status

| Area | State |
|---|---|
| Model registry, state protocol, layout/capacity, GraphIO | ✅ implemented |
| Static-shape ONNX export layer + artifact manifest | ✅ implemented (library) |
| PyTorch ↔ ONNXRuntime parity gate | ✅ implemented, no CLI path |
| Metrics with provenance, TrackEval | ✅ implemented, no CLI path |
| `dimot export` (CLI) | ✅ five `(family, variant)` recipes; all five run end to end (`comot`: 2026-09-30, random weights — wiring-level only, see Known issues) |
| `dimot models` (CLI) | ✅ lists all seven variants with an `upstream` column |
| Four tracker ports (MeMOTR · SambaMOTR · DualTemporalMOT · FDTA) | ⚠️ **all `UNVALIDATED`** — none has reproduced upstream numbers. MeMOTR and SambaMOTR each have the dynamic trunk, a fixed-state core, a real static-shape export and a 20-frame parity gate (random weights; SambaMOTR is additionally shape-verified against the shipped checkpoint, 754/754 tensors); FDTA has a real export + parity gate against the released checkpoint; DualTemporalMOT is contract layer only. Per-family detail in `di_mot/models/<family>/PROVENANCE.md` |
| Shipped-configuration export (four families, random weights) | ✅ measured 2026-09-29 / 2026-09-30, recorded per family in `PROVENANCE.md` |
| Train / infer / eval / quantize / parity / capacity | ❌ stubs |
| CO-MOT real export | ⚠️ 2026-09-30: exported end to end (random weights, upstream default config, boundary↔kernel dialect adapter added; pure-Python MSDA fallback, no CUDA extension). Not verified: trained weights, 20-frame ORT parity under `CO_MOT_PRECISION` — still `UNVALIDATED` |
| TensorRT deploy backend (ORT TRT EP, fp32, convert+build+measure) | ⚠️ 2026-09-30: engine/attribution/latency validated; fp32 parity **PASSES** 260/260 after the `CumSum`-axis workaround (head outputs 5.5e-05/4.1e-06, was 0.635/0.202) and the rewrite is recorded in `artifact.json`; float state `next_track_score` is 1.4e-07 off against a 0.0 tolerance once a state is populated; `run()` not implemented — see `docs/tensorrt-acceptance-2026-09-30.md` |
| Horizon S100 backend | ❌ placeholder |
| Docs site, CI, examples | examples ✅ (2026-09-29, `examples/` + tests); CI ✅ (workflow in-repo, first run awaits org-side Actions enablement); docs site ❌ |

Contributions and bug reports are welcome, but please check the table above before
assuming something is broken — a large part of this repository is not built yet.

---

## Citation

If this toolkit is useful to you, cite it as:

```bibtex
@software{dirobotics2026dimot,
  author  = {{D-Robotics}},
  title   = {di-mot},
  year    = {2026},
  version = {0.2.0},
  url     = {https://github.com/D-Robotics/di-e2e-mot},
  note    = {Unified end-to-end multi-object tracking: one registry and state protocol for DETR-family trackers, static-graph ONNX export and deployment}
}
```

**The rule: whichever family you use, cite that family's upstream paper alongside
di-mot.** The vendored TrackEval has no paper of its own — any reported HOTA number
additionally requires the HOTA paper (below the table):

| di-mot family / package | Upstream paper | Venue | Upstream repository |
|---|---|---|---|
| `comot` (variant `motr_co`) | `yan2025comot` | ICLR 2025 Poster | <https://github.com/BingfengYan/CO-MOT> |
| `motr` (package; MOTR source via CO-MOT) and `legacy/` | `zeng2022motr` | ECCV 2022 | <https://github.com/megvii-research/MOTR> |
| `motip` | `gao2025motip` | CVPR 2025 | <https://github.com/MCG-NJU/MOTIP> |
| `memotr` (variant `motr_memotr`) | `gao2023memotr` | ICCV 2023 | <https://github.com/MCG-NJU/MeMOTR> |
| `sambamotr` (variant `motr_sambamotr`) | `segu2025samba` | ICLR 2025 Spotlight | <https://github.com/mattiasegu/sambamotr> |
| `fdta` (a `motip` variant) | `shao2026fdta` | CVPR 2026 | <https://github.com/Spongebobbbbbbbb/FDTA> |
| `dualtemporalmotr` (contract layer) | `kim2025dualpath` | NeurIPS 2025 | <https://github.com/altkddhfcjs/DualTemporalMOT> |
| `eval` (vendored TrackEval) | `luiten2021hota` (the paper) | IJCV 2021 | <https://github.com/JonathonLuiten/TrackEval> |
| shared components, as used | `zhu2021deformabledetr` · `carion2020detr` · `zhang2023dino` · `ge2021yolox` · `dai2017dcn` | — | see [`THIRD_PARTY.md`](THIRD_PARTY.md) |

The HOTA paper (the metric the vendored TrackEval computes):

```bibtex
@article{luiten2021hota,
  title   = {{HOTA}: A Higher Order Metric for Evaluating Multi-object Tracking},
  author  = {Luiten, Jonathon and Osep, Aljosa and Dendorfer, Patrick and Torr, Philip and Geiger, Andreas and Leal-Taixe, Laura and Leibe, Bastian},
  journal = {International Journal of Computer Vision},
  volume  = {129},
  pages   = {548--578},
  year    = {2021},
  doi     = {10.1007/s11263-020-01375-2},
  note    = {Published online 8 October 2020; official evaluation code: https://github.com/JonathonLuiten/TrackEval}
}
```

<details>
<summary>All 12 upstream BibTeX entries (the papers behind the families and components)</summary>

```bibtex
@inproceedings{zeng2022motr,
  title         = {{MOTR}: End-to-End Multiple-Object Tracking with Transformer},
  author        = {Zeng, Fangao and Dong, Bin and Zhang, Yuang and Wang, Tiancai and Zhang, Xiangyu and Wei, Yichen},
  booktitle     = {European Conference on Computer Vision (ECCV)},
  year          = {2022},
  eprint        = {2105.03247},
  archivePrefix = {arXiv},
  url           = {https://github.com/megvii-research/MOTR}
}

@inproceedings{yan2025comot,
  title         = {{CO-MOT}: Boosting End-to-end Transformer-based Multi-Object Tracking via Coopetition Label Assignment and Shadow Sets},
  author        = {Yan, Feng and Luo, Weixin and Zhong, Yujie and Gan, Yiyang and Ma, Lin},
  booktitle     = {International Conference on Learning Representations (ICLR)},
  year          = {2025},
  eprint        = {2305.12724},
  archivePrefix = {arXiv},
  url           = {https://openreview.net/forum?id=0ov0dMQ3mN}
}

@inproceedings{gao2025motip,
  title         = {Multiple Object Tracking as {ID} Prediction},
  author        = {Gao, Ruopeng and Qi, Ji and Wang, Limin},
  booktitle     = {Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)},
  pages         = {27883--27893},
  year          = {2025},
  eprint        = {2403.16848},
  archivePrefix = {arXiv},
  url           = {https://github.com/MCG-NJU/MOTIP}
}

@inproceedings{gao2023memotr,
  title         = {{MeMOTR}: Long-Term Memory-Augmented Transformer for Multi-Object Tracking},
  author        = {Gao, Ruopeng and Wang, Limin},
  booktitle     = {Proceedings of the IEEE/CVF International Conference on Computer Vision (ICCV)},
  pages         = {9901--9910},
  year          = {2023},
  eprint        = {2307.15700},
  archivePrefix = {arXiv},
  url           = {https://github.com/MCG-NJU/MeMOTR}
}

@inproceedings{segu2025samba,
  title         = {Samba: Synchronized Set-of-Sequences Modeling for Multiple Object Tracking},
  author        = {Segu, Mattia and Piccinelli, Luigi and Li, Siyuan and Yang, Yung-Hsu and Van Gool, Luc and Schiele, Bernt},
  booktitle     = {International Conference on Learning Representations (ICLR)},
  year          = {2025},
  note          = {Spotlight},
  eprint        = {2410.01806},
  archivePrefix = {arXiv},
  url           = {https://openreview.net/forum?id=OeBY9XqiTz}
}

@inproceedings{shao2026fdta,
  title         = {From Detection to Association: Learning Discriminative Object Embeddings for Multi-Object Tracking},
  author        = {Shao, Yuqing and Yang, Yuchen and Yu, Rui and Li, Weilong and Guo, Xu and Yan, Huaicheng and Wang, Wei and Sun, Xiao},
  booktitle     = {Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)},
  year          = {2026},
  eprint        = {2512.02392},
  archivePrefix = {arXiv},
  url           = {https://github.com/Spongebobbbbbbbb/FDTA}
}

@inproceedings{kim2025dualpath,
  title     = {Dual-Path Temporal Decoder for End-to-End Multi-Object Tracking},
  author    = {Kim, Hyunseop and Jeong, Juheon and Kim, Hanul and Koh, Yeong Jun},
  booktitle = {Advances in Neural Information Processing Systems (NeurIPS)},
  year      = {2025},
  url       = {https://openreview.net/forum?id=T64Fa2hCZn}
}

@inproceedings{zhu2021deformabledetr,
  title         = {Deformable {DETR}: Deformable Transformers for End-to-End Object Detection},
  author        = {Zhu, Xizhou and Su, Weijie and Lu, Lewei and Li, Bin and Wang, Xiaogang and Dai, Jifeng},
  booktitle     = {International Conference on Learning Representations (ICLR)},
  year          = {2021},
  note          = {Oral},
  eprint        = {2010.04159},
  archivePrefix = {arXiv}
}

@article{carion2020detr,
  title   = {End-to-End Object Detection with Transformers},
  author  = {Carion, Nicolas and Massa, Francisco and Synnaeve, Gabriel and Usunier, Nicolas and Kirillov, Alexander and Zagoruyko, Sergey},
  journal = {arXiv preprint arXiv:2005.12872},
  year    = {2020},
  eprint  = {2005.12872},
  archivePrefix = {arXiv}
}

@inproceedings{zhang2023dino,
  title         = {{DINO}: {DETR} with Improved DeNoising Anchor Boxes for End-to-End Object Detection},
  author        = {Zhang, Hao and Li, Feng and Liu, Shilong and Zhang, Lei and Su, Hang and Zhu, Jun and Ni, Lionel M. and Shum, Heung-Yeung},
  booktitle     = {International Conference on Learning Representations (ICLR)},
  year          = {2023},
  eprint        = {2203.03605},
  archivePrefix = {arXiv}
}

@article{ge2021yolox,
  title   = {{YOLOX}: Exceeding {YOLO} Series in 2021},
  author  = {Ge, Zheng and Liu, Songtao and Wang, Feng and Li, Zeming and Sun, Jian},
  journal = {arXiv preprint arXiv:2107.08430},
  year    = {2021},
  eprint  = {2107.08430},
  archivePrefix = {arXiv}
}

@inproceedings{dai2017dcn,
  title         = {Deformable Convolutional Networks},
  author        = {Dai, Jifeng and Qi, Haozhi and Xiong, Yuwen and Li, Yi and Zhang, Guodong and Hu, Han and Wei, Yichen},
  booktitle     = {Proceedings of the IEEE International Conference on Computer Vision (ICCV)},
  year          = {2017},
  eprint        = {1703.06211},
  archivePrefix = {arXiv}
}
```

</details>

