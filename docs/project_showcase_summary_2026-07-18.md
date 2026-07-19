# Orin NX EIS Showcase Summary - 2026-07-18

## One-Line Project Story

Built a controllable Jetson Orin NX EIS pipeline with reproducible quality gates,
Jetson timing evidence, and scoped hardware-acceleration boundary tests.

## Current Baseline

Accepted CPU baseline:

```text
lp_rigid_strength080_dynzoom106
```

Key settings:

```text
lp_rigid
stabilization_strength=0.80
crop_ratio=0.90
lanczos resize
sharpen_strength=0.25
dynamic_zoom max=1.06
opencv_cpu warp
estimate_scale=1.0
```

Why this baseline:

- It reduced the visible `regular05` tail rollback/corner-pull risk better than
  the previous affine and full-strength rigid candidates.
- It keeps rollback at zero on the selected Regular05 Jetson evidence clip.
- It is a practical stage baseline, not a claim that global-warp EIS solves
  all local/parallax/rolling-shutter cases.

Jetson timing:

| Metric | Value |
|---|---:|
| Resolution | 640x360 |
| Frames | 180 |
| avg_estimate_ms | 8.568 |
| avg_warp_ms | 7.936 |
| total_wall_time_s | 8.473 |
| rollback_frames | 0 |
| p95_invalid_mask_ratio | 0.001196 |

## What Was Proven

### Quality And Evidence Control

- Main gate is `nus_regular_gate_v1`.
- Running, QuickRotation, Parallax, Zooming, and Crowd are challenge or
  diagnostic sets, not headline pass-rate pools.
- Harness validation passes for the current Jetson CPU baseline evidence.

### Backend Swap Boundary

Same-input Regular05 backend test:

| Backend | avg_warp_ms | total_wall_time_s | Result |
|---|---:|---:|---|
| opencv_cpu | 7.936 | 8.473 | current best |
| vpi_cuda | 9.621 | 9.382 | slower |
| vpi_cpu | 11.934 | 9.640 | slower |
| vpi_vic | 14.531 | 10.132 | slower |

Conclusion: simple VPI backend replacement inside the current 640x360 Python
pipeline is not an acceleration result.

### Motion-Estimation Cost Boundary

`estimate_scale` reduces runtime. The first simple downscale attempts hurt
smoothness, but adding a denser feature grid produced one objective-gated
candidate that the user accepted after side-by-side review:

| Candidate | avg_estimate_ms | total_wall_time_s | second_top5_improve | Result |
|---|---:|---:|---:|---|
| est1p0 | 8.568 | 8.473 | 0.006 | accepted |
| est0p75 | 6.350 | 8.091 | -0.018 | faster, rejected |
| est0p5 | 3.020 | 7.647 | -0.003 | faster, rejected |
| est0p5_grid16 | 3.022 | 7.565 | 0.0003 | Regular performance baseline |

Conclusion: `est0p5_grid16` is human-accepted on all five Regular review clips
and passed objective gates on all five `nus_regular_gate_v1` clips. It reduces
Regular05 total wall time by about 11%. The Regular05 tail still has slight
shake, which is treated as the current global-warp EIS model boundary rather
than a blocker.

Keep two baselines distinct:

```text
quality-safe baseline:
  estimate_scale=1.0, feature_grid_size=12

Regular performance baseline:
  estimate_scale=0.5, feature_grid_size=16
```

Regular gate validation:

| Clip | SR_pose | residual_improve | second_top5_improve | grade | layered |
|---|---:|---:|---:|---|---|
| regular_gate01 | 19.516 | 0.758 | 0.527 | A/B | pass |
| regular_gate02 | 5.912 | 0.398 | 0.683 | A/B | pass |
| regular_gate03 | 19.323 | 0.804 | 0.743 | A/B | pass |
| regular_gate04 | 16.304 | 0.760 | 0.757 | C | pass |
| regular_gate05 | 6.031 | 0.610 | 0.000 | A/B | pass |

### VPI High-Resolution Module Value

VPI CUDA helps when warp workload is large:

| Resolution | OpenCV CPU ms | VPI CUDA ms | Speedup |
|---|---:|---:|---:|
| 1280x720 | 6.118 | 4.523 | 1.35x |
| 1920x1080 | 13.569 | 7.398 | 1.83x |
| 2560x1440 | 22.920 | 10.651 | 2.15x |
| 3840x2160 | 48.452 | 20.836 | 2.33x |

Conclusion: hardware acceleration is workload- and dataflow-dependent. It is not
enough to swap APIs inside a small Python loop.

### GStreamer / NVMM Readiness

Minimum Jetson path is available and reached EOS:

```text
filesrc -> qtdemux -> h264parse -> nvv4l2decoder -> NVMM -> nvvidconv -> BGRx -> fakesink
```

This proves dataflow readiness only. It does not prove EIS acceleration yet.

### Device-Side MMAPI / VPI / NVENC Boundary

The next non-Python path has been advanced from readiness probing to a scoped
device-side warp/encode run:

```text
H264 input -> MMAPI decode / NvBufSurface -> pitch-linear NV12_ER scratch
-> VPI CUDA warp -> block-linear NV12 -> NVENC
```

Same-source testing found the correct matrix direction for this path:

| Matrix direction | Sampled black-border behavior | Decision |
|---|---:|---|
| forward CPU matrix | about 30% black area | reject |
| inverse CPU matrix | about 2.8-2.9% black area | current default |

Current boundary: this is an offline CPU-matrix-driven device warp/encode
milestone. It is not yet real-time full EIS and not CPU-output equivalence.
A 120-frame local panel comparison between CPU stabilized and device inverse
outputs showed `mean_abs_center_avg=37.033757`, so the remaining parity gap must
be treated explicitly.

Follow-up Jetson A/B:

| Candidate | mean_abs_center_avg vs CPU | Decision |
|---|---:|---|
| old inverse | 44.739667 | valid path, poor parity |
| 120-row aligned identity-first | 46.884302 | worse |
| 120-row post-geometry | 30.688605 | strong improvement |
| 120-row post-geometry + first-frame identity | 30.241568 | current best device candidate |
| Catmull-Rom interpolation | 30.902334 | slower and worse |

Conclusion: composing CPU dynamic zoom and crop geometry into the device matrix
is the right direction. Keeping the prepended first frame as identity gives a
small additional improvement. Catmull-Rom interpolation is not worth adopting.
An identity transcode baseline already has `mean_abs_center_avg=25.664099`
against source, so raw pixel diff has a high codec/colorspace floor and does not
map cleanly to geometric parity alone.

## How To Explain The Trade-Off

The project currently has a credible CPU EIS baseline and several measured
optimization boundaries:

- more aggressive motion-estimation downscaling is faster but harms smoothness;
- VPI is slower in the current small full pipeline;
- VPI is faster for high-resolution warp-heavy modules;
- GStreamer/NVMM is available for a future real dataflow optimization loop.
- MMAPI/VPI/NVENC device-side warp is now validated as a stage boundary, with a
  known CPU-output parity gap.

This is stronger than claiming one fake speedup. It shows measurement discipline:
the project separates algorithm quality, module acceleration, and data movement.

## Evidence Paths

```text
results/evidence/20260718_jetson_regular05_perf/
results/perf_backend_compare_20260718/backend_compare_summary.md
results/estimate_scale_regular05_20260718/estimate_scale_summary.md
results/estimate_scale_quality_perf_20260718/quality_perf_summary.md
results/regular_gate_est0p5_grid16_validation_20260718/regular_gate_validation_summary.md
results/vpi_resolution_scaling_benchmark/vpi_module_summary.md
results/gst_nvmm_probe_20260718_summary.md
results/same_source_matrix_20260719/device_matrix_inverse.log
results/device_matrix_warp_demo_20260719/triptych_cpu_vs_device/summary.md
docs/stage_result_regular_performance_baseline_2026-07-18.md
docs/gstreamer_nvmm_latency_plan_2026-07-18.md
docs/device_matrix_warp_demo_2026-07-19.md
```

Review videos:

```text
C:\Users\Admin\Videos\orin nx\review\quality\20260718_regular05_new_method\
C:\Users\Admin\Videos\orin nx\review\performance\20260718_jetson_regular05_perf\
C:\Users\Admin\Videos\orin nx\review\performance\20260718_backend_compare\
C:\Users\Admin\Videos\orin nx\review\performance\20260718_estimate_scale_regular05\
C:\Users\Admin\Videos\orin nx\review\performance\20260718_estimate_scale_quality_perf\
C:\Users\Admin\Videos\orin nx\review\performance\20260718_regular_gate_est0p5_grid16_validation\
C:\Users\Admin\Videos\orin nx\review\performance\20260719_same_source_matrix_device_warp\
```

## Next Best Step

The next most valuable loop is not another global LP parameter sweep.

Use one of these scoped directions:

1. Keep `post_geometry_identity_first` as the current device-side warp/encode
   stage candidate.
2. Continue parity work only if the next scoped change isolates a border
   workaround or colorspace/encoding difference.
3. Do not move to real-time online motion estimation until the parity boundary is
   closed.

Active next contracts:

```text
configs/harness/contracts/regular_performance_baseline_est0p5_grid16.json
configs/harness/contracts/regular05_estimate_scale_quality_perf.json
configs/harness/contracts/regular_gate_est0p5_grid16_validation_v1.json
configs/harness/contracts/gst_nvmm_decode_convert_latency_v1.json
configs/harness/contracts/device_matrix_warp_demo_v1.json
```
