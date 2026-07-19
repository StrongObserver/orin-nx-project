# Hybrid Matrix Handoff Result - 2026-07-19

## Stage Decision

The first hybrid real-time slice is validated as a mock online matrix handoff.

This is not live CPU motion estimation yet. It proves that the MMAPI/VPI/NVENC
device path can consume a per-frame matrix provider shape with frame-index
logging and handoff timing.

## Contract

```text
configs/harness/contracts/hybrid_realtime_matrix_handoff_v1.json
```

Accepted dependency:

```text
post_geometry_identity_first device-side stage demo
```

## What Was Tested

The test used the accepted 120-row matrix stream:

```text
results/device_matrix_warp_demo_20260719/device_matrices_inverse_post_geometry_identity_first.csv
```

The Jetson MMAPI sample was copied and patched to log a mock matrix handoff:

```text
/home/nvidia/orin-nx-project/_mmapi_work/jetson_multimedia_api/samples/99_vpi_transcode_matrix_handoff
```

The patch logs:

```text
MATRIX_HANDOFF frame=<frame> matrix_index=<index> fallback=<0|1> elapsed_us=<time>
```

## Result

### Mock Provider

| Metric | Value | Decision |
|---|---:|---|
| frames processed | 120 | pass |
| matrix fallback count | 0 | pass |
| frame-index mismatch count | 0 | pass |
| handoff avg | 1.376 us | pass |
| handoff p95 | 1.8624 us | pass |
| VPI warp avg at frame 100 | 1.461560 ms | pass |
| accepted device vs mock mean_abs_center_avg | 6.052197 | acceptable encoding variance |
| CPU vs mock mean_abs_center_avg | 30.724221 | close to accepted device candidate |

Interpretation:

```text
The matrix-provider shape works. The handoff overhead is negligible compared
with VPI warp time, frame-index alignment is correct, and no fallback occurred.
```

The output differs slightly from the accepted device output because the MMAPI
sample re-encoded a new output stream. The CPU-vs-mock diff remains close to the
accepted `post_geometry_identity_first` device result.

### FIFO Stream Provider

A second implementation used a real producer/consumer path:

```text
Python matrix producer -> FIFO -> MMAPI/VPI/NVENC consumer
```

The producer streamed the accepted 120-row
`post_geometry_identity_first` matrix CSV into a FIFO. The MMAPI sample consumed
one matrix row per decoded frame.

| Metric | Value | Decision |
|---|---:|---|
| frames processed | 120 | pass |
| streamed matrix rows | 120 | pass |
| fallback count | 0 | pass |
| frame-index mismatch count | 0 | pass |
| VPI warp avg at frame 100 | 1.485500 ms | pass |
| mock vs stream mean_abs_center_avg | 2.427583 | close |
| accepted device vs stream mean_abs_center_avg | 6.247061 | acceptable encoding variance |
| CPU vs stream mean_abs_center_avg | 30.744841 | close to accepted candidate |

The first `MATRIX_HANDOFF` sample includes FIFO startup wait
(`747435 us`). After startup, sampled handoff reads are tens of microseconds.
This is expected for the current process launch order and should not be treated
as steady-state per-frame latency.

Interpretation:

```text
The real producer/consumer matrix stream shape works. The current stream
provider still uses precomputed accepted matrices, so it is a live handoff
prototype, not live CPU motion estimation.
```

## Evidence

```text
results/hybrid_realtime_matrix_handoff_20260719/remote_outputs/mock_handoff_postgeom_idfirst.log
results/hybrid_realtime_matrix_handoff_20260719/remote_outputs/mock_handoff_postgeom_idfirst_120f.h264
results/hybrid_realtime_matrix_handoff_20260719/handoff_summary/summary.csv
results/hybrid_realtime_matrix_handoff_20260719/timing_mock_handoff/summary.csv
results/hybrid_realtime_matrix_handoff_20260719/direct_video_diff_accepted_vs_mock/correctness_summary.csv
results/hybrid_realtime_matrix_handoff_20260719/direct_video_diff_cpu_vs_mock/correctness_summary.csv
results/hybrid_realtime_matrix_handoff_20260719/remote_outputs/stream_handoff_postgeom_idfirst.log
results/hybrid_realtime_matrix_handoff_20260719/remote_outputs/stream_handoff_postgeom_idfirst_120f.h264
results/hybrid_realtime_matrix_handoff_20260719/handoff_summary_stream/summary.csv
results/hybrid_realtime_matrix_handoff_20260719/timing_stream_handoff/summary.csv
results/hybrid_realtime_matrix_handoff_20260719/direct_video_diff_mock_vs_stream/correctness_summary.csv
results/hybrid_realtime_matrix_handoff_20260719/direct_video_diff_cpu_vs_stream/correctness_summary.csv
```

Review copy:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260719_hybrid_realtime_matrix_handoff\20260719_hybrid_realtime_matrix_handoff_sample_outdoor_car_jetson_mock_handoff_grid_compare.mp4
C:\Users\Admin\Videos\orin nx\review\performance\20260719_hybrid_realtime_matrix_handoff\20260719_hybrid_realtime_matrix_handoff_sample_outdoor_car_jetson_stream_handoff_grid_compare.mp4
```

## Claim Boundary

Allowed:

```text
hybrid matrix handoff shape validated
producer/consumer FIFO matrix stream validated
frame-index alignment measured
matrix handoff overhead measured
MMAPI/VPI/NVENC device warp path remains active
```

Forbidden:

```text
live CPU motion estimation
zero-copy full chain
product-grade real-time EIS
VPI optical-flow acceleration
CPU-output pixel equivalence
```

## Next Step

The next step was tested: replacing the CSV producer with a live CPU-estimated
matrix producer on the same 120-frame source clip.

## Live CPU Producer Result

Two first-pass live producers were tested:

```text
cumulative_raw:
  cumulative raw motion matrix from per-frame CPU GFTT/LK/RANSAC estimates

window_correction:
  short-window trajectory smoothing and correction matrix
```

Both use the same FIFO stream consumer and MMAPI/VPI/NVENC path.

| Candidate | fallback count | frame-index mismatch | producer estimate avg | VPI warp avg at frame 100 | CPU-vs-output mean_abs_center_avg | Decision |
|---|---:|---:|---:|---:|---:|---|
| CSV stream provider | 0 | 0 | n/a | 1.485500 ms | 30.744841 | accepted handoff baseline |
| live cumulative raw | 0 | 0 | 18.374103 ms | 1.796820 ms | 42.764717 | live path works, quality weak |
| live window correction | 0 | 0 | 18.093807 ms | 1.714890 ms | 43.405001 | no improvement, reject |

Producer quality was not blocked by feature tracking:

```text
fallback_count = 0
avg_inlier_ratio ~= 0.9594
min_tracked >= 495
```

Interpretation:

```text
The live CPU producer can feed matrices through FIFO with correct frame index
and no fallback, but the first estimator/correction convention is not yet
compatible with the accepted offline matrix quality. The next problem is EIS
estimator convention and causal smoothing, not MMAPI handoff.
```

Review copy:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260719_hybrid_realtime_matrix_handoff\20260719_hybrid_realtime_matrix_handoff_sample_outdoor_car_jetson_live_cpu_provider_grid_compare.mp4
```

## Updated Next Step

Do not continue handoff work blindly. The handoff path is validated.

Next route:

```text
1. Audit the live producer's matrix convention against cpu_stabilize.py exported
   matrices on the same source.
2. Compare per-frame live matrices against the accepted offline
   post_geometry_identity_first matrices.
3. Fix estimator/correction convention before adding more pipeline complexity.
4. Only after live matrices approach accepted offline matrices should the project
   move to lower-copy frame access or VPI optical flow.
```
