# Regular05 Producer Scheduling Optimization - 2026-07-20

## Decision

The live producer bottleneck is now attributed and reduced without changing the
accepted C++ EGLImage consumer path.

The dominant cost was repeated LP prefix solving inside
`bounded_delay_lp_rigid`. A new optional `--lp-prefix-stride` parameter keeps the
original default behavior at `1`, and allows a bounded-delay producer to solve
LP prefixes every N frames. The tested stride-5 candidate preserves the
Regular05 hard gates and materially reduces producer compute time.

This is a producer scheduling optimization, not a full real-time EIS claim.

## Frozen Boundary

```text
input: Regular05 / regular_gate05_regular_6
matrix convention: source_to_dest
producer mode: bounded_delay_lp_rigid
producer delay: 90 frames
consumer: accepted C++ MMAPI/VPI/NVENC EGLImage FIFO sample
VPI interpolation: linear
border mode: VPI_BORDER_ZERO
```

Rejected routes remain rejected:

```text
old pitch-pointer wrapper
EGLImage image-wrapper reuse
direct mismatched NvBuffer input
block-linear VPI scratch pair
pitch-linear main encoder chain
```

## Producer Profiling

Jetson producer-only timing:

| Candidate | LP stride | LP calls | LP prefix frames | LP solve ms | mask safety ms | total ms |
|---|---:|---:|---:|---:|---:|---:|
| delay90 baseline | 1 | 89 | 12015 | 57068.382 | 10729.033 | 68507.848 |
| delay90 stride5 | 5 | 19 | 2582 | 12756.410 | 2308.349 | 15687.400 |

Interpretation:

```text
LP prefix solving, not LK/RANSAC or FIFO row writing, dominated producer wall
time. Stride5 reduces Jetson producer-only total time from about 68.5s to about
15.7s for 180 frames.
```

Matrix difference versus stride1 on the same Jetson input:

| Metric | Value |
|---|---:|
| frames_compared | 180 |
| translation_abs_mean | 0.037780 px |
| translation_abs_p95 | 0.293390 px |
| translation_abs_max | 1.128080 px |
| linear_fro_abs_mean | 0.001462 |

## Device Consumer Verification

The stride5 matrix CSV was run through the accepted EGLImage FIFO consumer.

| Metric | Value |
|---|---:|
| rc | 0 |
| MATRIX_HANDOFF samples | 11 |
| fallback_count | 0 |
| frame_index_mismatch_count | 0 |
| handoff elapsed avg | 42.567 us |
| handoff elapsed p95 | 98.547 us |
| VPI warp running avg at frame 100 | 1.530820 ms |
| black_border_p95 | 0.000784288 |
| black_border max | 0.003637153 |
| frames_gt_0p01 | 0 |

Direct diff against the prior delay90 FIFO output:

| Metric | Value |
|---|---:|
| frames_compared | 180 |
| mean_abs_all_avg | 6.669974 |
| p95_abs_all_avg | 21.250000 |
| mean_abs_center_avg | 7.147095 |
| p95_abs_center_avg | 22.161111 |

The diff is expected because stride5 reuses LP prefixes between solve points.
Use the review grid and black-border gate for acceptance, not raw pixel
equivalence.

## Concurrent Live Verification

The same stride5 producer was then run concurrently with the accepted EGLImage
FIFO consumer through a real FIFO.

| Metric | Value |
|---|---:|
| producer rc | 0 |
| consumer rc | 0 |
| wall_time_ms | 17533 |
| MATRIX_HANDOFF samples | 11 |
| fallback_count | 0 |
| frame_index_mismatch_count | 0 |
| handoff elapsed avg, excluding first producer wait | 28.504 us |
| handoff elapsed p95, excluding first producer wait | 39.025 us |
| VPI warp running avg at frame 100 | 1.513030 ms |
| black_border_p95 | 0.000784288 |
| black_border max | 0.003637153 |
| frames_gt_0p01 | 0 |
| diff vs precomputed stride5 | 0.000000 |

The first MATRIX_HANDOFF sample waits for producer startup and LP solve:

```text
frame=1 elapsed_us ~= 15.7s
```

This is expected for the current script structure because the producer still
computes the full delayed matrix sequence before the consumer receives the first
row. After startup, FIFO handoff is tens of microseconds. This result reduces
Regular05 concurrent live wall time from about 68.7s to 17.5s for 180 frames,
but it is still not zero-latency real-time EIS.

Tegrastats was captured during the concurrent live run:

```text
results/regular05_producer_scheduling_optimization_20260720/live_stride5_tegrastats.log
```

The log shows one CPU core saturated during producer LP solve, with GPU activity
appearing near the device warp/encode portion. This is a perf/power evidence
anchor, not a calibrated power measurement.

## Evidence

Local evidence:

```text
results/regular05_producer_scheduling_optimization_20260720/
```

Key files:

```text
results/regular05_producer_scheduling_optimization_20260720/jetson_delay90_stride1_timing.csv
results/regular05_producer_scheduling_optimization_20260720/jetson_delay90_stride5_timing.csv
results/regular05_producer_scheduling_optimization_20260720/jetson_diff_stride5_vs_stride1/summary.csv
results/regular05_producer_scheduling_optimization_20260720/handoff_stride5_fifo/summary.csv
results/regular05_producer_scheduling_optimization_20260720/warp_stride5_fifo/summary.csv
results/regular05_producer_scheduling_optimization_20260720/black_stride5_fifo/summary.csv
results/regular05_producer_scheduling_optimization_20260720/diff_stride5_fifo_vs_delay90_fifo/correctness_summary.csv
results/regular05_producer_scheduling_optimization_20260720/live_stride5_timing.csv
results/regular05_producer_scheduling_optimization_20260720/live_stride5_wall_time.csv
results/regular05_producer_scheduling_optimization_20260720/handoff_live_stride5_fifo/summary.csv
results/regular05_producer_scheduling_optimization_20260720/warp_live_stride5_fifo/summary.csv
results/regular05_producer_scheduling_optimization_20260720/black_live_stride5_fifo/summary.csv
results/regular05_producer_scheduling_optimization_20260720/diff_live_stride5_vs_precomputed_stride5/correctness_summary.csv
results/regular05_producer_scheduling_optimization_20260720/live_stride5_tegrastats.log
```

Review copy:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular05_producer_scheduling_optimization\20260720_regular05_producer_scheduling_optimization_regular_gate05_regular_6_jetson_source_delay90fifo_stride5fifo_grid.mp4
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular05_producer_scheduling_optimization\20260720_regular05_producer_scheduling_optimization_regular_gate05_regular_6_jetson_source_stride5csv_livestride5_grid.mp4
```

## Claim Boundary

Allowed:

```text
Regular05 bounded-delay producer compute was reduced by solving LP prefixes at
a stride of 5 instead of every frame.
Stride5 preserves the accepted EGLImage FIFO hard gates on Regular05:
rc=0, fallback=0, mismatch=0, and black-border p95 below 1%.
Concurrent live stride5 reduces the 180-frame wall time from about 68.7s to
17.5s while producing the same device output as precomputed stride5.
```

Forbidden:

```text
full real-time EIS
zero-latency producer
zero-copy full chain
VPI optical-flow acceleration
all-scene EIS quality
CPU-output pixel equivalence
```

## Next Step

The immediate next step is human visual review of the stride5 grids. If
accepted, extend the same producer scheduling optimization to all five Regular
clips under a separate five-clip contract and keep per-clip failures visible.

The remaining performance issue is startup latency: the current producer solves
the delayed matrix sequence before the consumer receives frame 1. A future route
can reduce first-row latency, but that would be a new scheduling contract and
must preserve matrix quality.
