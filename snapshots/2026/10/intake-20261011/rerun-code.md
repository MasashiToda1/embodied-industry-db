# Finding the training data your robot policy is missing

This example runs a full imitation-learning workflow with Rerun: record demos, review them, generate counterfactual
variations, measure how much each one moves a trained policy's actions, select a small repair set, fine-tune, and
evaluate. Every intermediate result is stored as a Rerun recording, layer, or table, so you can query it and look at
it in the viewer.

It follows the method from _[It's Not Just More Demos](https://arxiv.org/abs/2607.27261)_ (D'urso et al., 2026) and
is the code behind the Rerun blog post
[Finding the training data your robot policy is missing](https://rerun.io/blog/counterfactual-learning).
It has two parts:

- **Simulation:** ACT (action chunking transformer) on the bimanual MuJoCo cube-transfer task from the
  [original ACT repo](https://github.com/tonyzhaozh/act).
- **Real data:** the same workflow on
  [`lerobot/aloha_static_cups_open`](https://huggingface.co/datasets/lerobot/aloha_static_cups_open), offline.

Everything runs against the **open-source Rerun server**. If you have access to a Rerun Hub, the same code works
against it too (see [Using a Rerun Hub](#using-a-rerun-hub)).

[NOTES.md](NOTES.md) collects the things we found along the way: data problems, metric problems, and practical tips.

## Requirements

- Tested on macOS with an Apple silicon GPU (`ACT_DEVICE=mps`). The code also takes `cuda` or `cpu`, but those paths
  haven't been run end to end. CPU works for the review and selection steps but is far too slow for training.
- [`uv`](https://docs.astral.sh/uv/) for the Python environment, and `git`.
- MuJoCo rendering needs a display on macOS: run the scripts from a normal terminal session, not over SSH.
- Disk: plan for about 40 GB with one training seed. Most of it is evaluation rollouts (camera video plus simulator
  state for every step) and checkpoints.
- Time on an M4 Pro: about 8 hours for the simulation part with one seed, and about 5 more for the real-data part.
  Training and closed-loop evaluation are most of it.

## Setup

```sh
bash scripts/setup.sh        # Python env in .venv, ACT cloned at a pinned commit with act.patch applied
bash scripts/check_env.sh    # GPU and MuJoCo rendering work
bash scripts/smoke_test.sh   # optional: 3 demos, 5 epochs, 1 rollout (a few minutes)
```

`act.patch` is a small set of changes to ACT: a configurable device, seeded evaluation over 100 rollouts, the full
simulator state saved with every demo, Rerun logging hooks for training and rollouts, and the nuisance scene used for
counterfactuals.

## Running it

Start the catalog server in its own terminal and leave it running:

```sh
bash scripts/serve.sh        # open-source Rerun server on rerun+http://127.0.0.1:51234
```

It registers everything under `rerun/` (datasets, layers, tables, viewer blueprints) when it starts. The files are the
source of truth, so you can stop and restart it at any time. Open the same URL in the viewer:

```sh
rerun rerun+http://127.0.0.1:51234
```

Then run the steps in order. Each script is resumable: re-running skips work that's already done.

| Script | What it does | Time | What to look at |
|---|---|---|---|
| `01_record_demos.sh` | 50 scripted demos with full simulator state, exported to Rerun | ~15 min | `cube_demos` |
| `02_train_nominal.sh` | Train ACT for 2000 epochs (seed 0; `SEEDS="0 1 2"` for three) | ~1.5 h per seed | `cube_training` |
| `03_review.sh` | QA metrics as a layer and segment properties; a review checklist | ~2 min | sort `cube_demos` by `qa:lift_gap` |
| `04_counterfactuals.sh` | Task-preservation checks, evaluation under 11 conditions, action drift | ~2.5 h per seed | `task_preservation` and `drift_candidates` tables; `cube_rollouts` sorted by `qa:final_cube_z` |
| `05_select.sh` | Three K=20 selections; ghost arms for the top-drift episodes | ~2 min | `repair_selections` table; 3D view of the top episode |
| `06_repair.sh` | Fine-tune on each selection, streaming from the catalog, then evaluate | ~3.5 h | repaired rollouts in `cube_rollouts` |
| `07_real_data.sh` | Download, ingest, QA, edits, drift, selection, repair, offline eval on real data | ~5 h | sort `real_demos` by `qa:gripper_reversals` |

Results land in `results/` (CSV summaries and review checklists) and in the catalog. `reference_results/` has our
numbers to compare against.

## How the data is organized

Each episode is a segment in a Rerun dataset (`cube_demos`, `cube_rollouts`, `cube_training`, `real_demos`). Anything
computed later is written as a _layer_: another `.rrd` file with the same recording id, registered on the dataset
under a name. The server merges all layers of a segment when you query it or open it in the viewer, so the
counterfactual frames, predictions, QA metrics, masks, and 3D scenes all line up with the original episode on the
same timeline.

```
rerun/
  demos/                      cube_demos, layer "base"
  counterfactual/<condition>/ re-rendered frames + predictions + drift, layer <condition>
  qa/, scene3d/, train_pad/   more cube_demos layers
  ghost/ghost_<condition>/    the policy's intended pose under clean vs. counterfactual frames
  rollouts/, rollout_qa/, rollout_scene3d/   cube_rollouts and its layers
  training/                   cube_training (loss curves per run)
  real_demos/, real_*/        real_demos and its layers
  tables/<name>/              Lance tables: dataset_defs, task_preservation, drift_candidates, repair_selections, ...
  blueprints/                 viewer layouts, registered as each dataset's default
```

The code is in `cfnbc/cfnbc/`. The main entry points:

| Module | Purpose |
|---|---|
| `serve` | start the open-source catalog server over `rerun/` |
| `hub` | catalog access (`open_catalog`), `sync` to register new files with a running server |
| `export_demos`, `act_hooks` | demos, training runs, and rollouts as Rerun recordings |
| `qa` | QA layer and properties for demos and rollouts |
| `nuisance`, `counterfactual` | the counterfactual scene variations and re-rendering from recorded state |
| `scene3d`, `task_preservation` | 3D scenes from recorded state, and the geometric checks |
| `compute_drift`, `drift_query` | action drift with frames and predictions as layers; the same drift as a catalog query |
| `selection` | top-drift, random, and drift-weighted coverage selection, stored as a table |
| `clean_stream`, `repair_data`, `finetune` | training straight from the catalog (`RerunIterableDataset` for the clean demos, `RerunMapDataset` for the repair set) |
| `fast_eval` | closed-loop evaluation with several environments in lockstep |
| `ghost` | ghost arms: predicted actions posed as robot meshes |
| `real/` | the real-data pipeline: ingest, QA, frame edits with masks, drift, training, offline evaluation |

## Using a Rerun Hub

Point the tools at the Hub instead of the local server, and tell them it's a Hub (Hubs manage table storage
themselves):

```sh
export CFNBC_CATALOG_URL=rerun+https://<your-hub>
export CFNBC_HUB=1
export CFNBC_STORAGE_PREFIX=<file:// or s3:// location the Hub can read rerun/ files from>
python -m cfnbc.hub sync      # register everything under rerun/
```

With a storage prefix set, `hub sync` copies `file://` targets for you; for `s3://` sync `rerun/` there yourself.

## Licenses and citations

The code in this repository is MIT licensed (see [LICENSE](LICENSE)). `act.patch` modifies
[ACT](https://github.com/tonyzhaozh/act) (MIT, Tony Z. Zhao). The real-data part downloads
[`lerobot/aloha_static_cups_open`](https://huggingface.co/datasets/lerobot/aloha_static_cups_open) (MIT); the edits
and predictions this example makes are derived from it and are not redistributed here.

If you use the method, cite the paper it comes from:

```bibtex
@article{durso2026notjustmoredemos,
  title   = {It's Not Just More Demos: Counterfactual Action Sensitivity Coverage for Data-Efficient Robust Robot Imitation},
  author  = {D'urso and Roy and Lawrance and Tidd},
  journal = {arXiv preprint arXiv:2607.27261},
  year    = {2026}
}
```

For ACT and the ALOHA data:

```bibtex
@article{Zhao2023LearningFB,
  title   = {Learning Fine-Grained Bimanual Manipulation with Low-Cost Hardware},
  author  = {Tony Zhao and Vikash Kumar and Sergey Levine and Chelsea Finn},
  journal = {RSS},
  year    = {2023},
  url     = {https://arxiv.org/abs/2304.13705}
}
```
