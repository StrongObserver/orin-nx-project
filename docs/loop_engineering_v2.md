# Orin NX EIS Loop Engineering V2 - 2026-07-17

## Purpose

This document upgrades the Orin NX EIS project from Harness V1 to a clearer Loop
Engineering V2. It does not replace the existing harness. It explains how future
agents should decide what to do next, when to stop, when to recover, and when to
call the external knowledge base.

The decision is:

```text
Keep Harness V1 as the runtime and evidence control plane.
Add Loop Engineering V2 as the decision layer above it.
```

## Source Review

The updated oral-template source pointed to:

```text
C:\Users\Admin\Nutstore\1\Typora_save\AI & Agent学习\loop engeering.md
```

That file is a link index. I read the local index first, then resolved and read
the most relevant linked documents that were locally accessible. Some web
article URLs required authenticated access in a plain browser request, so I used
the available document search and fetch path for accessible copies instead.

High-value documents read:

| Topic | Useful conclusion |
|---|---|
| Loop Engineering system guide | Loop is a system above Prompt/Context/Harness; it needs automation, worktree, skill, connector, sub-agent, state, and verification |
| Prompt to verifiable Agent loop | Loop must be verifiable, terminable, recoverable, and auditable; verifier strength controls autonomy |
| Cybernetics / SpecCoding / Loop | Spec is feedforward; Loop is feedback; use both instead of choosing one |
| RL view of Agent loops | Goal + Workflow + External Observation; feedback must come from outside the agent |
| Loop essence/practice notes | Long tasks need state, next-step rationale, failed attempts, and exit conditions; "running long" is not success |
| Maze app practice | `tasks.md` + `verify.md` + goal hook is enough for a small loop; the hardest part is defining verification |
| Outbound Agent self-evolution | Evaluation is the loss; maker/checker must be separate; candidates must beat baseline before promotion |
| Agent Loop / Harness basics | Think/Act/Observe is the inner loop; Loop Engineering is the outer loop that controls goals, state, verification, and risk |

Lower-value or conditional material:

| Content | Why not primary for this project |
|---|---|
| Full factory automation / event-driven production lines | Current project is a local resume project with one user and hardware-in-the-loop constraints |
| Worktree-heavy multi-agent systems | Useful later, but current verifier/review bandwidth and hardware access are the real bottlenecks |
| Hill-climbing / self-improving Agent systems | Too heavy until the project has enough calibrated EIS evidence and stable evals |
| MLLM / judge-based quality scoring | Not needed until human-reviewed side-by-side samples are large enough to calibrate it |

## Core Judgment

Do not rebuild the current framework from scratch.

The existing project already has the correct harness shape:

- gate roles in `configs/harness/gates.json`;
- a Done Contract in `configs/harness/contracts/jetson_regular05_perf.json`;
- evidence package creation and validation in `scripts/harness_runner.py`;
- manual visual veto;
- public Regular main gate and Running challenge gate separation;
- knowledge-base recovery routing in `docs/knowledge_base/`.

What is missing is a stronger **Loop Engine** above that runtime:

- loop type selection;
- autonomy level;
- external observation definition;
- stop and recovery state;
- state/update policy;
- escalation to knowledge base or human only when needed.

## Anti-Retreat Rule

This loop system must not turn a stable checkpoint into the final project goal.

Stable baselines exist for version control, comparison, rollback, and honest
before/after claims. They do not lower the original project target. A negative
result is also evidence, but it is not permission to retreat into documentation
or presentation work while core engineering tracks remain unfinished.

Use this rule after every failed or negative performance result:

| Observation | Correct interpretation | Required next action |
|---|---|---|
| VPI backend swap is slower | The chosen placement/dataflow is bad, not VPI as a whole | Classify conversion/sync/readback cost, then test backend support or module scope |
| Python appsink/appsrc is expensive | Python round trip is bad, not NVMM/NVDEC/NVENC as a whole | Route to non-Python NVMM/CUDA/C++ dataflow contract |
| Challenge clips fail | Current global-warp model is limited, not the whole project failed | Keep Regular as main gate and open mesh/grid/scene-degrade as future model route |
| CPU baseline is stable | A checkpoint exists, not the project is finished | Preserve it with Git/evidence, then continue the active core track |

Forbidden behavior:

- downgrade the project goal without user approval;
- replace unfinished core work with documentation packaging;
- keep polishing the same stable CPU baseline after its gate is already closed;
- treat "do not overclaim" as "do not continue exploring".

The active unfinished core tracks are:

1. VPI backend validation and heterogeneous acceleration;
2. algorithm cost reduction, zero-copy or non-Python pipeline exploration;
3. hardware decode/encode plus power and perf/watt evaluation.

## Layer Split

| Layer | Current project owner | Job |
|---|---|---|
| Harness Runtime | `scripts/`, `configs/harness/`, `results/` | Run commands, check gates, create/validate evidence, preserve review assets |
| Loop Engine | this document + loop profiles | Decide allowed loop type, variable freeze, verifier strength, stop/recovery path |
| Knowledge Recovery | `docs/knowledge_base/` + `.local_knowledge/` | Provide outside references only when a loop is stuck or enters a new domain |
| Human Gate | user/manual review | Decide subjective visual veto, scope forks, hardware steps, and high-risk actions |

This split matters: a better loop should not rewrite the harness; a new metric
or backend should not silently change loop stop rules.

## Design Principles

### 1. Spec + Loop, Not Spec Or Loop

Use the control-theory framing:

```text
Spec / Done Contract = feedforward
Harness evidence = external measurement
Loop reflection/recovery = feedback
```

For this project, the Done Contract should push each loop close to the right
target before any action starts. The loop should then use real measurements to
decide whether to stop, retry once with a new hypothesis, or recover.

### 2. External Observation Is Mandatory

Agent self-report is not evidence.

Valid external observations include:

- command exit codes;
- metrics CSV and summary CSV;
- manifest/scene-gate CSV;
- side-by-side videos;
- human review CSV;
- Jetson platform label and timing;
- copied review asset under `C:\Users\Admin\Videos\orin nx`.

If a loop cannot name its external observation, it is not allowed to become an
autonomous loop.

### 3. Verifier Strength Controls Autonomy

| Verifier strength | Examples | Allowed autonomy |
|---|---|---|
| Strong deterministic | command exit code, file existence, JSON schema, CSV fields | Agent can run within contract |
| Medium proxy | SR/residual/smoothness/black-border metrics | Agent can attempt once, then inspect visual evidence |
| Weak subjective | blur, jello, local pull, panning intent, "looks good" | Human review or explicit visual evidence required |
| Missing | no metric, no evidence path, no platform label | Stop and define verifier first |

### 4. Stop Is A First-Class State

A good loop stops for more than success. It must also stop for:

- hard gate failure;
- visual veto;
- missing evidence;
- stale or repeated plan;
- unsafe scope expansion;
- device/SSH/runtime blocker;
- need for gyro, mesh, rolling-shutter, or product-level decision outside the current pipeline.

### 5. Recovery Is Not Retry

Retry means repeating the same action. Recovery means changing the loop state:

- reduce scope;
- switch loop type;
- read a matched knowledge-base source;
- ask for internal AI/user evidence;
- mark the sample as diagnostic/model-boundary;
- create a new Done Contract.

## Loop State Machine

Use this state machine for every non-trivial EIS task:

| State | Required action | Exit condition |
|---|---|---|
| Observe | Read current prompt, AGENTS, active context, gate roles, prior evidence | Task boundary known or blocker identified |
| Frame | Choose loop type and autonomy level; name external observation | Loop profile selected |
| Plan | Define objective, one allowed variable, frozen variables, validators, max attempts, stop/recovery path | Done Contract or loop checklist ready |
| Act | Run/edit only the scoped action | Action completes or fails |
| Verify | Run the verifier and collect evidence paths | Hard pass/fail/unknown exists |
| Reflect | Explain why result changed, what it cost, and whether evidence supports continuing | Continue once, recover, or stop |
| Recover | Use knowledge base, reduce scope, or ask human with exact blocker | New plan exists or task stops |
| Stop | Record outcome, evidence, and next action | No required work remains for this loop |

The current inner Agent Loop can still be Think/Act/Observe. V2 is the outer
project loop that controls whether the inner loop is allowed to continue.

## Autonomy Levels

| Level | Name | What the agent may do | Current project use |
|---|---|---|---|
| L0 | Manual only | Read and propose; no edits/runs | Strategic decisions and scope forks |
| L1 | Read-only triage | Inspect files, metrics, docs, and evidence | Reference reading, status alignment |
| L2 | Assisted single-action | Make a scoped edit or run a scoped command, then verify | Most local project edits |
| L3 | Contracted loop | Execute up to max attempts inside a Done Contract | Jetson same-input perf and narrow quality loops |
| L4 | Semi-autonomous pipeline | Scheduled/event loops, worktrees, maker/checker automation | Not recommended yet for this project |

Current recommendation: keep Orin NX EIS at **L2/L3**. Do not build L4
automation until Jetson performance evidence, manual review labels, and stable
quality gates are stronger.

## Loop Profiles

The machine-readable profile list lives at:

```text
configs/harness/loop_profiles.json
```

Human-readable summary:

| Loop type | Allowed change | Required observation | Max attempts | Knowledge trigger |
|---|---|---|---|---|
| `performance_loop` | platform/backend/dataflow only | same-input timing + quality no-regression | 2 | VPI/GStreamer/NVMM ambiguity |
| `quality_loop` | one algorithm/config variable | metrics CSV + side-by-side + manual veto | 2 | visual veto or metric/visual conflict |
| `scene_gate_loop` | scene thresholds or policy only | scene CSV + class counts + audit assets | 2 | Regular/Running role confusion |
| `evaluation_loop` | dataset/metric/report/audit schema only | dataset registry + metric schema + human-review compatibility | 1 | metric contradicts visual review |
| `knowledge_recovery_loop` | no code/algorithm change | source notes + one concrete recovery idea | 1 | repeated failed action or new domain |
| `documentation_loop` | wording and routing only | no invented metrics; links to existing evidence | 1 | stale context or misleading claim |
| `device_recovery_loop` | USB/SSH/runtime recovery only | connectivity or runtime proof | 1 | Jetson unreachable or env blocker |

## Done Contract V2 Fields

Existing contracts remain valid. New contracts should add these optional fields
when relevant:

```json
{
  "loop_profile": "performance_loop",
  "autonomy_level": "L3",
  "external_observation": [
    "summary_csv_has_avg_estimate_ms",
    "summary_csv_has_avg_warp_ms",
    "comparison_mp4_exists",
    "review_copy_exists"
  ],
  "knowledge_base_refs": [
    "public:nvidia_vpi_samples"
  ],
  "state_update_policy": "record outcome and next action only; no running log",
  "human_gate": [
    "manual visual veto",
    "device-side command if SSH is blocked"
  ]
}
```

## How To Use The Knowledge Base

The knowledge base is not part of every loop preflight. Use it like this:

1. Stop or recover state is reached.
2. Define blocker in one sentence.
3. Open `docs/knowledge_base/routing.md`.
4. Read at most two matched source cards or internal summaries.
5. Extract one concrete idea, one risk, and one verifier.
6. Return to a loop profile or Done Contract.

If more than two sources seem necessary, the task is not scoped tightly enough.

## Progressive Disclosure Startup

Startup itself is now part of the loop design. Future agents should avoid a
large default context load and follow this order:

```text
1. Read the oral template from the first line, including its rules.
2. Read configs/harness/onboarding_manifest.json, or run:
   py -3.12 scripts\harness_runner.py onboard
3. Read configs/harness/contracts/orin_next_engineering_loop_v1.json.
4. Read the current task contract, currently:
   configs/harness/contracts/regular05_live_eglimage_path_v1.json.
5. Open long-term context sections or reference folders only when a manifest
   trigger, contract stop/recovery rule, or real blocker requires them.
```

The largest avoidable token costs are:

- full-reading the long-term context when only the latest milestone sections are
  needed;
- broad-scanning internal camera-reference folders at startup;
- reading multiple presentation/evidence documents that repeat the same
  boundary;
- enumerating all `results/` folders instead of following the active contract.

This rule must not weaken recovery. If a blocker appears, the agent should still
use `docs/knowledge_base/routing.md`, the local internal index, or public search
as directed by the current contract.

## Project-Specific Stop Rules

Stop instead of continuing when:

- the latest user prompt or human visual review contradicts the active contract
  state;
- a second attempt improves one metric but worsens hard gates or visual review;
- the same failed action has already been retried once without a new hypothesis;
- Running improves while Regular gets worse;
- a performance change changes output semantics;
- the next fix requires gyro/IMU/mesh/rolling-shutter support;
- no side-by-side review asset exists for a quality claim;
- performance evidence lacks `platform_label=jetson`;
- the agent cannot explain why a change helped and what it costs.

## Project-Specific Recovery Rules

| Failure | Recovery |
|---|---|
| Latest user review rejects a candidate that a contract still marks pending | Treat the user review as the newest external observation; update active contract, onboarding manifest, and summaries before any new experiment |
| Command/runtime failure | Preserve exact error, inspect minimally, retry once after a concrete fix |
| Metric regression | Compare against frozen baseline; change hypothesis before rerun |
| Visual veto | Mark run failed/diagnostic; do not argue from metrics |
| Running failure | Treat as challenge/model-boundary unless Regular evidence demands otherwise |
| Backend swap slower than baseline | Do not stop the acceleration track; classify overhead and move to backend-support, module-level, or dataflow contract |
| Python dataflow path too costly | Do not stop NVMM/GStreamer work; route away from Python loop toward C++/CUDA/device-side pipeline |
| Stable baseline accepted | Commit/preserve if appropriate, then continue the next unfinished core track |
| Weak texture/foreground/parallax | Use knowledge routing before changing algorithm |
| Device/SSH blocker | Stop EIS loop; run USB SSH recovery path; resume only after connectivity proof |
| Evaluation ambiguity | Create/extend human review CSV before more tuning |
| Scope fork | Ask user with exact decision and recommended default |

## Why Not A Full Rebuild

A full rebuild would add overhead without solving the current bottleneck.

Current completed boundary:

```text
Jetson same-input CPU baseline evidence exists for regular_gate05_regular_6.
```

The current frozen stage baseline is:

```text
clip: results/nus_regular_gate_v1/raw_clips/regular_gate05_regular_6.mp4
config: lp_rigid + stabilization_strength=0.80 + crop90 + lanczos + sharpen0.25 + dynzoom1.06
platform_label: jetson
evidence: results/evidence/20260718_jetson_regular05_perf/
```

Same-input backend replacement has also been checked: `vpi_cpu`, `vpi_cuda`, and
`vpi_vic` are slower than `opencv_cpu` in the current 640x360 Python
full-pipeline path. Do not start another LP parameter sweep or claim VPI
full-pipeline acceleration from that result. The next performance loop should
change one variable such as motion-estimation scale/feature budget, or move to a
separate high-resolution VPI module or GStreamer/NVMM dataflow contract.

## What V2 Changes Immediately

1. Every substantial task must choose a loop profile.
2. Every loop must name its external observation.
3. Every scoped loop has max attempts and stop/recovery rules.
4. Knowledge base use is a recovery action, not default context.
5. Human visual review remains the authority for jello, local pull, rollback,
   blur, and subjective display decisions.
6. Negative results must produce a next exploration route while core tracks are
   unfinished.
7. Documentation loops may record a checkpoint, but they cannot replace
   unfinished VPI, dataflow, decode/encode, or power-evaluation work.

## What V2 Defers

- Scheduled automation.
- Multi-worktree parallel agents.
- Automatic PR creation.
- MLLM visual scoring as a gate.
- Self-improving prompt or harness mutation.
- Mesh/RS/gyro algorithm expansion.

These are valid future directions, but only after the current evidence loop is
stronger.
