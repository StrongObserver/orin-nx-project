# Regular05 Hybrid Matrix Handoff - 2026-07-20

## Stage Decision

Regular05 `source_to_dest` FIFO matrix handoff is now validated on Jetson.

This proves:

```text
Python matrix producer / CSV streamer -> FIFO -> MMAPI/VPI/NVENC consumer
```

can deliver per-frame matrices for the real Regular05 EIS clip with correct
frame-index alignment and no fallback. It is still not a full real-time EIS
result because the current live producer is a simple short-window estimator and
does not reproduce the accepted offline CPU baseline matrices.

## What Ran

Input:

```text
results/regular05_device_replay_20260719/regular05_source.h264
```

Producer:

```text
scripts/live_matrix_producer.py
--output-convention source_to_dest
--max-frames 180
```

Consumer:

```text
_mmapi_work/jetson_multimedia_api/samples/99_vpi_transcode_matrix_stream/multivideo_transcode
VPI_MATRIX_FIFO=results/regular05_hybrid_matrix_handoff_20260720/matrix_stream_fifo.csv
```

Important command shape:

```text
./multivideo_transcode num_files 1 <input.h264> H264 <output.h264> H264
```

Do not use `-i/-o` for this MMAPI sample.

## Evidence

Local result directory:

```text
results/regular05_hybrid_matrix_handoff_20260720/
```

Main files:

```text
stream_regular05_source_to_dest.h264
stream_regular05_source_to_dest.log
live_regular05_source_to_dest.csv
remote_live_regular05_source_to_dest_log.csv
handoff_summary_stream/summary.csv
timing_stream_handoff/summary.csv
black_border_stream/summary.csv
direct_video_diff_cpu_vs_stream/correctness_summary.csv
direct_video_diff_fixed_vs_stream/correctness_summary.csv
matrix_diff_fixed_vs_live/summary.csv
regular05_source_cpu_fixed_stream_grid.mp4
```

Review copy:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular05_hybrid_matrix_handoff\20260720_regular05_hybrid_matrix_handoff_regular_gate05_regular_6_jetson_source_cpu_fixed_stream_grid.mp4
```

## Measured Result

FIFO / matrix handoff:

| Metric | Value |
|---|---:|
| MATRIX_HANDOFF samples | 11 |
| fallback_count | 0 |
| frame_index_mismatch_count | 0 |
| handoff elapsed avg | 96.181 us |
| handoff elapsed p95 | 377.310 us |
| handoff elapsed max | 693.882 us |

VPI warp timing:

| Metric | Value |
|---|---:|
| last sampled frame | 100 |
| last running avg VPI warp | 0.647185 ms |

Producer timing:

| Metric | Value |
|---|---:|
| rows / frames | 180 |
| fallback rows | 0 |
| avg estimate_ms | 2.577 ms |
| max estimate_ms | 11.243 ms |

Black border:

| Metric | Value |
|---|---:|
| frames measured | 180 |
| mean black border | 0.000000000 |
| p95 black border | 0.000000000 |
| max black border | 0.000000000 |
| frames_gt_0p01 | 0 |

Diff checks:

| Comparison | mean_abs_center_avg | p95_abs_center_avg |
|---|---:|---:|
| CPU baseline vs stream handoff | 26.273266 | 91.133333 |
| fixed device replay vs stream handoff | 26.018254 | 90.383611 |

Matrix convention check:

| Comparison | translation_abs_mean | translation_abs_p95 |
|---|---:|---:|
| fixed replay matrix vs live producer matrix | 35.890052 px | 62.762400 px |

Interpretation:

```text
The handoff and device-side warp path are working. The remaining gap is producer
quality/convention relative to the accepted offline matrices, not FIFO delivery.
```

## Claim Boundary

Allowed:

```text
Regular05 source_to_dest FIFO matrix handoff runs on Jetson.
Matrix handoff has zero fallback and zero frame-index mismatch in the sampled log.
VPI warp in the MMAPI path runs at about 0.65 ms/frame order for 640x360.
The output has no measured edge-connected black-border regression.
```

Forbidden:

```text
full real-time EIS
CPU-output equivalence
all-scene EIS quality
VPI optical-flow acceleration
zero-copy full chain
```

## Next Step

Do not add more pipeline complexity yet.

The next useful work is producer alignment:

```text
1. Compare the live producer trajectory against cpu_stabilize.py exported
   offline matrices.
2. Bring the live producer closer to the accepted offline convention or classify
   the gap as causal-smoothing/model quality.
3. Only after producer output is close enough should the project extend this
   handoff to all five Regular clips or move to lower-copy / VPI optical-flow
   work.
```
