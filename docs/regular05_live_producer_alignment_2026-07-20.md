# Regular05 Live Producer Alignment - 2026-07-20

## Stage Decision

The Regular05 matrix handoff path is not the current bottleneck. A fixed-matrix
FIFO control replay reproduced the accepted fixed replay exactly, so FIFO
delivery and the MMAPI/VPI/NVENC consumer are aligned.

The live producer quality gap is mainly caused by the producer's smoothing model.
The original short-window producer mostly emitted fixed post-geometry matrices
instead of the accepted LP-rigid stabilization matrices. Reusing the offline
LP-rigid stabilizer inside the producer closes most of the matrix gap, but this
is an offline upper bound, not a zero-latency real-time result.

## Fixed FIFO Control

Input matrix:

```text
results/regular05_device_replay_20260719/device_regular05_postgeom_idfirst_forward.csv
```

FIFO output:

```text
results/regular05_live_producer_alignment_20260720/fixed_fifo_control.h264
```

Result:

| Metric | Value |
|---|---:|
| fallback_count | 0 |
| frame_index_mismatch_count | 0 |
| VPI warp running avg at frame 100 | 0.563228 ms |
| black_border_p95 | 0.000972005 |
| fixed replay vs fixed FIFO mean_abs_center_avg | 0.000000 |

Interpretation:

```text
The FIFO stream provider and MMAPI consumer do not introduce the live-output
quality gap. When the accepted fixed matrices are streamed through FIFO, the
result is pixel-identical to the previous fixed replay artifact.
```

## Producer Alignment

Baseline live producer:

| Candidate | translation_abs_mean | translation_abs_p95 | Decision |
|---|---:|---:|---|
| original live window=1 | 35.890052 px | 62.762400 px | too far from fixed replay |
| simple window=15 | 35.113947 px | 61.280390 px | tiny improvement only |
| offline LP rigid upper bound | 0.501640 px | 1.341285 px | validates producer-quality route |

The `offline_lp_rigid` producer mode reuses the current CPU baseline's LP-rigid
smoothing convention, then streams `source_to_dest` matrices through the same
FIFO consumer.

FIFO output:

```text
results/regular05_live_producer_alignment_20260720/offline_lp_fifo_output.h264
```

Measured result:

| Metric | Value |
|---|---:|
| fallback_count | 0 |
| frame_index_mismatch_count | 0 |
| handoff elapsed avg | 61.901636 us |
| handoff elapsed p95 | 199.766000 us |
| VPI warp running avg at frame 100 | 0.380287 ms |
| black_border_p95 | 0.001477648 |
| fixed replay vs offline-LP FIFO mean_abs_center_avg | 5.163971 |
| fixed replay vs offline-LP FIFO p95_abs_center_avg | 15.877778 |

Review copy:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular05_live_producer_alignment\20260720_regular05_live_producer_alignment_regular_gate05_regular_6_jetson_source_fixed_live_offline_lp_grid.mp4
```

## Claim Boundary

Allowed:

```text
Fixed matrices streamed through FIFO reproduce the accepted fixed replay.
The live producer gap is a producer smoothing/trajectory problem, not a FIFO
or VPI warp problem.
An offline LP-rigid producer can reduce the fixed-vs-produced matrix translation
gap from about 35.9 px mean to about 0.5 px mean.
```

Forbidden:

```text
full real-time EIS
zero-latency LP-rigid producer
CPU-output equivalence as a general claim
VPI optical-flow acceleration
all-scene EIS quality
```

## Next Route

Do not jump to VPI optical flow or all-five-Regular expansion yet.

The next contract should be a bounded delayed-window producer:

```text
1. Keep the same source_to_dest FIFO consumer.
2. Replace the offline full-clip LP upper bound with a bounded-latency producer,
   such as 15/30/45-frame delayed smoothing.
3. Measure matrix gap, black border, handoff timing, and review video.
4. Decide the latency-quality trade-off explicitly before calling it real-time.
```

If bounded delayed smoothing cannot get close enough without unacceptable
latency, classify the gap as a causal-smoothing limitation and route to a new
model or internal EIS reference prompt.
