# T5T board views and governance signals

The Personal Edition Core Console uses T5T as an append-only project log.
The board's default **company core** view is a presentation projection over
known portfolio anchors:

- `wbc`
- `vlm-brain`
- `g1-wuji-teleoperation`
- `humanoid-foundation`
- `matrix-agentvla`
- `xviinfra`
- `metabot`

Projects remain ordinary T5T projects; this list does not create a second
hierarchy, change ownership, or persist metadata. Use **all projects** in the
console to inspect projects outside the projection.

The server also derives a `no_evaluator` anomaly when a project has no declared
evaluator and its 24-hour initialization grace period has elapsed. The signal
is computed from existing project and evaluator documents and does not mutate
T5T history. Newly-created projects are therefore not reported immediately.
