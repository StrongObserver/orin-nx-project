# Regular Gate NvBuffer Pair Resid Closeout - 2026-07-23

## Decision

`resid_r15_s07` is the current Regular-gate quality anchor. The format-matched
NvBuffer pair path was rerun with that anchor on all five Regular clips and is
accepted as a quality-preserving dataflow follow-up with a small measured
device-stage gain.

This does not change the claim boundary:

```text
allowed: quality-preserving device-side dataflow alternative with small stage gain
forbidden: zero-copy full chain, full real-time EIS, full-pipeline acceleration
```

## Why This Run Was Needed

The first five-clip NvBuffer pair review used `inclusion_source_to_dest.csv`.
That matrix family is a geometry-coverage candidate, not the strongest
stabilization baseline. Human review correctly found it visually healthy but
weaker in stabilization.

The root cause was candidate semantics, not the NvBuffer pair transport path:

```text
inclusion_source_to_dest.csv:
  geometry coverage / five-clip inclusion target

candidate_stride5_fixedscale_safe103.csv + crop98:
  earlier Regular05 viewport-stable target

resid_r15_s07:
  current accepted Regular-gate stabilization-strength target
```

Future quality comparisons must keep the same source, matrix, crop/postprocess,
frame rate, and frame-count boundary. Do not compare mixed 30 FPS source panels
against 25 FPS device outputs.

## Five-Clip Device Result

All five Regular clips ran through the format-matched NvBuffer pair path with
`resid_r15_s07`.

| Clip | rc | fallback | trans_mean | trans_p95 | black_p95 | EGL-vs-NvBuffer offset |
|---|---:|---:|---:|---:|---:|---:|
| regular_gate01_regular_10 | 0 | 0 | 0.972874227 | 2.211062239 | 0.027435981 | 0 |
| regular_gate02_regular_19 | 0 | 0 | 0.786741886 | 2.005991900 | 0.000421875 | 0 |
| regular_gate03_regular_13 | 0 | 0 | 0.751183434 | 1.645812497 | 0.000343099 | 0 |
| regular_gate04_regular_8 | 0 | 0 | 0.490487411 | 0.893171580 | 0.003435113 | 0 |
| regular_gate05_regular_6 | 0 | 0 | 1.024843785 | 3.041786998 | 0.000000000 | 0 |

Regular01 remains visual-conditional because the gray-threshold black-border
metric is sensitive to dark edges. Do not treat that metric as an automatic
visual failure unless human review rejects the video.

## Same-Source Regular05 Timing

Same source, same `resid_r15_s07` matrix, same crop/postprocess boundary:

| Metric | EGLImage | NvBuffer pair | Improvement |
|---|---:|---:|---:|
| VPI warp avg | 1.518510 ms | 1.491370 ms | 1.79% |
| Stage frame100 | 7.535330 ms | 7.230350 ms | 4.05% |
| Stage running avg | 9.588980 ms | 9.401090 ms | 1.96% |

Interpretation:

```text
NvBuffer pair avoids part of the EGLImage path overhead and gives a small but
real device-stage improvement. The remaining architecture still has the
block-linear main chain, pitch-linear NV12_ER scratch, transform sandwich, VPI
wrapper, and sync costs.
```

## Evidence

Project-local evidence:

```text
results/regular_gate_nvbuffer_pair_resid_20260723/
results/regular05_eglimage_timing_resid_compare_20260723/
```

Review asset:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260723_regular_gate_nvbuffer_pair_resid_r15_s07_5clip\20260723_regular_gate_nvbuffer_resid_r15_s07_5clip_overview_grid.mp4
```

## Do Not Reopen

```text
Do not use inclusion_source_to_dest or safe103_crop98 as the current
stabilization-strength baseline.

Do not revive lim/R/LP/residual-strength sweeps for this accepted issue.

Do not describe NvBuffer pair as zero-copy or as full EIS pipeline acceleration.
```
