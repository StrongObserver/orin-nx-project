# Regular Gate Stabilization Strength Recovery - 2026-07-21

## Trigger

Human review of `bqp_w90_s15` found:

```text
No black border.
No zooming.
Normal color.
Some stabilization exists, but stabilization strength is not obvious enough.
```

So `bqp_w90_s15` is healthy in geometry / color / handoff, but too weak as a
stabilization result.

## MeshFlowPy Source Inspection

The user-provided archive was extracted locally under ignored evidence:

```text
results/external_refs_20260721/MeshFlowPy-master-ce3fbe97e66632b73d85b1ad237ff37a7af12d1a/
```

Relevant source files:

```text
src/MIA.cpp
src/MIA.hpp
src/mia_MeshGrid.cpp
src/mia_MeshGrid.hpp
wapper/python_warpper.cpp
```

Conclusion:

```text
MeshFlowPy exposes mia_flow.calc_flow(image0, image1, mask). Internally it uses
MIA / mesh vertices / LSCG to compute dense or mesh-like optical flow. It is a
spatial alignment / flow backend, not a temporal camera-path optimizer. It is
useful for a future mesh route, but it does not directly solve the current
global-path stabilization-strength issue.
```

## Root Cause

Residual-motion measurement on Regular05 explains the weak BQP result:

| Candidate | residual trans mean | residual trans p95 | Interpretation |
|---|---:|---:|---|
| source | 4.545601211 | 12.269095166 | shaky input |
| safe103crop98 | 2.103411091 | 6.455903068 | strongest stabilization, but pose jumps |
| lim8 | 2.476191066 | 9.994355982 | stronger than BQP, but still jumps |
| R4 | 4.016137992 | 9.855062313 | too weak |
| bqp_w90_s15 | 3.915331140 | 10.497760325 | too weak |

`bqp_w90_s15` optimized continuity, but it reduced too much of the original
safe103 correction. The better target is therefore not stronger global
smoothing. It is localized spike repair on top of the strong safe103 correction:
keep the strong stabilization path, and repair only the D2/D3 discontinuities.

## Selected Enhanced Candidate

```text
candidate: spike_mid_t6_b70_r2_i2
input: safe103crop98 matrix path
method: local D2 pose-spike repair
threshold: 6 px equivalent
blend: 0.70
radius: 2
iterations: 2
postprocess: crop98
consumer: accepted C++ EGLImage FIFO path
```

Regular05 matrix comparison:

| Candidate | trans_d1_p95 | trans_d2_max | trans_d3_max | Decision |
|---|---:|---:|---:|---|
| safe103crop98 | 12.267411933 | 13.950844965 | 13.362624322 | strong but jumpy |
| lim8 | 8.000000000 | 8.596968915 | 11.692269792 | rejected, still jumps |
| bqp_w90_s15 | 7.934347526 | 2.172563644 | 1.834481615 | smooth but too weak |
| spike_mid | 8.964161501 | 6.486622351 | 9.488187420 | stronger stabilization candidate |

Regular05 residual-motion comparison after device/crop98:

| Candidate | residual trans mean | residual trans p95 |
|---|---:|---:|
| source | 4.545601211 | 12.269095166 |
| safe103crop98 | 2.103411091 | 6.455903068 |
| bqp_w90_s15 | 3.915331140 | 10.497760325 |
| spike_mid | 2.787707733 | 10.204933052 |

`spike_mid` is not as strong as safe103crop98, but it is materially stronger
than BQP while repairing the worst matrix spikes more than lim8.

## Jetson Device Result

The selected `spike_mid` matrices ran through the accepted EGLImage FIFO
consumer on all five Regular clips:

```text
5/5 rc=0
5/5 fallback=0
5/5 frame-index mismatch=0
```

Device summary:

```text
results/regular_gate_stabilization_strength_recovery_20260721/p3_spike_mid_fifo/regular_gate_spike_mid_device_summary.csv
```

Per-clip summary:

| Clip | rc | fallback | mismatch | black p95 | geometry p95 | Decision |
|---|---:|---:|---:|---:|---:|---|
| regular_gate01_regular_10 | 0 | 0 | 0 | 0.047806640 | 0.000000000 | conditional visual review |
| regular_gate02_regular_19 | 0 | 0 | 0 | 0.000539496 | 0.001227430 | pass hard gates |
| regular_gate03_regular_13 | 0 | 0 | 0 | 0.000921658 | 0.000000000 | pass hard gates |
| regular_gate04_regular_8 | 0 | 0 | 0 | 0.019547309 | 0.002228732 | conditional visual review |
| regular_gate05_regular_6 | 0 | 0 | 0 | 0.000004340 | 0.000000000 | pass hard gates |

Regular01 and Regular04 keep the same gray-threshold conditional pattern as
previous candidates: gray black-border p95 is high, but geometry p95 stays below
1%. They require visual review rather than automatic rejection.

## Review Evidence

Review directory:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260721_regular_gate_stabilization_strength_recovery\
```

Main five-clip review grid:

```text
20260721_regular_gate_stabilization_strength_recovery_5clip_review_grid.mp4
```

Panel order:

```text
source / safe103crop98 / bqp_w90_s15 / spike_mid
```

## Follow-Up Decision

Human review later rejected `spike_mid` as still insufficient for the current
quality target. It is retained as diagnostic evidence only.

The accepted follow-up is documented in:

```text
docs/regular_gate_residual_closed_loop_2026-07-21.md
```

`resid_r15_s07` supersedes `spike_mid` for the current Regular gate
stabilization-strength recovery result. The user accepted `resid_r15_s07` on
2026-07-22 as visibly stronger than BQP/spike_mid, with no hard pose snaps and
no visible black borders.

