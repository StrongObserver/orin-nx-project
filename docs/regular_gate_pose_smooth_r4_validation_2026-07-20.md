# Regular Gate Pose Smooth R4 Validation - 2026-07-20

## Problem

Human review of the five-clip viewport-stable outputs found a new artifact:

```text
No zooming.
No brief narrow black edge.
But the image pose is not smooth: translation/rotation can jump to a nearby
camera pose abruptly.
```

This is a different failure mode from the earlier zooming and border problem.

## Root Cause

The fixed-scale/crop98 route solved scale variation, but it did not smooth the
matrix translation and rotation components. Matrix diagnostics show large
`tx/ty/angle` deltas remain after the fixed-scale step.

Examples:

```text
regular_gate01 fixed-scale: trans_delta_p95=8.8936 px, max=26.5559 px
regular_gate03 fixed-scale: trans_delta_p95=6.3385 px, max=19.6941 px
regular_gate05 fixed-scale: trans_delta_p95=12.2635 px, max=16.2605 px
```

The largest jumps often occur near stride/prefix update boundaries, which is
consistent with `lp_prefix_stride=5` reusing LP prefix solutions between solve
points. The viewport is stable, but the pose path is still piecewise and can
look like a sudden camera attitude switch.

## Candidate

The focused candidate keeps the previously accepted viewport rule and adds pose
smoothing:

```text
input: stride5 fixed-scale safe103 matrices
scale: fixed, unchanged
tx/ty smoothing radius: 4
angle smoothing radius: 4
first frame: copy next matrix
postprocess: crop98
consumer: accepted EGLImage FIFO path
```

This is called `pose_smooth_r4`.

## Matrix Improvement

| Clip | Before trans p95 | R4 trans p95 | Before trans max | R4 trans max | Before angle p95 | R4 angle p95 |
|---|---:|---:|---:|---:|---:|---:|
| regular_gate01 | 8.893594 | 4.945992 | 26.555884 | 6.389901 | 0.006442 | 0.003848 |
| regular_gate02 | 4.192783 | 3.166811 | 10.544636 | 4.330179 | 0.004052 | 0.002891 |
| regular_gate03 | 6.338537 | 4.689318 | 19.694116 | 6.789499 | 0.004777 | 0.002933 |
| regular_gate04 | 6.501285 | 2.714630 | 9.065482 | 3.023167 | 0.004082 | 0.002156 |
| regular_gate05 | 12.263541 | 7.243054 | 16.260519 | 8.054621 | 0.010880 | 0.005548 |

## Device Results

The R4 matrices were run through the accepted EGLImage FIFO consumer on all five
Regular clips.

```text
5/5 rc=0
5/5 fallback_count=0
5/5 frame_index_mismatch_count=0
```

Black-border results after crop98:

| Clip | black p95 | frames > 1% | Decision |
|---|---:|---:|---|
| regular_gate01 | 0.027832031 | 35 | Conditional, visual review required |
| regular_gate02 | 0.000278212 | 0 | Pass |
| regular_gate03 | 0.000404080 | 0 | Pass |
| regular_gate04 | 0.002921007 | 0 | Pass |
| regular_gate05 | 0.000000000 | 0 | Pass |

Regular01 remains conditional for the same reason as the previous viewport
candidate: gray-threshold black-border flags dark regions, while geometry
coverage remains safe. Do not call this 5/5 pass until human review confirms
Regular01.

## Evidence

Local evidence:

```text
results/regular_gate_stride5_viewport_stable_validation_20260720/
```

Summary CSV:

```text
results/regular_gate_stride5_viewport_stable_validation_20260720/pose_smooth_r4_summary.csv
```

Review directory:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_stride5_pose_smooth_r4_validation\
```

Main review file:

```text
20260720_regular_gate_stride5_pose_smooth_r4_validation_5clip_review_grid.mp4
```

Per-clip review files:

```text
20260720_regular_gate_stride5_pose_smooth_r4_validation_regular_gate01_regular_10_jetson_source_safe103crop98_pose_r4_grid.mp4
20260720_regular_gate_stride5_pose_smooth_r4_validation_regular_gate02_regular_19_jetson_source_safe103crop98_pose_r4_grid.mp4
20260720_regular_gate_stride5_pose_smooth_r4_validation_regular_gate03_regular_13_jetson_source_safe103crop98_pose_r4_grid.mp4
20260720_regular_gate_stride5_pose_smooth_r4_validation_regular_gate04_regular_8_jetson_source_safe103crop98_pose_r4_grid.mp4
20260720_regular_gate_stride5_pose_smooth_r4_validation_regular_gate05_regular_6_jetson_source_safe103crop98_pose_r4_grid.mp4
```

Panel order:

```text
source / safe103crop98 / pose_r4_crop98
```

## Claim Boundary

Allowed:

```text
R4 reduces the translation and angle jumps caused by the previous fixed-scale
stride5 path while keeping the accepted EGLImage FIFO consumer healthy.
It is diagnostic evidence for the pose-jump root cause.
```

Forbidden:

```text
Do not claim full Regular 5/5 pass until Regular01 is visually accepted.
Do not claim all-scene EIS quality.
Do not claim zero-latency real-time EIS.
```

## Next Step

Human review result:

```text
R4 reduces pose jumps, but the user judged the stabilization effect too weak.
R4 is rejected as an active candidate and kept only as diagnostic evidence.
```

Next route:

```text
Do not freeze R4.
Do not keep trying neighboring R values as the main route.
Use first-principles root-cause analysis and local/public/internal EIS references
to choose a camera-path planning fix that preserves stabilization while removing
abrupt translation/rotation pose jumps.
```
