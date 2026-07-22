# Regular Gate Residual Closed-Loop Recovery - 2026-07-21

## Trigger

`bqp_w90_s15` solved the hard continuity problem but was too weak. `spike_mid`
kept more stabilization but was still rejected by human review.

The next route is residual closed-loop correction:

```text
1. Start from the strong safe103crop98 output.
2. Estimate residual frame-to-frame motion in that output.
3. Smooth that residual path.
4. Compose the residual correction back into the original device matrix.
```

This directly targets residual shake instead of only optimizing matrix
smoothness.

## Knowledge / Mesh Check

The external knowledge search emphasized residual suppression, zero velocity,
drift correction, panning intent, and confidence gating.

`MeshFlowPy-master.zip` was extracted and inspected earlier:

```text
results/external_refs_20260721/MeshFlowPy-master-ce3fbe97e66632b73d85b1ad237ff37a7af12d1a/
```

It is an MIA / dense mesh flow backend, not a temporal camera-path optimizer.
Residual-grid diagnostics on Regular05 did not show a clear local-motion or
parallax-only signature, so the mesh route remains closed for now.

## Selected Candidate

```text
candidate: resid_r15_s07
base: safe103crop98 matrix and output
residual smoothing radius: 15
residual correction strength: 0.7
postprocess: crop98
consumer: accepted C++ EGLImage FIFO path
```

## Regular05 Comparison

Residual motion after crop98:

| Candidate | trans mean | trans p95 | angle p95 | Notes |
|---|---:|---:|---:|---|
| source | 4.545601211 | 12.269095166 | 0.013632336 | shaky input |
| safe103crop98 | 2.103411091 | 6.455903068 | 0.014768418 | strongest previous, but jumpy |
| bqp_w90_s15 | 3.915331140 | 10.497760325 | 0.012972871 | too weak |
| spike_mid | 2.787707733 | 10.204933052 | 0.014022947 | stronger than BQP, still rejected |
| resid_r15_s07 | 1.032654799 | 3.256414700 | 0.006553800 | strongest residual suppression |

Matrix jump risk:

```text
resid_r15_s07 improves video residual motion strongly, but raw matrix D2/D3
metrics are higher than BQP/R4 because residual closed-loop correction is more
aggressive. This was the main visual-review risk before acceptance.
```

Human review result, 2026-07-22:

```text
Accepted. The user confirmed that resid_r15_s07 is visibly more stable than
bqp_w90_s15 / spike_mid, and that it does not show hard pose snaps or visible
black borders in the review videos.
```

## Jetson Device Result

Full-length matrices were generated for every clip. A previous truncated probe
caused Regular02 fallback, but the full-length rerun fixed that.

Final device result:

```text
5/5 rc=0
5/5 fallback=0
5/5 frame-index mismatch=0
```

Device summary:

```text
results/regular_gate_stabilization_strength_recovery_20260721/p5_residual_closed_loop_fifo_full/regular_gate_residual_closed_loop_full_device_summary.csv
```

Per-clip summary:

| Clip | rc | fallback | mismatch | black p95 | geometry p95 | Decision |
|---|---:|---:|---:|---:|---:|---|
| regular_gate01_regular_10 | 0 | 0 | 0 | 0.048346137 | 0.000478299 | conditional visual review |
| regular_gate02_regular_19 | 0 | 0 | 0 | 0.000499349 | 0.004569228 | pass hard gates |
| regular_gate03_regular_13 | 0 | 0 | 0 | 0.000878038 | 0.000005859 | pass hard gates |
| regular_gate04_regular_8 | 0 | 0 | 0 | 0.019831814 | 0.002818359 | conditional visual review |
| regular_gate05_regular_6 | 0 | 0 | 0 | 0.000008681 | 0.000664930 | pass hard gates |

Regular01 and Regular04 retain the known gray-threshold / dark-edge conditional
pattern in automated metrics. Geometry remains below 1%, and the user visual
review accepted the result with no visible black border, so these are treated as
metric-conditionals rather than visual failures.

## Review Evidence

Review directory:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260721_regular_gate_residual_closed_loop_full\
```

Main five-clip review grid:

```text
20260721_regular_gate_residual_closed_loop_full_5clip_review_grid.mp4
```

Panel order:

```text
source / safe103crop98 / spike_mid / resid_r15_s07
```

## Decision

Human review has accepted `resid_r15_s07`:

```text
1. It provides stronger visible stabilization than bqp_w90_s15 / spike_mid.
2. It avoids the hard pose snaps that made safe103crop98 / lim8 unacceptable.
3. The Regular01 / Regular04 gray black-border flags are not visible black-border
   failures in the accepted review.
```

This closes the stabilization-strength recovery loop for the current Regular
gate. Do not continue blind limiter, R-radius, LP-weight, or residual-strength
sweeps on this same issue. Mesh/grid warp remains deferred because the accepted
global residual closed-loop result is sufficient for this stage and the
residual-grid diagnostics did not justify local-motion/parallax escalation.

