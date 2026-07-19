# Orin NX EIS Harness Engineering V1

## Purpose

This harness is a small control plane for the Orin NX EIS project. It is not a
new algorithm framework and not a dashboard. Its job is to make every AI-assisted
experiment reproducible, reviewable, and stoppable.

The core rule is:

```text
Do not let an agent change an EIS configuration unless the clip role,
frozen variables, validators, evidence paths, and stop reasons are known.
```

## What Is Fixed

`configs/harness/gates.json` defines the current test-set boundary:

| Gate | Role | Use |
|---|---|---|
| `smoke_ostrich` | smoke | Fast script sanity only |
| `nus_regular_gate_v1` | main quality gate | Current primary quality and display pool |
| `nus_running_gate_v1` | challenge gate | Failure-boundary and scene-gate degradation evidence |
| `regular05_perf_gate` | performance gate | Same-input Jetson runtime evidence |

The main project claim must come from Regular, not Running. Running is a model
boundary set for the current pure-visual global-affine pipeline.

## Done Contract

Each real experiment starts from a Done Contract under
`configs/harness/contracts/`.

## Progressive Onboarding

Default startup should not load every long document and reference folder.

Use the lightweight onboarding manifest first:

```text
configs/harness/onboarding_manifest.json
```

Command:

```powershell
py -3.12 scripts\harness_runner.py onboard
```

This command names the active overall loop contract and the current task-specific
contract. It also lists which long documents are on-demand only. The long-term
context document and internal camera-reference folders are not default preflight
loads; open them only when the current loop, blocker, or manifest trigger points
to a specific section or source.

Loop Engineering V2 adds a decision layer above this harness:

```text
docs/loop_engineering_v2.md
docs/evaluation_system_v1.md
configs/harness/loop_profiles.json
configs/harness/evaluation_datasets.json
configs/harness/metric_schema.json
```

Before a substantial run, choose a loop profile and name the external
observation that will decide whether the loop may continue. Agent self-report is
not evidence.

The first contract is:

```text
configs/harness/contracts/jetson_regular05_perf.json
```

It freezes the current stage evidence configuration:

```text
regular_gate05_regular_6.mp4
lp_rigid
stabilization_strength=0.80
crop_ratio=0.90
crop_interpolation=lanczos
sharpen_strength=0.25
lp_trim_ratio=0.10
lp_w1/lp_w2/lp_w3/lp_w4=50/10/20/30
dynamic_zoom=true, max_zoom=1.06, zoom_rate_limit=0.003
scene_gate_policy=weak
warp_backend=opencv_cpu
```

Only the runtime platform is allowed to change in that contract.

This baseline was promoted after user review of the regular05 tail. The previous
full-strength affine/rigid variants reduced some objective motion but left
visible tail jitter or corner-pull. The accepted baseline deliberately weakens
the global rigid correction to reduce local pull risk. It is a practical CPU
baseline, not a claim that global-warp EIS has solved all local/parallax cases.

## Commands

Check that the configured gates still exist:

```powershell
py -3.12 scripts\harness_runner.py doctor
```

List gate roles:

```powershell
py -3.12 scripts\harness_runner.py list-gates
```

Check whether a gate can support a claim:

```powershell
py -3.12 scripts\harness_runner.py check-claim --gate-id nus_running_gate_v1 --claim main_gate_success_rate
```

Return codes:

```text
0 = claim is allowed
1 = claim is unknown for this gate
2 = claim is explicitly forbidden
```

Print the active contract:

```powershell
py -3.12 scripts\harness_runner.py print-contract
```

List lifecycle evaluation datasets and metric layers:

```powershell
py -3.12 scripts\harness_runner.py list-evaluation-datasets
py -3.12 scripts\harness_runner.py check-evaluation-datasets
py -3.12 scripts\harness_runner.py list-metric-schema
```

Create a dated evidence package:

```powershell
py -3.12 scripts\harness_runner.py init-evidence --date 20260717 --platform-label jetson
```

For harness self-tests that intentionally run on Windows and must not be treated
as project progress, mark the package explicitly:

```powershell
py -3.12 scripts\harness_runner.py init-evidence --date 20990104 --platform-label windows_simulation --self-test
```

Print the reproducible commands for the contract:

```powershell
py -3.12 scripts\harness_runner.py print-commands --date 20260717
```

Validate an evidence package after a run:

```powershell
py -3.12 scripts\harness_runner.py validate-evidence results\evidence\20260717_jetson_regular05_perf
```

`validate-evidence` is expected to fail immediately after `init-evidence`,
because the run has not produced the stabilized video, metrics, summary, and
comparison video yet. It should pass only after the commands in `commands.txt`
have run successfully and the review copy exists.

## Evidence Rules

An evidence package is valid only if it contains:

```text
contract.json
run_metadata.json
commands.txt
stabilized mp4
metrics csv
summary csv
side-by-side mp4
human_review.csv
```

If performance is discussed, the summary must contain:

```text
avg_estimate_ms
avg_warp_ms
total_wall_time_s
```

Real performance evidence for `jetson_regular05_perf` must also have:

```text
run_metadata.json: platform_label = jetson
```

Self-test packages may use `platform_label = windows_simulation`, but they must
also set `is_harness_self_test = true` and must not be cited as project progress.

Reviewable videos must also be copied to the stable review tree:

```text
C:\Users\Admin\Videos\orin nx\review\<category>\<YYYYMMDD>_<loop_or_gate>
```

Use these categories:

| Category | Use |
|---|---|
| `performance` | Jetson timing and same-input performance evidence |
| `quality` | Main Regular quality review assets |
| `challenge` | Running / QuickRotation / Parallax boundary assets |
| `diagnostic` | Zooming / Crowd / metric-debug assets |
| `archive` | Historical one-off review copies kept only for reference |

For the current `jetson_regular05_perf` contract, the review directory is:

```text
C:\Users\Admin\Videos\orin nx\review\performance\<YYYYMMDD>_jetson_regular05_perf
```

Review video filenames must include enough context to avoid duplicate-looking
files:

```text
<YYYYMMDD>_<gate_id>_<clip_stem>_<platform>_<config_slug>_<asset_kind>.mp4
```

Example:

```text
20260718_regular05_perf_gate_regular_gate05_regular_6_jetson_crop90_dynzoom1p06_lanczos_sharp0p25_lp_rigid_opencv_cpu_est1p0_strength0p8_compare.mp4
```

Do not use bare names such as
`regular_gate05_regular_6_new_crop90_lanczos_sharp025_compare.mp4` in the review
root for new runs. Those names are allowed inside the reproducible
`results/evidence/...` package, but the user-facing review copy must be dated,
categorized, and gate/platform/config qualified.

## Manual Veto

Metrics are not enough. Any of these visual failures veto a result:

```text
frame shift
rollback / snapback
jello or rolling-shutter-like artifact
local distortion or corner pull
continuous black border
unacceptable blur or detail loss
```

If manual review vetoes a result, do not argue from SR/residual metrics. Mark
the run as failed or diagnostic.

## Stop Rules

Stop the current unsafe or unproductive action instead of blindly repeating it
when:

- two attempts improve one metric but worsen visual quality or hard gates;
- a change helps Running while hurting Regular;
- a performance change changes output semantics;
- required command/config/metrics/video evidence is missing;
- the next fix requires gyro, mesh, or RS support outside the current pipeline;
- the agent cannot explain why a change helped and what it costs.

Stopping the current action is not the same as stopping the project track.

If an experiment produces a negative result, preserve the evidence and route the
next attempt instead of retreating to the stable baseline:

| Negative result | Do not conclude | Required recovery route |
|---|---|---|
| VPI backend replacement is slower | VPI acceleration is impossible | Build/check backend support, measure module-level cost, or isolate conversion/readback overhead |
| Python GStreamer round trip is too costly | GStreamer/NVMM is useless | Move to non-Python NVMM, CUDA, C++, or hardware decode/encode boundary work |
| Challenge set fails | EIS project is finished or hopeless | Keep Challenge as boundary evidence and continue Regular-performance or next-model exploration |
| CPU baseline is accepted | Project is done | Commit/preserve the checkpoint, then continue the unfinished core track |

The harness must keep these active core tracks visible until they are explicitly
completed or the user changes the target:

1. VPI backend validation and heterogeneous acceleration.
2. Algorithm cost reduction plus zero-copy or non-Python pipeline exploration.
3. Hardware decode/encode, power modes, perf/watt, and quality/crop trade-off.

## Knowledge Base Recovery

When a stop rule or material blocker is hit, use the external knowledge base as a
recovery aid instead of repeating the same local action:

```text
docs/knowledge_base/routing.md
```

The knowledge base is not a default preflight load. Open it only when the loop is
stuck, when a new technical domain is entered, or when VPI/CUDA/GStreamer/NVMM
usage needs an outside reference. Read at most two matched source cards before
returning to a scoped Done Contract.

Company/internal Typora references are routed through the local-only index:

```text
.local_knowledge/internal_reference_index.md
```

That directory is ignored by Git. Do not copy internal original text into public
project docs.

## Loop Engineering V2

The current project should remain at autonomy level `L2/L3`: scoped single
actions or contracted loops with hard validators. Do not build scheduled
automation, multi-worktree pipelines, automatic PRs, or self-improving harness
mutation for this stage.

Use these profiles:

| Profile | Use |
|---|---|
| `performance_loop` | Same-input Jetson timing, backend, or dataflow evidence |
| `quality_loop` | One EIS algorithm/config variable with metrics plus visual review |
| `scene_gate_loop` | Scene role or degradation-policy changes |
| `evaluation_loop` | Metric/report/human-review schema changes |
| `knowledge_recovery_loop` | Read outside references after a real blocker |
| `documentation_loop` | Wording, routing, and evidence packaging only |
| `device_recovery_loop` | USB SSH or Jetson runtime recovery |

The detailed design lives in:

```text
docs/loop_engineering_v2.md
```

## Current Next Action

The Jetson same-input CPU baseline evidence for `regular_gate05_regular_6.mp4`
has been recorded and validates under the current Done Contract:

```powershell
py -3.12 scripts\harness_runner.py validate-evidence results\evidence\20260718_jetson_regular05_perf --date 20260718
```

The frozen stage baseline is now `lp_rigid_strength080_dynzoom106`. Same-input
backend comparison shows that `vpi_cpu`, `vpi_cuda`, and `vpi_vic` are all slower
than `opencv_cpu` for the current 640x360 Python full-pipeline path. Do not claim
VPI full-pipeline acceleration from that result.

Update - anti-retreat correction:

```text
The CPU baseline and its Git/evidence checkpoint are not the final goal.
The next project work should return to the three unfinished core tracks:
VPI backend validation, non-Python dataflow/zero-copy or pipeline work, and
NVDEC/NVENC plus power/perf evaluation.
```

Update - device-side path:

```text
The current acceleration frontier is no longer Python appsink/appsrc or a simple
VPI backend swap. MMAPI experiments have validated a device-side path:

H264 input -> decode/NvBufSurface -> scratch pitch-linear NV12_ER -> VPI CUDA
warp -> block-linear NV12 -> NVENC.

The current useful loop is to validate same-source inverse-matrix device output
against CPU stabilized output and then decide whether it is a stage demo or
needs more matrix/crop/zoom alignment work.

2026-07-19 boundary update:

```text
Same-source inverse-matrix output has normal sampled black-border sanity, so the
device-side warp/encode path is valid as a stage boundary. A 120-frame local
panel comparison still shows a large CPU-vs-device parity gap, so the result is
not CPU-output equivalence. Use configs/harness/contracts/device_matrix_warp_demo_v1.json
and docs/device_matrix_warp_demo_2026-07-19.md for this claim boundary.
```
```
