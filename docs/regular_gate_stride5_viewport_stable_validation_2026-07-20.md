# Regular Gate Stride5 Viewport-Stable Validation - 2026-07-20

## Decision

The Regular05 `safe103_crop98` viewport-stable fix was extended to all five NUS
Regular gate clips under a new contract and without manual per-clip tuning.

The device path is healthy on all five clips:

```text
rc=0
fallback_count=0
frame_index_mismatch_count=0
```

The black-border result is not a clean 5/5 objective pass yet. Four clips pass
the gray-threshold black-border hard gate. Regular01 is conditional: geometry
coverage is safe, but the gray-threshold black-border metric flags many frames.
This needs human review because Regular01 has known dark-edge false-positive
risk in earlier inclusion validation.

## Frozen Rule

```text
producer: bounded_delay_lp_rigid
producer_delay_frames: 90
lp_prefix_stride: 5
matrix convention: source_to_dest
viewport: fixed absolute scale from same automatic rule
first frame: copy next matrix, not identity
postprocess: crop98
consumer: accepted C++ EGLImage FIFO path
```

The fixed-scale rule was adjusted after local precheck showed that `median scale
* 1.03` was not enough for Regular02. The accepted rule is:

```text
absolute_scale = max_original_matrix_scale * required_extra_scale_max * 1.03
```

This keeps the rule automatic and evidence-derived. It is not manual per-clip
tuning, but it does allow each clip to compute its own safety scale from its own
matrix sequence.

## Summary

| Clip | rc | fallback | mismatch | gray black p95 | gray frames > 1% | geometry p95 invalid | Decision |
|---|---:|---:|---:|---:|---:|---:|---|
| regular_gate01_regular_10 | 0 | 0 | 0 | 0.026323350 | 36 | 0.000003906 | Conditional, needs visual review |
| regular_gate02_regular_19 | 0 | 0 | 0 | 0.000291016 | 0 | 0.001227430 | Pass |
| regular_gate03_regular_13 | 0 | 0 | 0 | 0.000364800 | 0 | 0.000000000 | Pass |
| regular_gate04_regular_8 | 0 | 0 | 0 | 0.002923394 | 0 | 0.002360460 | Pass |
| regular_gate05_regular_6 | 0 | 0 | 0 | 0.000000000 | 0 | 0.000091363 | Pass |

Notes:

```text
Regular01 has a gray-threshold failure but geometry coverage is safe.
Treat it as conditional rather than objective pass until human review confirms
whether this is the known dark-edge false positive or a real border artifact.
```

## Evidence

Local evidence:

```text
results/regular_gate_stride5_viewport_stable_validation_20260720/
```

Summary CSV:

```text
results/regular_gate_stride5_viewport_stable_validation_20260720/regular_gate_stride5_viewport_summary.csv
```

Review copies:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_stride5_viewport_stable_validation\
```

Main review files:

```text
20260720_regular_gate_stride5_viewport_stable_validation_5clip_review_grid.mp4
20260720_regular_gate_stride5_viewport_stable_validation_regular_gate01_regular_10_jetson_source_safe103_safe103crop98_grid.mp4
20260720_regular_gate_stride5_viewport_stable_validation_regular_gate02_regular_19_jetson_source_safe103_safe103crop98_grid.mp4
20260720_regular_gate_stride5_viewport_stable_validation_regular_gate03_regular_13_jetson_source_safe103_safe103crop98_grid.mp4
20260720_regular_gate_stride5_viewport_stable_validation_regular_gate04_regular_8_jetson_source_safe103_safe103crop98_grid.mp4
20260720_regular_gate_stride5_viewport_stable_validation_regular_gate05_regular_6_jetson_source_safe103_safe103crop98_grid.mp4
```

Panel order for each clip:

```text
source / safe103 / safe103_crop98
```

## Claim Boundary

Allowed:

```text
The stride5 viewport-stable strategy runs through the accepted EGLImage FIFO
consumer on all five Regular clips with rc=0, fallback=0, and mismatch=0.
Four clips pass the gray-threshold black-border hard gate.
Regular01 is conditional pending human visual review.
```

Forbidden:

```text
Do not claim full 5/5 Regular pass until Regular01 is visually accepted.
Do not claim all-scene EIS quality.
Do not claim zero-latency real-time EIS.
Do not call this VPI optical-flow acceleration.
```

## Next Step

Human review should focus on:

```text
1. Regular01: is the gray-threshold black-border failure a real border artifact,
   or the same dark-edge false positive seen in earlier Regular inclusion review?
2. All clips: is the fixed-scale/crop98 field-of-view loss acceptable?
3. All clips: is zooming gone compared with the previous live_stride5/delay90
   outputs?
```

If Regular01 is visually accepted, this route can be frozen as the Regular gate
viewport-stable candidate. If Regular01 shows real border or the FOV loss is too
large, stop local patching and route to viewport-planning / FOV-safe crop
knowledge recovery.
