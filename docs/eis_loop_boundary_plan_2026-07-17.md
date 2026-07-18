# Jetson Orin NX EIS Boundary And Loop Plan - 2026-07-17

Status note - 2026-07-18: this is a historical planning note. Its boundary
principles remain useful, but the concrete "Recommended Next Step" has been
superseded. Jetson same-input CPU baseline evidence now exists under
`results/evidence/20260718_jetson_regular05_perf/`, the frozen baseline is
`lp_rigid_strength080_dynzoom106`, and same-input VPI backend swaps were
measured slower than `opencv_cpu` for the current 640x360 Python full pipeline.
Use `README.md`, `docs/harness_engineering_v1.md`, and the active Harness
contract as the current execution entry points.

## Purpose

This note fixes the current evaluation boundary and the recommended long-running
LLM loop for the Jetson Orin NX EIS project. It is not an algorithm progress
log. The goal is to keep future iterations from drifting into blind parameter
sweeps or unverified acceleration claims.

Update after local reread: the previously inaccessible loop-design material was
available through a private local internal-note summary. It is a curated summary
of Agent Loop / Loop Engineering articles, not a single original article. The
planning below incorporates its usable principles and keeps project-specific EIS
evidence as the source of truth. Do not copy private source paths or internal
text into public outputs.

## Current Project State

The project is not starting from zero. A useful harness already exists:

| Step | Existing tool | Role |
|---|---|---|
| Prepare clips | `scripts/prepare_nus_gate_set.py` | Build reproducible gate/challenge clips, manifest, metadata, contact sheet |
| Scene classification | `scripts/scene_gate_diagnostics.py` | Classify input clips before stabilization |
| Batch stabilization | `scripts/run_gate_matrix.py` | Run one config across a clip matrix |
| Batch evaluation | `scripts/evaluate_gate_matrix.py` | Compute SR/residual/smoothness/black-border gates |
| Human review assets | `scripts/make_gate_audit_assets.py` | Generate side-by-side videos, contact sheets, review CSV |
| Summary reports | `scripts/summarize_gate_report.py`, `scripts/summarize_scene_gate.py` | Convert CSV evidence to readable reports |

Mapped to the Loop Engineering split from the local notes:

| Layer | In this project | Boundary |
|---|---|---|
| Harness Runtime | Data paths, clip manifests, scene-gate scripts, run/eval scripts, audit assets, Git hygiene, evidence directories | Touches files, videos, Jetson, metrics, and reproducibility |
| Loop Engine | Plan/act/verify/reflect/retry/stop rules for each EIS iteration | Decides what may run next based on evidence |

This split matters: changing the loop strategy should not require rewriting the
clip/evaluation harness, and adding a new backend or metric should not silently
change the loop stop rules.

The main boundary decision is already supported by local evidence:

| Set | Current role | Evidence |
|---|---|---|
| NUS Regular gate v1 | Main quality gate / primary demo pool | Mostly normal candidate clips; current best visual evidence is `regular_gate05` |
| NUS Running gate v1 | Challenge / failure-boundary set | 4/5 `challenge_degrade`, 1/5 `global_model_risk`, 0/5 normal candidates |
| `ostrich_shaky.mp4` | Smoke test and external baseline sanity | Too small and narrow to prove final quality |
| 1080p ocean sample | Performance/no-regression only | Too smooth to prove stabilization quality |

Current measured acceptance boundary:

| Result | Meaning |
|---|---|
| Regular `scene_gate_weak` | 1/5 complete objective pass; `regular_gate05` passes objective gates |
| Running `lp_affine_trim010` | 0/5 complete objective pass; mainly smoothness and some stability failures |
| `regular_gate05 + crop90_lanczos_sharp025` | Best current stage evidence, but not a final quality solution |
| Running clips | Useful for explaining model limits, not for claiming full EIS success |

## What The References Add

The local reference notes are useful, but not all at the same priority.

High-value conclusions:

1. Test sets should be split into a core regression set and a badcase/boundary
   set. This maps directly to Regular as the main gate and Running as challenge.
2. Objective metrics are not ground truth. They must be tied to human visual
   review, otherwise proxy metrics can overrule obvious artifacts or reward the
   wrong thing.
3. EIS has unavoidable trade-offs: stability, crop/FOV, latency, image quality,
   and intent preservation cannot all be maximized at once.
4. Pure visual global-affine EIS has known weak zones: large running motion,
   weak texture, foreground/parallax, rolling-shutter-like row motion, and slow
   panning or intentional camera motion.
5. Long-running LLM work needs explicit separation and freeze rules. Each loop
   should change one primary variable and keep other dimensions fixed, similar
   to "explicit decoupling + explicit freezing + strength grading" in prompt
   engineering notes.
6. The local loop notes add a stronger engineering frame: a real Agent Loop is a
   state machine, not just tool calls. It needs explicit Observe/Think/Act/
   Feedback states, stop reasons, hard validators, recovery paths, and audit
   evidence.

## Loop Engineering Principles To Keep

The local `aime整理.md` note changes the planning emphasis in five concrete ways.

| Principle | Meaning for this EIS project |
|---|---|
| State machine first | Every long-running task should name its state: observe, plan, act, verify, reflect, retry, stop |
| Verifier strength controls autonomy | Hard signals such as metrics CSV, command exit code, frame counts, and Jetson timing allow more automation; visual quality remains human-reviewed |
| Stop is a first-class state | Stop because of success, hard gate failure, max attempts, stale plan, missing evidence, or human decision |
| Recover instead of looping blindly | On failure, switch strategy, reduce scope, or ask for internal AI/user evidence rather than repeating the same run |
| Auditability is required | Each loop leaves enough paths, commands, configs, metrics, and visual assets for the next agent to resume |

The production threshold for this project should therefore be:

```text
verifiable + terminable + recoverable + auditable
```

If a proposed loop cannot satisfy these four properties, it is a one-off
experiment, not the project loop.

Lower-priority or non-actionable content:

| Content type | Why not primary now |
|---|---|
| Generic IQA model lists | Useful background, but current project already has task-specific motion metrics |
| Heavy MLLM scoring | Not needed until there is enough human-reviewed EIS data to calibrate it |
| Full mobile camera OIS/IMU pipeline | Useful for explanation, but current project lacks gyro/OIS integration |
| Complex mesh/RS correction | Future upper-bound direction, not the next lowest-risk step |

## Test Set Boundary

### Main Gate

Use NUS Regular gate v1 as the current public, reproducible main gate.

Expected use:

- judge whether the current CPU EIS pipeline is demonstrably useful;
- compare same-input versions of smoothing, crop, warp, and quality settings;
- produce stage evidence for resume/interview explanation.

Do not use it to claim final product-grade EIS unless both objective and visual
review are clean across the selected clips.

### Challenge Gate

Use NUS Running gate v1 as a challenge/failure-boundary set.

Expected use:

- expose the limits of global 2D affine stabilization;
- verify scene-gate degradation behavior;
- explain why weak/off/mesh/RS/gyro-like alternatives are needed for high-risk
  scenes.

Do not treat Running pass rate as the main project success criterion for the
current pure-visual global-affine pipeline.

### Smoke And Performance Sets

Use `ostrich_shaky.mp4` for quick smoke tests and `vid.stab` comparison only.
Use the 1080p ocean sample for performance/no-regression only.

## Evaluation Method

The current evaluation should stay layered:

| Layer | Gate type | Current rule |
|---|---|---|
| Hard degradation | Crop and black border | Crop loss <= 15%; black-border p95/edge-connected failures are hard stops |
| Stability | SR/residual image-motion proxy | Main gate should improve residual motion, but interpret by scene role |
| Smoothness | `second_diff_top5_mean` | Non-regression is required for main evidence; challenge clips may remain diagnostic |
| Visual veto | Human side-by-side review | Frame jump, rollback, jello, local distortion, continuous black border, or unacceptable blur overrides metric pass |
| Performance | Same input, same config | Jetson numbers only; Windows numbers are not resume performance claims |

For quality claims, report at least:

```text
clip set + clip role
input path
algorithm config
SR/residual/smoothness/black-border/crop metrics
side-by-side evidence path
manual visual veto result
runtime platform and timing, if performance is discussed
```

## Expected Benefit Definition

Do not define success as "the output video exists".

Current realistic benefit targets:

| Benefit | Acceptable wording |
|---|---|
| Quality | "On selected Regular clips, the pipeline reduces residual motion while controlling crop and black border; best current visual evidence is regular_gate05." |
| Boundary awareness | "Running/high-risk clips are detected and degraded instead of forcing full affine EIS that creates jello or pullback." |
| Performance | "After Jetson same-input testing, report module latency and FPS. Until then, Windows timing is only development evidence." |
| Engineering value | "The project has a reproducible gate/harness that prevents blind tuning and separates main quality, challenge, and performance evidence." |

Claims to avoid:

- "Regular gate is solved" when only a subset passes.
- "Running is stabilized" when it is acting as challenge evidence.
- "VPI accelerated the full pipeline" without same-input end-to-end Jetson speedup.
- "The metric proves quality" without side-by-side human review.

## LLM Loop Design

Each iteration should be a controlled state-machine run, not open-ended
exploration.

### State Machine

Use this minimal state model for future EIS work:

| State | Required action | Exit condition |
|---|---|---|
| Observe | Read current context, relevant scripts, prior metrics, and evidence paths | Boundary is known or a blocking question is identified |
| Plan | Define objective, one allowed variable, frozen variables, validators, stop rules | Done Contract is written |
| Act | Run or edit only the scoped piece of work | Command/file change completes or fails |
| Verify | Run the relevant evaluator and inspect required visual evidence | Hard pass/fail evidence exists |
| Reflect | Explain why results changed, what costs were introduced, and whether the loop may continue | Continue, retry with changed strategy, or stop |
| Stop | Record outcome and next action | Evidence and summary are sufficient for resume |

This is not meant to become heavy infrastructure. It is a checklist for every
manual or AI-driven iteration.

### Loop Input Contract

Every loop starts with a Done Contract:

```text
current objective:
clip set and roles:
baseline config:
one variable allowed to change:
frozen variables:
hard validators:
soft validators:
max attempts:
stop reasons:
recovery path:
evidence output directory:
```

Example:

```text
current objective: Jetson same-input performance verification
clip set and roles: regular_gate05 as main evidence clip
baseline config: crop90_lanczos_sharp025, lp_affine, scene_gate_policy=weak
one variable allowed to change: runtime platform only
frozen variables: input clip, algorithm parameters, output resolution, quality gates
hard validators: output exists, summary CSV exists, avg_estimate_ms/avg_warp_ms/total_wall_time_s recorded on Jetson
soft validators: side-by-side video has no obvious visual regression vs Windows stage evidence
max attempts: 2 runs before changing strategy
stop reasons: success, SSH/device blocker, output mismatch, missing metric fields, hard visual regression
recovery path: preserve logs, summarize blocker, then either fix SSH/runtime or fall back to Windows-only planning
evidence output directory: results/evidence/<date>_jetson_regular05_perf/
```

### Allowed Loop Types

| Loop type | Allowed change | Required evidence |
|---|---|---|
| Quality loop | One algorithm/config variable | Metrics CSV, side-by-side video, visual veto |
| Scene-gate loop | Scene thresholds or policy only | Scene CSV, class counts, before/after audit clips |
| Performance loop | Backend/platform/dataflow only | Same-input timing, module breakdown, quality no-regression |
| Documentation loop | Wording and evidence packaging only | No new measured claims unless linked to existing artifacts |

Recommended strategy by verifier strength:

| Situation | Loop mode |
|---|---|
| Hard command/test/eval signal exists | ReAct-style short loop is enough |
| Multi-step but deterministic task, such as Jetson perf reproduction | Plan-and-Execute |
| Quality tuning with metrics plus visual review | Reflexion-style: attempt, evaluate, reflect, retry once with changed strategy |
| Conflicting algorithm directions or unclear references | Use internal AI or human input before implementing |
| Need independent viewpoints | Use subagent-style isolation only when explicitly requested; its value is protecting root context, not adding more opinions |

### Freeze Rules

When one dimension is being tested, freeze the others:

| Testing dimension | Must freeze |
|---|---|
| Smoothing quality | Input clips, crop ratio, interpolation, sharpen, estimate scale, scene roles |
| Crop/FOV | Smoothing method, LP weights, scene roles, input clips |
| Scene gate | Stabilization config and quality metrics |
| Warp/backend speed | Input, transforms, crop/interpolation, output format, quality evaluation |
| Visual packaging | Algorithm output and metrics |

### Stop Rules

Stop a loop and summarize instead of continuing when any of these occur:

- Two consecutive changes improve one metric but worsen visual veto or hard gates.
- The same failing action has been retried once without a new hypothesis.
- A change only helps Running while hurting Regular main evidence.
- A performance change changes output semantics, so it is no longer same-input
  acceleration.
- The next step requires gyro/IMU/mesh/RS support that is outside the current
  controllable pipeline.
- The LLM cannot explain why a change helped or what it costs.
- Required evidence is missing: no command, no config, no metrics path, no visual
  path, or no platform label.

### Recovery Rules

Failure is part of the loop. Use a different recovery path depending on the
failure type:

| Failure | Recovery |
|---|---|
| Command/runtime failure | Save exact error, inspect environment minimally, retry once after a concrete fix |
| Metric regression | Keep outputs, compare against frozen baseline, change hypothesis before rerun |
| Visual veto | Do not argue from metrics; mark clip/config as failed or diagnostic |
| Device/SSH blocker | Stop the EIS loop, run the USB SSH recovery SOP, then resume |
| Reference ambiguity | Ask for internal AI/user evidence with a focused prompt |
| Repeated soft-metric ambiguity | Convert the question into a human audit CSV before more tuning |

## Recommended Next Step

The next best action is not another LP parameter sweep.

Run Jetson same-input performance verification for the current stage evidence:

```text
input: results/nus_regular_gate_v1/raw_clips/regular_gate05_regular_6.mp4
config: crop90 + lanczos + sharpen_strength=0.25 + lp_affine + scene_gate weak
record: avg_estimate_ms, avg_warp_ms, total_wall_time_s, FPS
compare: Windows timing is development-only; Jetson timing is resume evidence
output: one metrics CSV, one summary CSV, one side-by-side video copied to C:\Users\Admin\Videos\orin nx
```

After that, decide whether to optimize the high-quality crop/remap path using
OpenCV CPU vs VPI/CUDA remap on the same input. Do not start mesh/RS work until
the Jetson same-input performance boundary is recorded.

### Concrete Next Loop Contract

```text
state: Plan-and-Execute performance loop
objective: produce Jetson same-input runtime evidence for the current Regular stage clip
clip: results/nus_regular_gate_v1/raw_clips/regular_gate05_regular_6.mp4
config: current crop90_lanczos_sharp025 lp_affine scene-gate-weak config
frozen: input, output resolution, crop ratio, interpolation, sharpen, LP weights, scene-gate policy
hard validators:
  - stabilized mp4 exists
  - metrics CSV exists
  - summary CSV contains avg_estimate_ms, avg_warp_ms, total_wall_time_s
  - side-by-side review clip exists under results/evidence and C:\Users\Admin\Videos\orin nx
soft validators:
  - no obvious black border, frame jump, rollback, or unacceptable blur in side-by-side review
max attempts: 2
stop on:
  - successful evidence package
  - Jetson SSH/runtime blocker
  - missing metric fields after one fix attempt
  - output semantics differ from Windows baseline
recovery:
  - for SSH blocker, run USB SSH recovery SOP before returning to EIS
  - for runtime dependency blocker, inspect existing Jetson env first and avoid broad rebuilds
```

## Open Items

1. The local loop note is a curated summary. If exact implementation details are
   needed, read the linked original internal articles through user-side access.
2. Regular gate needs a small human review CSV that marks each clip as main,
   backup, diagnostic, or vetoed.
3. The long-term AI context should eventually link to this note if the user wants
   the project memory updated.
