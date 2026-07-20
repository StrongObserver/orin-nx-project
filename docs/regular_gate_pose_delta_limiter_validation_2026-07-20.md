# Regular Gate Pose Delta Limiter Validation - 2026-07-20

## Problem

`pose_smooth_r4` reduced the abrupt translation/rotation pose jumps, but human
review found that it also weakened the stabilization effect too much. The root
cause is that R4 applies whole-sequence moving average smoothing to `tx/ty/angle`,
so it removes both unwanted pose steps and useful stabilization corrections.

## Human Review Update

The user reviewed `lim8` and rejected it:

```text
lim8 still has abrupt pose jumps.
Do not continue the same local limiter route before root-cause analysis and
external/reference search.
```

This report is therefore diagnostic evidence, not an active candidate report.

## Diagnostic Candidate

The next candidate is a local delta limiter:

```text
scale: fixed, unchanged
crop: crop98
max translation step: 8 px/frame
max angle step: 0.008 rad/frame
consumer: accepted EGLImage FIFO path
```

This is called `lim8`. Unlike R4, it does not average the entire pose sequence.
It only clamps frame-to-frame pose steps that exceed the threshold. Human review
showed that this does not solve the visible failure.

## Matrix Trade-Off

Compared with the original fixed-scale safe103 path and R4:

| Clip | safe trans p95 | R4 trans p95 | lim8 trans p95 | safe max | R4 max | lim8 max |
|---|---:|---:|---:|---:|---:|---:|
| regular_gate01 | 8.893594 | 4.945992 | 8.000000 | 26.555884 | 6.389901 | 8.000000 |
| regular_gate02 | 4.192783 | 3.166811 | 4.192783 | 10.544636 | 4.330179 | 8.000000 |
| regular_gate03 | 6.338537 | 4.689318 | 8.000000 | 19.694116 | 6.789499 | 8.000000 |
| regular_gate04 | 6.501285 | 2.714630 | 6.501285 | 9.065482 | 3.023167 | 8.000000 |
| regular_gate05 | 12.263541 | 7.243054 | 8.000000 | 16.260519 | 8.054621 | 8.000000 |

Interpretation:

```text
R4 is smoother but too destructive.
lim8 is less smooth than R4, but it should preserve more of the original
stabilization correction than R4.
```

## Probe Metrics

Representative local image-motion metrics:

```text
Regular05 safe: SR_pose=4.151, residual_improve=0.516
Regular05 R4:   SR_pose=2.955, residual_improve=0.410
Regular05 lim8: SR_pose=3.629, residual_improve=0.376
```

`lim8` keeps more stabilization than R4 in SR_pose, but still loses some
residual improvement relative to the original safe103crop98. The user-visible
result is still unacceptable because abrupt pose jumps remain.

## Device Results

`lim8` was run through the accepted EGLImage FIFO consumer on all five Regular
clips:

```text
5/5 rc=0
5/5 fallback=0
5/5 frame-index mismatch=0
```

Black-border after crop98:

| Clip | black p95 | frames > 1% | Decision |
|---|---:|---:|---|
| regular_gate01 | 0.028801216 | 26 | Conditional, visual review required |
| regular_gate02 | 0.000290798 | 0 | Pass |
| regular_gate03 | 0.000331163 | 0 | Pass |
| regular_gate04 | 0.002923394 | 0 | Pass |
| regular_gate05 | 0.000000000 | 0 | Pass |

Regular01 remains conditional due to the known gray-threshold / dark-edge risk.

## Evidence

Review directory:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_stride5_pose_delta_limiter_validation\
```

Main review file:

```text
20260720_regular_gate_stride5_pose_delta_limiter_lim8_5clip_review_grid.mp4
```

Per-clip panel order:

```text
source / safe103crop98 / pose_r4 / lim8
```

## Decision

```text
lim8: rejected / diagnostic only.
```

Why:

```text
Hard local delta limiting caps the largest per-frame tx/ty/angle step, but it
does not produce a physically or visually continuous camera path.
```

Required next route:

```text
Stop local limiter tuning. Reframe the blocker as camera-path planning:
separate intended camera motion from shake, enforce temporal continuity inside
the path optimizer, keep FOV/crop constraints in the same model, and use local /
public / internal EIS references before implementing another candidate.
```
