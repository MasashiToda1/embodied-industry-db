# Articulation

Local Articraft generation and HTTP service, copied from the GPU08 deployment at `gongsi / gensim-articulation`. It supports a compatible API gateway or a locally authenticated Codex CLI. The migration did not modify the remote service, its credentials, or other workspaces.

## Safety Boundary

**For trusted local users only.** Articraft executes model-generated Python and shell commands on the host. Child processes remove API-key environment variables, but this is not a security sandbox and does not isolate host files or Codex authentication. Do not accept untrusted prompts or expose this service directly to the public Internet.

Starting the service and running `doctor` do not invoke a model. `generate` and valid submissions to `/generate_articulation` invoke a real model and consume API credit or Codex quota.

## Start From a Clean Clone

The verified environment is Linux x86_64 with Python 3.11. The API backend does not require a baseline workspace or Codex login. After installing Conda, run:

```bash
git clone "https://github.com/DexForce/Articulation.git"
cd "Articulation"
conda env create -f "environment.yml"
conda activate agentable-articulation
python "scripts/bootstrap.py"
```

`bootstrap.py` creates an isolated `.venv`, installs the locked dependencies and both vendored packages, and runs an offline CAD/USDC smoke check. It refuses to overwrite an existing `.venv`. `environment.yml` supplies the matching Python and C++ runtime without modifying system libraries.

Configure your own repository-root `.env` using `.env.example`. Supply your own key and ensure that your account supports the selected model, Responses, image input, and function tools. The launcher reads `OPENAI_API_MODE=responses` and `OPENAI_REASONING_EFFORT=low` from the template; explicit command-line options override these values.

```bash
".venv/bin/python" "local.py" doctor --backend api
".venv/bin/python" "local.py" serve --backend api
```

The service runs in the foreground at `127.0.0.1:18688`. In another terminal, preflight or run the four bundled cases:

```bash
".venv/bin/python" "local.py" benchmark --backend api
".venv/bin/python" "local.py" benchmark --backend api --run --continue-on-failure
```

The first command does not invoke a model; the second consumes API credit. The four original images, manifest, and acceptance criteria are in `benchmarks/articulation/`. The launcher configures the current Python runtime's C++ library path for child processes, so no developer-specific absolute path is required. To use another port, pass the same `--port` to the service and benchmark commands.

`4/4` means that this particular run completed generation, download, and static USDC acceptance. It does not guarantee repeated success, identical latency, visual accuracy, or valid dynamics. Generated outputs and credentials are not distributed through Git.

A clean GitHub clone with a fresh Conda environment and venv passed installation, the offline USDC smoke check, 70 tests, and all four real API cases. The four cases took approximately 12 minutes 3 seconds. See the [benchmark validation record](benchmarks/articulation/README.md#clean-clone-validation) for the evidence boundaries and credential-free summary. The historical test prompts remain unchanged in the manifest; English descriptions are provided in that document.

## Default Configuration

| Backend | Address | Model and authentication |
| --- | --- | --- |
| `api` | `http://127.0.0.1:18688` | Reads `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and `OPENAI_MODEL` from the selected `.env` at startup |
| `codex` | `http://127.0.0.1:18689` | Local `codex`, existing login, `gpt-5.6-sol / low / Standard` |

The repository-root `.env` takes precedence. For compatibility with the original workspace, a missing root `.env` can fall back to the adjacent baseline configuration. Clean clones do not require that fallback. Use `--env-file` for another file and `--model` to override the model. Remote authentication is not copied. The API proxy comes only from `EMBODICHAIN_LLM_PROXY` in the selected file; an empty value means direct access, without inheriting global proxies. Codex uses the host's network environment and does not control remote Mihomo or switch routes automatically.

Without an explicit configuration, the API backend uses Chat Completions and preserves MiMo's provider-default thinking; `low` is not automatically mapped to a MiMo parameter. For a Responses-capable gateway, use `--api-mode responses --effort low`. Model ID, endpoint, and key still come from the selected `.env`. A complete endpoint URL does not receive a duplicate suffix. Running services do not automatically reload `.env`.

Use `--effort low|medium|high|xhigh` when starting, checking, or directly invoking the Codex backend.

The local Codex launch profile matches the GPU08 process configuration verified on 2026-10-08. It is defined by `CODEX_RUNTIME_PROFILE` in `local.py`. It overrides inherited values for the same runtime keys without modifying shell settings, global Codex configuration, or shared SDK defaults:

| Parameter | Local profile |
| --- | --- |
| Transport | Forced HTTPS; WebSocket disabled for initial and resumed turns |
| Turn protection | 120-second shadow deadline, 180-second no-progress hard deadline, 25-second reconnect protection |
| Recovery | Up to 3 attempts with one 600-second recovery budget; resume after transport failures, fresh context after invalid structured responses |
| Limits | 1800 seconds per CLI attempt, 100 agent turns, 900 seconds per compile, 7200 seconds per job, concurrency 1 |

The 180-second deadline restores the remote protection setting; it is not a universal cure for stream disconnects or slow inference. Local CLI version, login, and proxy are retained. Remote credentials are not copied, and the CLI is not downgraded. `doctor` does not verify account access to a model or long-stream reliability.

Explicit `--fast` forwards `service_tier="fast"` and `features.fast_mode=true` on initial and resumed turns. Standard forwards `service_tier="default"` and `features.fast_mode=false`. Neither modifies global user configuration. According to the [official configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference), Fast requests the `priority` tier; availability depends on the account and model. Fast consumes more quota.

Each backend runs one job at a time. Artifacts are stored separately in `outputs/api/` and `outputs/codex/`. Local execution avoids the remote queue but does not guarantee faster inference.

## Run

Run these commands from the repository root:

```bash
".venv/bin/python" "local.py" doctor --backend api
".venv/bin/python" "local.py" doctor --backend codex
".venv/bin/python" "local.py" serve --backend api
```

Start the Codex backend in another terminal:

```bash
".venv/bin/python" "local.py" serve --backend codex
```

Stop foreground services with `Ctrl+C`. Automatic startup at boot is not configured. Background process IDs and logs from the initial migration are stored in the ignored `.runtime/` directory. Check existing processes and ports before restarting to avoid duplicate services.

Start a Responses backend after confirming that the previous API service has no active jobs and has stopped:

```bash
".venv/bin/python" "local.py" doctor --backend api --api-mode responses --effort low
".venv/bin/python" "local.py" serve --backend api --api-mode responses --effort low
```

Responses mode reuses the existing OpenAI message, tool, and checkpoint logic over the configured HTTP gateway. It does not use the fixed official WebSocket endpoint or invoke Codex CLI. Requests use `store=false` and replay existing Responses items client-side, preserving encrypted reasoning and tool outputs. HTTP status, timing, model, requested/returned effort, and token counts are recorded in `compatible-api-diagnostics/`; request bodies, images, authentication headers, and keys are not stored. Authentication failures are not retried. Transport and retryable HTTP failures are bounded by `OPENAI_MAX_ATTEMPTS` in `.env`.

## Call the Service

```bash
".venv/bin/python" "local.py" client --backend api health
".venv/bin/python" "local.py" client --backend codex health
```

The following command invokes a real model and waits for the result:

```bash
".venv/bin/python" "local.py" client --backend api generate \
  "Reconstruct this object with one valid articulation and export USDC." \
  --image "/absolute/path/reference.png" --artifact usdc --output "outputs/object.usdc"
```

Replace `--backend api` with `--backend codex` to use local Codex. Generation can also run without an HTTP service:

```bash
".venv/bin/python" "local.py" generate --backend api "a hinged box"
```

The HTTP protocol provides `GET /health`, `POST /generate_articulation` (JSON prompt or multipart prompt/image), `GET /tasks/<request_id>`, `POST /tasks/<request_id>/cancel`, and `GET /assets/<request_id>/usdc`. No additional service authentication is implemented. A healthy service or a `succeeded` job alone does not establish valid USDC output; inspect the downloaded artifact.

## Verify and Rebuild

```bash
".venv/bin/python" "local.py" smoke
LD_LIBRARY_PATH="$CONDA_PREFIX/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" ".venv/bin/python" -m pytest -q
```

`smoke` compiles a fixed CAD fixture without model requests. It verifies real compilation, USDZ-to-USDC export, binary format, joint/body structure, offline HTTP queuing, and download consistency. It does not verify real model generation, live proxy behavior, dynamics, or manipulation-task success.

Tests also start a temporary loopback mock model and exercise the real service worker through `write -> compile -> finish`, followed by USDC download acceptance. Codex protocol tests replace only the model execution result. These tests do not consume real model credit.

### P1 Regression Checks

CLI reconnect messages such as `Reconnecting... N/M (request timed out)` are correctly classified. A recovered turn is accepted only when the process exits successfully, the watchdog has not fired, the final event is `turn.completed`, no terminal failure event exists, and the structured response is valid. Authentication, quota, unknown errors, and invalid tool arguments remain rejected. Unrecovered reconnect timeouts use the existing bounded retry path; HTTP jobs are not automatically resubmitted.

Regression tests cover a reduced saved medium/Stapler failure, rejection of genuine failures, resume/fresh recovery budgets, and initial/resume runtime flags. Verify the installed CLI against a loopback mock API without real inference or credentials:

```bash
LD_LIBRARY_PATH="$CONDA_PREFIX/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" ".venv/bin/python" -m scripts.probe_fast_tier --cloud-profile
```

The existing restart utility validates PID, workspace, and service identity and refuses to restart while jobs are active. The following applies the profile to the local Codex service without submitting generation jobs or changing the API backend:

```bash
LD_LIBRARY_PATH="$CONDA_PREFIX/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" ".venv/bin/python" -c \
  'import json; from scripts.compare_sol56 import restart; print(json.dumps(restart("low", service_tier="default", align_runtime=True), indent=2))'
```

### Historical Image Benchmark

```bash
".venv/bin/python" "local.py" benchmark --backend codex
```

The default is preflight only. Explicit `--run` consumes local Codex quota and runs Bell, Switch, Stapler, and Microwave in the original order. Use `--cases bell` for Bell only. The default input is the bundled `benchmarks/articulation/manifest.json`, with no baseline2 dependency. Original image bytes and test prompts are preserved, and image hashes and dimensions are checked. Override the manifest with `--manifest`.

The same driver supports `--backend api`, using `127.0.0.1:18688` and `outputs/api/` with identical inputs, acceptance rules, and time limits:

```bash
".venv/bin/python" "local.py" benchmark --backend api --run --continue-on-failure
```

API and Codex differ in protocol, output budget, and transport. Cross-backend results are not a strict single-factor comparison. Gateway billing does not use the SDK's static OpenAI price table; `cost=0` means uncalculated, not free.

Each run gets a separate directory under `outputs/benchmarks/`, containing request IDs, input copies, task state, downloaded USDC, hashes, and independent OpenUSD checks. Submissions are not automatically retried. By default, later cases stop after the first failure to avoid duplicate paid work. Static acceptance checks required joint counts, root/body relationships, valid targets and limits, authored mass/inertia, and asset dependencies. Missing mass properties are reported separately and do not count as dynamics qualification.

`--continue-on-failure` submits each of the four cases once even if a prior case fails. An uncertain submission still stops immediately without automatic resubmission. Earlier `xhigh` comparisons retained their original watchdog settings; the P1-fixed default uses the profile above. Historical results are not rewritten, and runs with different runtime profiles must not be presented as effort-only comparisons.

Reproduce the approved two-group GPT-5.6-Sol comparison with the following command. Without `--run`, it does not execute; with `--run`, it restarts an idle local Codex service and submits eight real cases:

```bash
LD_LIBRARY_PATH="$CONDA_PREFIX/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" ".venv/bin/python" -m scripts.compare_sol56 --run
```

The order is four `medium` cases followed by four `xhigh` cases. The runner changes the model and effort, explicitly restores Standard tier, and preserves proxy, watchdog, and acceptance settings. The service remains on `gpt-5.6-sol / xhigh` afterward.

Run four GPT-6-Luna / xhigh / Fast cases:

```bash
LD_LIBRARY_PATH="$CONDA_PREFIX/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" ".venv/bin/python" -m scripts.benchmark_luna_fast --run
```

The historical Luna run explicitly requested Fast before reconnect classification and watchdog alignment were repaired. This script changes only model, effort, and tier; other settings come from the running service. New runs must be distinguished from those older records. Each case is submitted once, and the service retains the tested configuration. The Sol comparison explicitly restores Standard tier so Fast cannot silently contaminate that comparison.

Use `environment.yml` and `scripts/bootstrap.py` for dependency installation and offline compilation checks. They do not depend on the original developer's Conda environment name or absolute paths. `local.py` injects the current Python runtime's C++ library path and local settings only into child processes, without changing shell configuration. Do not launch with system Python 3.10.

## Provenance and Adaptations

- Copy date: 2026-10-08. Container image: `sha256:da95805fb2c0eccb236597daf0d5ceddc8fe4be413c6c57a08b78475f50369c2`.
- The remote `/opt/Articraft/src/articraft` and `/opt/articulation-server/src/articulation_server` matched the deployed packages when compared. The container had no Git metadata, so an upstream commit cannot be claimed.
- `vendor/Articraft` retains its Apache-2.0 license. The service wrapper has no separate license file; local use alone does not establish public redistribution rights.
- The copy excluded build directories, egg-info, caches, Git metadata, and `.env`. Historical runs/jobs, authentication volumes, and proxy configuration were not copied. Original file hashes are in `cloud-source.sha256`; package versions are in `requirements-cloud.lock`.
- The local `compatible-api` provider handles images, tools, MiMo `reasoning_content` replay, bounded retries, and rejection of incomplete output. HTTP Responses mode reuses existing OpenAI conversation logic rather than introducing a second agent executor.
- Venv interpreter symlink handling was fixed in the server configuration. Local launch, credential loading, and offline verification live in `local.py`, `scripts/`, and `tests/`.
- Compatible API `cost=0` means provider pricing is not calculated, not that requests are free. Token usage is retained. MiMo thinking uses provider defaults; Codex `medium` is not mapped to a MiMo parameter.
- Git excludes `.venv`, generated output, logs, `.env`, and authentication files. A clone does not carry host credentials, running-service configuration, or generated benchmark artifacts.

Protocol references: [MiMo Chat Completions](https://mimo.mi.com/docs/en-US/api/chat), [MiMo thinking mode](https://mimo.mi.com/docs/en-US/quick-start/usage-guide/other/deep-thinking), and [Codex non-interactive execution](https://developers.openai.com/codex/noninteractive/).
