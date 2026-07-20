# Regular Gate Pose-Jump Root-Cause Recovery - 2026-07-20

## Human Review Trigger

The user reviewed `lim8` and rejected it:

```text
lim8 still has abrupt translation/rotation pose jumps.
Do not continue local limiter tuning before first-principles root-cause analysis
and external/reference search.
```

Therefore `pose_smooth_r4` and `pose_delta_limiter_lim8` are diagnostic only.

## First-Principles Root Cause

The accepted C++ EGLImage FIFO consumer is healthy for these runs:

```text
rc = 0
fallback = 0
frame-index mismatch = 0
```

So the remaining artifact is not a device handoff failure. It is a camera-path
quality failure: the final per-frame matrices still contain abrupt translation
and rotation steps after scale has been fixed.

The failed local fixes show the real boundary:

```text
R4 moving average: reduces pose jumps, but weakens stabilization too much.
lim8 hard delta limiter: caps max tx/ty/angle step, but visible jumps remain.
```

That means post-processing final matrices is the wrong abstraction. The next
solution must solve a temporally continuous camera path with intent, derivative,
confidence, and FOV/crop constraints in one model.

## Reference Search

Local knowledge routing pointed to:

```text
internal:eis_algorithm_topic
internal:eis_cis_solution
internal:orb_eis_application
```

The useful project-level takeaways were:

```text
Do not optimize stability alone.
Treat smoothness / frameshift / FOV / local deformation as separate gates.
Panning or intent preservation should be handled in the path planning stage, not
as a final affine-matrix patch.
Confidence and scene routing matter when visual motion estimation is unreliable.
```

Public/open-source search checked:

```text
public:l1_optimal_camera_paths
public:opencv_videostab
public:meshflow
public:bundled_camera_paths
```

Two public implementations were cloned only under ignored local evidence:

```text
results/external_refs_20260720/L1-optimal-paths-Stabilization/
results/external_refs_20260720/meshflow/
```

L1 optimal camera paths directly matches the current global-camera-path issue:
it optimizes first, second, and third derivatives under crop/FOV constraints.
MeshFlow is relevant when the single global transform is insufficient, but it is
a larger model change and should not be the immediate small fix unless the
global path route is exhausted.

## Local Matrix Probes

Two scoped code probes were added with default-off behavior:

```text
scripts/live_matrix_producer.py --published-prefix-weight <w>
scripts/live_matrix_producer.py --intent-reference-weight <w>
```

They are matrix-level probes only; no new Jetson review video was promoted.

### Probe 1: Published-Prefix Continuity

Hard locking already emitted prefix matrices was infeasible on Regular01/02.
Soft locking with weight 100 was feasible but did not solve Regular05:

```text
Regular05 safe103crop98 trans_delta_p95: 12.263541
Regular05 lockw100 trans_delta_p95:     12.188008
```

Conclusion: prefix re-solving may contribute, but it is not the root fix by
itself.

### Probe 2: Intent Reference Inside LP

Adding a low-pass intent-reference soft cost inside LP improved Regular05 but
remained insufficient:

```text
Regular05 safe103crop98 trans_delta_p95: 12.263541
Regular05 intentw20 trans_delta_p95:     11.340817
Regular05 intentw100 trans_delta_p95:    10.762828
Regular05 lim8 trans_delta_p95:          8.000000
Regular05 R4 trans_delta_p95:            7.243054
```

This confirms the right direction is path-level optimization, but the naive
reference term is not enough. Increasing weight blindly risks turning into
another R4-like over-smoothing or causing FOV pressure.

## Current Decision

Do not generate another local limiter, neighboring R radius, or blind LP weight
sweep.

The next recovery needs industrial or mature-reference guidance on the exact LP
formulation for:

```text
intent preservation / panning
first/second/third derivative continuity
bounded-delay online output
FOV/crop constraints
motion-estimation confidence
stabilization strength retention
```

If internal guidance returns a concrete minimal route, create a new scoped
quality-loop contract before producing another Jetson review video.

