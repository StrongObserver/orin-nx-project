# Regular05 Bounded-Delay Producer - 2026-07-20

## Stage Decision

The bounded-delay producer route is valid, but the current 45-frame delayed
candidate is not yet close enough to the offline LP-rigid upper bound.

This means:

```text
FIFO/MMAPI/VPI/NVENC remains healthy.
Bounded delay improves the live producer substantially.
The current delayed-window implementation still leaves a large tail matrix gap.
Do not expand to five Regular clips yet.
```

## Baselines

| Candidate | translation_abs_mean | translation_abs_p95 | Meaning |
|---|---:|---:|---|
| original live producer | 35.890052 px | 62.762400 px | too weak |
| offline LP-rigid upper bound | 0.501640 px on Jetson | 1.341285 px on Jetson | non-realtime target |
| bounded delay 15, local matrix only | 14.565927 px | 45.419468 px | improves but weak |
| bounded delay 30, local matrix only | 8.817800 px | 28.767727 px | better |
| bounded delay 45, Jetson run | 7.308316 px | 33.183706 px | valid intermediate |
| bounded delay 90, Jetson run | 1.099470 px | 3.399610 px | current best bounded-delay producer |

The local delay-45 matrix looked slightly better than the Jetson-generated
delay-45 matrix. The accepted comparison should use the Jetson-generated matrix
and output.

## Jetson Delay-45 Run

Producer:

```text
scripts/live_matrix_producer.py
--matrix-mode bounded_delay_lp_rigid
--producer-delay-frames 45
--output-convention source_to_dest
```

Output:

```text
results/regular05_bounded_delay_producer_20260720/delay45_fifo_output.h264
```

Measured result:

| Metric | Value |
|---|---:|
| producer delay | 45 frames |
| producer avg estimate_ms | 8.239195 ms |
| fallback_count | 0 |
| frame_index_mismatch_count | 0 |
| handoff elapsed avg | 80.774364 us |
| handoff elapsed p95 | 302.850000 us |
| VPI warp running avg at frame 100 | 0.659701 ms |
| black_border_p95 | 0.000143447 |
| black_border max | 0.003671875 |
| fixed replay vs delay45 mean_abs_center_avg | 17.206929 |
| fixed replay vs delay45 p95_abs_center_avg | 57.894444 |

Review copy:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular05_bounded_delay_producer\20260720_regular05_bounded_delay_producer_regular_gate05_regular_6_jetson_source_fixed_live_delay45_grid.mp4
```

## Interpretation

The delay-45 run is a real improvement over the original live producer:

```text
translation_abs_mean: 35.89 px -> 7.31 px
translation_abs_p95: 62.76 px -> 33.18 px
```

It also keeps the hard gates healthy:

```text
fallback_count = 0
frame_index_mismatch_count = 0
black_border_p95 < 0.01
```

But it is still far from the offline LP-rigid upper bound:

```text
offline LP-rigid upper bound: 0.50 px mean / 1.34 px p95
delay45: 7.31 px mean / 33.18 px p95
```

So delay45 should be treated as a meaningful intermediate step, not the final
producer.

## Jetson Delay-90 Run

Producer:

```text
scripts/live_matrix_producer.py
--matrix-mode bounded_delay_lp_rigid
--producer-delay-frames 90
--output-convention source_to_dest
```

Output:

```text
results/regular05_bounded_delay_producer_20260720/delay90_fifo_output.h264
```

Measured result:

| Metric | Value |
|---|---:|
| producer delay | 90 frames |
| producer avg estimate_ms | 8.216220 ms |
| fallback_count | 0 |
| frame_index_mismatch_count | 0 |
| handoff elapsed avg | 70.474364 us |
| handoff elapsed p95 | 245.510000 us |
| VPI warp running avg at frame 100 | 0.772729 ms |
| black_border_p95 | 0.000670356 |
| black_border max | 0.003702257 |
| fixed replay vs delay90 mean_abs_center_avg | 9.753476 |
| fixed replay vs delay90 p95_abs_center_avg | 32.461389 |

Review copy:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular05_bounded_delay_producer\20260720_regular05_bounded_delay_producer_regular_gate05_regular_6_jetson_source_fixed_delay45_delay90_grid.mp4
```

Delay90 is now the best tested bounded-delay candidate:

```text
translation_abs_mean: original 35.89 px -> delay45 7.31 px -> delay90 1.10 px
translation_abs_p95:  original 62.76 px -> delay45 33.18 px -> delay90 3.40 px
```

It is close to the offline LP-rigid upper bound, but its delay is 90 frames, so
it must be presented as a latency-quality trade-off, not as zero-latency EIS.

## Viewport Stability Diagnosis

The user reported that delay45 and delay90 still have slight black border,
unstable framing, and abrupt zoom-in / zoom-out feeling.

Matrix diagnosis showed:

```text
fixed replay, delay45, and delay90 all carry a large device-side similarity
scale around 1.14-1.18 because the current VPI path uses the source_to_dest
warp plus post-geometry, while VPI uses zero border and does not reproduce the
CPU output crop/resize/sharpen path as an actual post-process.
```

A quick fixed-scale candidate was tested:

```text
candidate_delay90_fixedscale_firstcopy.csv
```

This candidate:

```text
scale_delta_p95 ~= 0
trans_delta_max: 44.34 px -> 16.09 px
```

but it failed the hard black-border gate:

| Candidate | black_border_p95 | frames_gt_0p01 | Decision |
|---|---:|---:|---|
| delay90 original | 0.000670356 | 0 | keep |
| fixed-scale first-copy | 0.025768229 | 27 | reject |

Review diagnostic copy:

```text
C:\Users\Admin\Videos\orin nx\review\diagnostic\20260720_regular05_viewport_stability\20260720_regular05_viewport_stability_regular_gate05_regular_6_jetson_delay90_vs_fixedscale_reject_grid.mp4
```

Interpretation:

```text
The abrupt framing feeling is real, but simply forcing a constant scale is not
safe. It reduces one kind of viewport jump while exposing VPI zero-border black
areas. Keep original delay90 as the current best candidate until a safer local
window or border/FOV strategy is tested.
```

## Claim Boundary

Allowed:

```text
A 45-frame bounded-delay producer improves matrix quality substantially over
the original live producer while preserving FIFO/VPI correctness and black-border
hard gates on Regular05.
```

Forbidden:

```text
full real-time EIS
zero-latency EIS
producer parity with offline LP-rigid
all-scene EIS quality
VPI optical-flow acceleration
```

## Next Step

Do not expand to five Regular clips until the user reviews the delay90 video.

The next useful action is:

```text
1. User reviews the delay90 grid video and the fixed-scale reject diagnostic if
   needed.
2. If delay90 is acceptable despite its 90-frame delay, run the same producer
   across the five Regular gate clips.
3. If the framing/black-border artifact is not acceptable, try local-window LP
   or a border/FOV-safe post-process. Do not use fixed-scale forcing as-is.
```

## Local-Window And FOV-Safe Follow-Up

After user review, delay45 and delay90 still showed slight black border,
unstable framing, and abrupt zoom-like changes. Two recovery directions were
tested.

### Local-Window LP

Local-window LP was tested only in matrix space first. It reduced per-frame
motion jumps, but it moved too far away from the accepted fixed replay matrices.

| Candidate | translation_abs_mean | translation_abs_p95 | Decision |
|---|---:|---:|---|
| local-window 45 | 37.406169 px | 85.283207 px | reject |
| local-window 60 | 33.153689 px | 80.101945 px | reject |
| local-window 90 | 17.322793 px | 56.890645 px | reject |

Do not run these local-window candidates on Jetson in the current form.

### Fade-In FOV-Safe Candidate

The safer recovery was to keep the delay90 matrix sequence, but fade in the
first frames from identity to the delay90 transform. This targets the obvious
frame0 identity -> frame1 zoom/translation jump without forcing constant scale
across the whole clip.

Candidate:

```text
candidate_delay90_fade15.csv
```

Jetson output:

```text
results/regular05_bounded_delay_producer_20260720/delay90_fade15_output.h264
```

Measured result:

| Metric | Value |
|---|---:|
| fallback_count | 0 |
| frame_index_mismatch_count | 0 |
| handoff elapsed avg | 63.990182 us |
| handoff elapsed p95 | 214.390500 us |
| VPI warp running avg at frame 100 | 0.503813 ms |
| black_border_p95 | 0.000670356 |
| black_border max | 0.003702257 |
| delay90 vs fade15 mean_abs_center_avg | 3.230821 |
| delay90 vs fade15 p95_abs_center_avg | 10.638889 |

Review copy:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular05_bounded_delay_producer\20260720_regular05_bounded_delay_producer_regular_gate05_regular_6_jetson_source_fixed_delay90_fade15_grid.mp4
```

Decision:

```text
delay90_fade15 is the current preferred viewport-stability candidate. It keeps
the hard black-border gate healthy, changes the delay90 output only mildly, and
smooths the startup transition. User review should compare delay90 and fade15
before expanding to five Regular clips.
```

### Constant Safe Scale Candidate

The user still reported zooming after reviewing delay90_fade15, so a stronger
viewport-stability candidate was tested. The failed `fixed-scale first-copy`
candidate used the median scale and exposed black borders. A safer constant scale
candidate was generated by fixing scale near the high end of the delay90 scale
range:

```text
candidate_delay90_fixedscale_safe103.csv
```

Jetson output:

```text
results/regular05_bounded_delay_producer_20260720/delay90_safe103_output.h264
```

Measured result:

| Metric | Value |
|---|---:|
| scale_delta_p95 | ~0 |
| fallback_count | 0 |
| frame_index_mismatch_count | 0 |
| handoff elapsed avg | 69.939364 us |
| handoff elapsed p95 | 241.478500 us |
| VPI warp running avg at frame 100 | 0.630590 ms |
| black_border_p95 | 0.000238715 |
| black_border max | 0.003702257 |
| delay90 vs safe103 mean_abs_center_avg | 15.132977 |
| delay90 vs safe103 p95_abs_center_avg | 50.061389 |

Review copy:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular05_bounded_delay_producer\20260720_regular05_bounded_delay_producer_regular_gate05_regular_6_jetson_source_fixed_delay90_safe103_grid.mp4
```

Decision:

```text
delay90_safe103 passes the black-border hard gate and removes scale variation,
but it changes framing more than fade15 and sacrifices more field of view. It is
a valid review candidate, not an automatic replacement. Human review should
compare delay90_fade15 and delay90_safe103.
```

### Border/FOV-Safe Post-Process

Because safe103 still sacrifices field of view, a post-process route was tested:
keep the original delay90 matrix sequence and apply a fixed border-safe output
post-process to the rendered video.

Candidates:

| Candidate | black_border_p95 | max black | delay90 diff center mean | Decision |
|---|---:|---:|---:|---|
| crop98 | 0.000000000 | 0.000008681 | 8.146386 | best black-border cleanup |
| reflect8 | 0.000038411 | 0.004283854 | 10.828121 | passes hard gate |
| reflect8_crop98 | 0.000042534 | 0.004231771 | 6.853398 | lowest diff among post-process variants |

Review copies:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular05_bounded_delay_producer\20260720_regular05_bounded_delay_producer_regular_gate05_regular_6_jetson_delay90_postprocess_grid.mp4
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular05_bounded_delay_producer\20260720_regular05_bounded_delay_producer_regular_gate05_regular_6_jetson_source_delay90_safe103_postcrop98_grid.mp4
```

Interpretation:

```text
Post-processing does not change the stabilization matrix or remove all perceived
zooming, but it is the safest way tested so far to remove visible edge-connected
black border without increasing matrix scale. `crop98` is the cleanest black
border option; `reflect8_crop98` changes the delay90 video least among the
post-process variants.
```

### Safe103 + Crop98 Combined Candidate

After safe103 still showed a small left-edge black border in a few frames, the
safe scale candidate was combined with a fixed 98% output crop.

Candidate:

```text
safe103_post_crop98.mp4
```

Measured result:

| Metric | Value |
|---|---:|
| scale_delta_p95 | ~0 before post-process |
| black_border_mean | 0.000000000 |
| black_border_p95 | 0.000000000 |
| black_border_max | 0.000000000 |
| frames_gt_0p001 | 0 |
| frames_gt_0p01 | 0 |
| safe103 vs safe103_crop98 mean_abs_center_avg | 8.079741 |
| safe103 vs safe103_crop98 p95_abs_center_avg | 26.200000 |

Review copy:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular05_bounded_delay_producer\20260720_regular05_bounded_delay_producer_regular_gate05_regular_6_jetson_source_safe103_safe103crop_postcrop_grid.mp4
```

Decision:

```text
safe103_crop98 is the strongest tested candidate for eliminating both visible
scale variation and measured black border. It has an explicit field-of-view
cost: safe103 already uses a higher constant scale, and crop98 adds a further
fixed 2% crop. If this is not visually acceptable, the current global-matrix
device replay path has likely reached the practical FOV/stability boundary for
Regular05 and should route to internal/industry EIS guidance.
```
