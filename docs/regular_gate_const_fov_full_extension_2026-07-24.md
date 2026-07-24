# Regular Gate Const-FOV-Full Extension - 2026-07-24

## Scope

This loop extends the user-accepted Regular05 `constant FOV full` startup-black
fix across all five NUS Regular clips using the accepted stream-only reuse
consumer.

It keeps the current `resid_r15_s07` stabilization-strength anchor and does not
change the EIS algorithm. The change is a constant inclusion-safe extra scale
composed into the existing device matrices for each clip.

## Matrix Generation

The generation route was first validated on Regular05:

```text
compute_inclusion_scale.py --safety-px 4
constant_inclusion_scale.py --frames 0
apply_inclusion_scale_to_matrix.py --compose pre
```

The regenerated Regular05 matrix matched the previously user-accepted
`resid_r15_s07_constant_fov_full.csv` exactly:

```text
translation_abs_mean = 0
linear_fro_abs_mean = 0
max_abs_max = 0
```

Then the same rule was applied to all five Regular clips.

## Jetson Stream-Only Result

All five clips ran through the accepted stream-only reuse consumer on Jetson.

| Clip | rc | fallback | mismatch | constant scale | stage avg | black p95 | black max | frames > 1% black |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| regular_gate01_regular_10 | 0 | 0 | 0 | 1.036530691 | 9.848460 ms | 0.006756728 | 0.010811632 | 2 |
| regular_gate02_regular_19 | 0 | 0 | 0 | 1.060287785 | 8.800470 ms | 0.000043403 | 0.000416667 | 0 |
| regular_gate03_regular_13 | 0 | 0 | 0 | 1.035325964 | 9.287630 ms | 0.000108941 | 0.000238715 | 0 |
| regular_gate04_regular_8 | 0 | 0 | 0 | 1.047682802 | 9.932410 ms | 0.000330946 | 0.000611979 | 0 |
| regular_gate05_regular_6 | 0 | 0 | 0 | 1.038357587 | 9.711440 ms | 0.000000000 | 0.000004340 | 0 |

## Decision

The five-clip extension is technically healthy:

```text
5/5 rc=0
5/5 fallback=0
5/5 frame-index mismatch=0
5/5 readable output
```

Four clips are black-border clean under the current hard gate. Regular01 is
visual-conditional because gray-threshold black-border p95 stays below 1% but
the max slightly exceeds 1% for two frames. This matches the project's earlier
Regular01 dark-edge sensitivity pattern and should be checked by human review
instead of treated as an automatic hard failure.

## Evidence

Local ignored evidence:

```text
results/regular_gate_const_fov_full_extension_20260724/
```

Review copy:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260724_regular_gate_const_fov_full_extension\20260724_regular_gate_const_fov_full_resid_r15_s07_5clip_grid.mp4
```

Summary CSV:

```text
results/regular_gate_const_fov_full_extension_20260724/regular_gate_const_fov_full_summary.csv
```

## Claim Boundary

Allowed:

```text
The user-accepted Regular05 startup-black fix extends technically across all
five Regular clips through the accepted stream-only reuse consumer with rc=0,
fallback=0, and frame-index mismatch=0.
```

Forbidden:

```text
Do not claim all five clips are visually accepted until Regular01 is reviewed.
Do not present constant FOV full as EIS quality improvement.
Do not present it as full real-time EIS, zero-copy, or full-pipeline acceleration.
```
