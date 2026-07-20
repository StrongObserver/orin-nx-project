# Regular05 Viewport / Zooming Fix - 2026-07-20

## Problem

Human review found that `delay90_fifo`, `stride5_fifo`, `stride5_csv`, and
`live_stride5` all have the same viewport artifact:

```text
1. visible zooming / breathing: the view scale feels non-constant;
2. a narrow left-bottom black edge flashes near the beginning.
```

This review supersedes further progress expansion. The goal is to solve the
viewport artifact before extending to more clips.

## Root Cause

The artifact is not introduced by stride5, FIFO, or the accepted C++ consumer.
It is already present in the shared device-ready matrix sequence.

The first rows of the existing delay90 matrices show the issue directly:

```text
frame 0: scale = 1.000000, tx = 0, ty = 0
frame 1: scale ~= 1.176-1.177, ty ~= -45 px
```

That means the video jumps from an identity first frame to a post-geometry
zoomed and translated matrix at frame 1. This explains both the start-up
viewport jump and the brief edge exposure.

The rest of the sequence also has a non-constant effective scale around
`1.175-1.180`, which can be perceived as zoom breathing even when the absolute
scale delta is numerically small.

## Fix Candidate

The focused candidate is:

```text
input matrix: stride5 delay90 source_to_dest
fixed scale: median scale * 1.03
first frame: copy next matrix, not identity
postprocess: crop98
consumer: accepted EGLImage FIFO path
```

Generated files:

```text
results/regular05_viewport_fix_20260720/candidate_stride5_fixedscale_safe103.csv
results/regular05_viewport_fix_20260720/stride5_safe103_fifo_eglimage_output.h264
results/regular05_viewport_fix_20260720/stride5_safe103_crop98_fifo_eglimage.mp4
```

## Metrics

Scale stability:

| Candidate | scale_min | scale_max | scale_delta_max |
|---|---:|---:|---:|
| original stride5 | 1.000000 | 1.180257 | 0.177082 |
| fixed safe103 | 1.178057 | 1.178057 | ~0 |

Black-border gate:

| Candidate | black p95 | black max | frames > 1% |
|---|---:|---:|---:|
| live_stride5 | 0.000784288 | 0.003637153 | 0 |
| safe103 device | 0.000265408 | 0.003637153 | 0 |
| safe103_crop98 | 0.000000000 | 0.000008681 | 0 |

Device path:

```text
safe103 through accepted EGLImage FIFO:
rc=0
fallback_count=0
frame_index_mismatch_count=0
VPI warp running avg at frame 100 ~= 1.535 ms
```

Difference versus live_stride5:

```text
mean_abs_center_avg = 17.174438
p95_abs_center_avg = 57.483333
```

The diff is expected because fixed scale plus crop98 intentionally changes the
framing. This candidate should be judged by human review: if zooming and the
left-bottom black edge are gone, decide whether the narrower field of view is
acceptable.

## Review

Review copy:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular05_viewport_fix\20260720_regular05_viewport_fix_regular_gate05_regular_6_jetson_source_livestride5_safe103_safe103crop98_grid.mp4
```

Panel order:

```text
source / live_stride5 / safe103 / safe103_crop98
```

## Claim Boundary

Allowed:

```text
The shared zooming artifact is caused by the device-ready viewport matrix
sequence, especially the identity frame0 -> post-geometry frame1 jump and
non-constant effective scale.
safe103_crop98 removes measured black-border exposure and fixes scale variation
on Regular05 under the accepted EGLImage FIFO consumer.
```

Forbidden:

```text
This is not proof of all-scene EIS quality.
This is not a zero-latency real-time result.
This is not a general five-clip Regular producer until all five clips are run
and reviewed.
```

## Next Step

Human review decides the next branch:

```text
If safe103_crop98 is accepted:
  freeze it as the Regular05 viewport-stable candidate and then test across the
  five Regular clips under a new contract.

If safe103_crop98 removes zooming/black edge but FOV loss is unacceptable:
  try a less aggressive fixed-scale/crop trade-off, but keep scale constant and
  avoid identity frame0.

If safe103_crop98 still has zooming:
  stop local patching and route to internal/industrial EIS guidance for viewport
  planning, FOV-safe crop, and causal smoothing practice.
```
