# Regular Gate Bounded QP Path Loop - 2026-07-21

## Decision Context

`safe103crop98` fixed the earlier zooming and brief black-edge issue, but human
review found abrupt translation/rotation pose jumps. `pose_smooth_r4` reduced
the jumps but weakened stabilization too much. `lim8` preserved more motion but
still had visible jumps.

The selected recovery route replaces post-hoc final-matrix smoothing/limiting
with bounded-delay camera-path optimization.

## Selected Candidate

```text
candidate: bqp_w90_s15_w2_20_w3_200
input: safe103crop98 matrix path
model: tx / ty / theta bounded-delay QP, scale kept from input
window: 90 frames
commit stride: 15 frames
w2: 20
w3: 200
seam continuity: C0/C1/C2 in path-parameter domain
consumer: accepted C++ EGLImage FIFO path
postprocess: crop98
```

This is not a limiter and not an R-radius moving average. It optimizes path
continuity before matrix emission.

## Matrix Result

Regular05 comparison:

| Candidate | trans_d1_p95 | trans_d2_max | trans_d3_max | Decision |
|---|---:|---:|---:|---|
| safe103crop98 | 12.267411933 | 13.950844965 | 13.362624322 | diagnostic, pose jumps |
| lim8 | 8.000000000 | 8.596968915 | 11.692269792 | rejected, still jumps |
| R4 | 7.245537215 | 2.867312244 | 2.256685864 | rejected, too weak |
| offline QP upper bound | 7.665149823 | 2.068776893 | 1.161258154 | matrix pass |
| bounded QP selected | 7.934347526 | 2.172563644 | 1.834481615 | selected for device run |

Five-clip selected matrix summary:

```text
results/regular_gate_bounded_delay_qp_path_loop_20260721/p2_bounded_qp_selected_w90_s15/pose_jump_candidate_summary.csv
```

## Jetson Device Result

The selected bounded-QP matrices ran through the accepted EGLImage FIFO
consumer on all five Regular clips.

```text
5/5 rc=0
5/5 fallback=0
5/5 frame-index mismatch=0
```

Device summary:

```text
results/regular_gate_bounded_delay_qp_path_loop_20260721/p3_five_regular_fifo/regular_gate_bqp_device_summary.csv
```

Per-clip summary:

| Clip | rc | fallback | mismatch | black p95 | geometry p95 | VPI avg ms | Decision |
|---|---:|---:|---:|---:|---:|---:|---|
| regular_gate01_regular_10 | 0 | 0 | 0 | 0.046756077 | 0.000000000 | 1.543830 | conditional visual review |
| regular_gate02_regular_19 | 0 | 0 | 0 | 0.000451606 | 0.001045139 | 1.540140 | pass hard gates |
| regular_gate03_regular_13 | 0 | 0 | 0 | 0.000873264 | 0.000000000 | 1.518040 | pass hard gates |
| regular_gate04_regular_8 | 0 | 0 | 0 | 0.016383247 | 0.001888672 | 1.547960 | conditional visual review |
| regular_gate05_regular_6 | 0 | 0 | 0 | 0.000004340 | 0.000128255 | 1.545310 | pass hard gates |

Regular01 and Regular04 have high gray-threshold black-border values, but
geometry coverage remains below 1%. Treat them as visual-review conditional,
not automatic failures.

## Review Evidence

Review directory:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260721_regular_gate_bounded_qp_path_loop\
```

Main five-clip review grid:

```text
20260721_regular_gate_bounded_qp_path_loop_5clip_review_grid.mp4
```

Per-clip review grids:

```text
20260721_regular_gate_bounded_qp_path_loop_regular_gate01_regular_10_jetson_source_safe_lim8_bqp_grid.mp4
20260721_regular_gate_bounded_qp_path_loop_regular_gate02_regular_19_jetson_source_safe_lim8_bqp_grid.mp4
20260721_regular_gate_bounded_qp_path_loop_regular_gate03_regular_13_jetson_source_safe_lim8_bqp_grid.mp4
20260721_regular_gate_bounded_qp_path_loop_regular_gate04_regular_8_jetson_source_safe_lim8_bqp_grid.mp4
20260721_regular_gate_bounded_qp_path_loop_regular_gate05_regular_6_jetson_source_safe_lim8_bqp_grid.mp4
```

Panel order:

```text
source / safe103crop98 / lim8_rejected / bqp_w90_s15
```

## Mesh Route Decision

Do not open mesh/grid warp yet.

Reason:

```text
The global bounded-QP route materially improves pose-jump matrix metrics and
passes device handoff / geometry hard gates. MeshFlowPy was also not present at
C:\Users\Admin\Documents\MeshFlowPy-master during this run. Mesh should only
open if human review rejects bounded QP and residual-grid diagnostics show local
motion/parallax rather than global path discontinuity.
```

## Next Step

Human review should focus on whether `bqp_w90_s15` removes or materially reduces
the hard pose jumps while preserving enough stabilization versus `lim8` and not
becoming as weak as `R4`.

Do not claim final 5/5 Regular pass until that visual review is accepted.

