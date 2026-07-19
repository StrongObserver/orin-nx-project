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

## Evidence

```text
results/hybrid_realtime_matrix_handoff_20260719/remote_outputs/mock_handoff_postgeom_idfirst.log
results/hybrid_realtime_matrix_handoff_20260719/remote_outputs/mock_handoff_postgeom_idfirst_120f.h264
results/hybrid_realtime_matrix_handoff_20260719/handoff_summary/summary.csv
results/hybrid_realtime_matrix_handoff_20260719/timing_mock_handoff/summary.csv
results/hybrid_realtime_matrix_handoff_20260719/direct_video_diff_accepted_vs_mock/correctness_summary.csv
results/hybrid_realtime_matrix_handoff_20260719/direct_video_diff_cpu_vs_mock/correctness_summary.csv
```

Review copy:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260719_hybrid_realtime_matrix_handoff\20260719_hybrid_realtime_matrix_handoff_sample_outdoor_car_jetson_mock_handoff_grid_compare.mp4
```

## Claim Boundary

Allowed:

```text
hybrid matrix handoff shape validated
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

The next step is to replace the mock matrix provider with a live CPU-estimated
matrix provider on the same 120-frame source clip.

Keep the first live version small:

```text
CPU estimator may remain separate or minimally integrated.
The output must still log frame index, matrix index, fallback, handoff latency,
VPI warp timing, and total run status.
```

Stop if:

```text
frame index drifts;
fallback appears;
output is empty or unreadable;
quality is clearly worse than post_geometry_identity_first;
the change requires a broad C++ rewrite before a small verifier exists.
```
