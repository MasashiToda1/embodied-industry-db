---
language:
- en
tags:
- robotics
- simulation
- pick-and-place
- manipulation
- ur10
- video
configs:
- config_name: ur10_seed0
  data_files:
  - split: train
    path:
    - robots/ur10/videos/*.mp4
    - robots/ur10/videos/metadata.jsonl
  drop_labels: true
---

# Pick-and-place dataset (format v1)

Robot pick-and-place trajectories collected with a scripted task-space expert and joint-space PD control. Each NPZ is one episode. The current release contains one UR10 with Robotiq-85 dataset: 32 valid episodes, 32 successful episodes, and 32 rendered videos.

## Repository layout and Hub preview

```text
README.md
robots/<robot_id>/
  README.md
  metadata.json              # Collection configuration, schema, ordering, and units
  summary.json               # Episode and outcome counts
  manifest.jsonl             # One complete index row per episode
  files.jsonl                # Size and SHA-256 inventory
  assets/<robot>.urdf        # Robot description used by the dataset
  episodes/*.npz             # State and control trajectories
  videos/*.mp4               # Rendered pose replays
  videos/metadata.jsonl      # Hugging Face VideoFolder browsing index
```

The YAML configuration selects the videos and their VideoFolder metadata. After upload and Hub processing, the Dataset Viewer can show a playable `video` column with robot ID, episode ID, action count, validity, success, termination reason, outcome label, failure cause, seed, and pointers to the NPZ and manifest.

`videos/metadata.jsonl` is a derived browsing index. Its `file_name` is relative to the `videos/` directory. `npz_path` and `manifest_path` are relative to the dataset root. `manifest.jsonl` remains the authoritative episode index, and `metadata.json` remains the authoritative schema and collection configuration. The Viewer does not expand NPZ arrays or automatically join manifest diagnostics.

The `train` split is a storage designation, not a curated training/evaluation partition. Preserve the directory structure when publishing. This is a native NPZ dataset with a VideoFolder browsing index, not a LeRobot export.

VideoFolder format: https://huggingface.co/docs/hub/datasets-video

## Current dataset

- Robot: UR10 with Robotiq-85 two-finger gripper
- Root seed: `0`
- Episodes: `32`
- Valid: `32`
- Successful: `32`
- Vector environments: `32`
- Control rate: `60 FPS` (`control_dt = 1/60 s`)
- Physics rate: `240 Hz` (`physics_dt = 1/240 s`)
- Object: `0.05 × 0.05 × 0.05 m`, `0.08 kg`
- Coordinate convention: metres, radians, seconds, +Z up, quaternions in wxyz order

## Randomization

Sampling is deterministic per episode. The episode seed is `root_seed + episode_id × 1,000,003`; retries also include the attempt index. Slot scheduling and vector-environment completion order do not change sampled values.

The following values are randomized independently for every episode and recorded in `manifest.jsonl` under `episode_spec`:

| value | distribution |
| --- | --- |
| Initial arm joints | Uniform jitter around the IK home solution: ±`[0.08, 0.06, 0.06, 0.06, 0.05, 0.08]` rad |
| Object X | Uniform in `[0.52, 0.58]` m |
| Object Y | Uniform in `[0.12, 0.18]` m |
| Goal X | Uniform in `[0.37, 0.43]` m |
| Goal Y | Uniform in `[-0.18, -0.12]` m |

Object and goal Z are fixed at `0.025 m`, half the cube height. Object yaw is fixed at `0` in this run. Object size, mass, friction, robot base pose, gripper parameters, PD gains, control timing, and task tolerances are not randomized. Samples violating joint limits or the minimum `0.15 m` transfer distance are rejected and resampled; rejection records are retained in `planning_rejections`.

## Trajectory fields

A trajectory with T actions stores T+1 measured states. Alignment is:

`state[t] → action[t] → state[t+1]`

The initial hold is included. State arrays use shape `(T+1, ...)`; transition/control arrays use `(T, ...)`. The same schema is machine-readable in `metadata.json` under `npz`.

| field | shape | dtype | description |
| --- | --- | --- | --- |
| `time` | `(T+1)` | float32 | Control time in seconds |
| `joint_position` | `(T+1, 8)` | float32 | Measured joint angles in radians |
| `joint_velocity` | `(T+1, 8)` | float32 | Measured joint velocities in rad/s |
| `joint_target` | `(T+1, 8)` | float32 | Active absolute joint target |
| `tcp_position` | `(T+1, 3)` | float32 | TCP position in metres |
| `tcp_quaternion` | `(T+1, 4)` | float32 | TCP orientation, wxyz |
| `object_position` | `(T+1, 3)` | float32 | Object position in metres |
| `object_quaternion` | `(T+1, 4)` | float32 | Object orientation, wxyz |
| `object_linear_velocity` | `(T+1, 3)` | float32 | Object linear velocity in m/s |
| `object_angular_velocity` | `(T+1, 3)` | float32 | Object angular velocity in rad/s |
| `goal_position` | `(T+1, 3)` | float32 | Episode placement target in metres |
| `gripper_contact` | `(T+1, 2)` | bool | Left/right configured finger contact |
| `body_position` | `(T+1, 18, 3)` | float32 | Recorded body positions for replay |
| `body_quaternion` | `(T+1, 18, 4)` | float32 | Recorded body orientations for replay, wxyz |
| `action` | `(T, 8)` | float32 | Absolute joint-position command |
| `control_mode` | `(T)` | int32 | `0=open/move`, `1=close`, `2=hold` |
| `payload_mass` | `(T)` | float32 | Payload mass used by feedforward compensation, kg |
| `pd_gains` | `(T, 8, 2)` | float32 | Applied `(kp, kd)` gains |
| `feedforward_torque` | `(T, 8)` | float32 | Applied feedforward torque in N·m |
| `expert_phase` | `(T)` | int32 | Index into `metadata.json: expert_phases` |
| `terminated` | `(T)` | bool | Terminal transition marker |
| `truncated` | `(T)` | bool | Timeout transition marker |

Joint order is stored in `metadata.json: joint_names`. Body order is stored in `metadata.json: body_names`; consumers should not infer either order from the URDF.

## Episode index and labels

Every `manifest.jsonl` row contains:

- Identity and storage: `episode_id`, `seed`, `episode_path`, `num_actions`.
- Primary labels: `valid`, `success`, `termination_reason`.
- Randomization: `episode_spec.initial_joints`, object pose, goal pose, episode seed, and attempt.
- Planning/validation: `planning_rejections`, `validation_errors`, and `error`.
- Video status: path, frame count, FPS, dimensions, replay source, and export error.
- Outcome label: `outcome.label`, `outcome.category`, `outcome.final_phase`, `outcome.failed_checks`, and `outcome.failure_cause`.
- Task diagnostics: maximum lift, final 3D/XY/height placement error, oriented-box bottom height, final object orientation error, final TCP position/orientation error, and final arm tracking error.
- Final checks: released, supported, slow, TCP clear, gripper contact, final linear speed, and final angular speed.

A successful episode must lift the object, release it, leave it supported near the goal, reach the stability thresholds, and clear the TCP. Final object orientation is recorded as a diagnostic but is not part of the success criterion.

Failure rows are retained. Possible termination or outcome labels distinguish planning failure, grasp failure, object drop/out-of-bounds, phase timeout, support timeout, invalid state, simulation error, and time limit. `failure_cause` contains a more specific derived cause when the recorded evidence supports one; otherwise it is null.

`valid` means the trajectory arrays satisfy the data contract. It does not mean the task succeeded.

## Videos and indexes

Videos are rendered from recorded body poses at the control rate. Physics is not rerun during video generation.

- Video frame `t` corresponds to NPZ `state[t]` and `time[t]`.
- T actions produce T+1 video frames.
- Playback time is `frame_index × control_dt`.
- Successful and failed valid trajectories are both eligible for video export.

`videos/metadata.jsonl` supports Hub browsing. `files.jsonl` inventories every published robot-dataset artifact except itself and records relative path, role, byte size, and SHA-256 checksum. `summary.json` provides aggregate episode, validity, success, termination, outcome, vector-environment, and execution-backend counts.

## Assets

Each robot directory stores one robot description at `assets/ur10_grip.urdf`. Mesh files are not duplicated into the dataset. The recorded body poses and exported videos remain the authoritative visual trajectory data.
