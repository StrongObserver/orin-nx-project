# Jetson Orin NX EIS Project

Resume-oriented engineering project for real-time electronic image
stabilization (EIS) and heterogeneous vision acceleration on NVIDIA Jetson Orin
NX.

The project is not just a demo. The target is an explainable engineering loop:

```text
shaky video
-> controllable CPU EIS baseline
-> quality and artifact gates
-> Jetson timing evidence
-> scoped backend / dataflow optimization
-> honest boundary and trade-off summary
```

## Current Highlights

```text
Regular performance baseline:
  lp_rigid_strength080_dynzoom106 + estimate_scale=0.5 + feature_grid_size=16
  NUS Regular gate: 5/5 objective pass and human accepted

VPI acceleration boundary:
  640x360 full Python EIS pipeline is slower with VPI backend swap
  720p -> 4K warp-heavy module shows 1.35x -> 2.33x VPI CUDA speedup

Challenge model boundary:
  Running / QuickRotation / Parallax / Crowd expose global-warp FOV, rotation,
  parallax, and foreground-motion limits

GStreamer/NVMM boundary:
  Python appsink/appsrc pass-through costs about 15.81 ms/frame before EIS work,
  so direct Python-in-the-loop EIS integration is not the next acceleration path

Device-side MMAPI/VPI/NVENC path:
  C++ Jetson Multimedia API experiments now run decode -> NvBufSurface scratch
  -> VPI CUDA warp -> block-linear NV12 -> NVENC. Same-source inverse matrix
  drive is validated as an offline-matrix device-side warp/encode path, not a
  real-time full EIS pipeline yet. The latest panel-diff check also shows it is
  not yet a close CPU-output reproduction because CPU crop/zoom/sharpen parity
  is not implemented on the device path.
```

## Current Stage

The accepted custom CPU baseline is frozen as:

```text
smoothing_method=lp_rigid
stabilization_strength=0.80
crop_ratio=0.90
crop_interpolation=lanczos
sharpen_strength=0.25
dynamic_zoom=true, max_zoom=1.06
warp_backend=opencv_cpu
estimate_scale=1.0
```

Main evidence clip:

```text
results/nus_regular_gate_v1/raw_clips/regular_gate05_regular_6.mp4
```

Jetson same-input evidence for the frozen CPU baseline:

| Metric | Value |
|---|---:|
| Resolution | 640x360 |
| Frames | 180 |
| avg_estimate_ms | 8.568 |
| avg_warp_ms | 7.936 |
| total_wall_time_s | 8.473 |
| mask_safety_rollback_frames | 0 |
| p95_invalid_mask_ratio | 0.001196 |

This baseline was selected because it reduces the visible `regular05` tail
pull/rollback risk better than the full-strength affine or rigid variants. It is
a practical stage baseline, not a claim that one global warp solves all
parallax, rolling-shutter, or local non-rigid motion cases.

## Backend Boundary

Same-input Jetson backend comparison kept the quality configuration fixed and
changed only `warp_backend`:

| Backend | avg_estimate_ms | avg_warp_ms | total_wall_time_s | Result |
|---|---:|---:|---:|---|
| opencv_cpu | 8.568 | 7.936 | 8.473 | current best |
| vpi_cuda | 8.777 | 9.621 | 9.382 | slower |
| vpi_cpu | 8.620 | 11.934 | 9.640 | slower |
| vpi_vic | 8.587 | 14.531 | 10.132 | slower |

Conclusion: for the current 640x360 Python/OpenCV/VPI full-pipeline path, VPI
warp backend replacement is not an acceleration result. Prior warp-only
high-resolution benchmarks still show VPI CUDA can help when the warp workload
is large enough, but this project should not claim full-pipeline VPI acceleration
until same-input Jetson timing proves it.

## Optimization Findings

### Motion-Estimation Downscaling

`estimate_scale` is a real speed knob. The first simple downscale attempts were
faster but failed smoothness; a second scoped contract found one objective-gated
candidate that the user accepted after side-by-side review.

| Candidate | avg_estimate_ms | total_wall_time_s | second_top5_improve | Result |
|---|---:|---:|---:|---|
| est1p0 | 8.568 | 8.473 | 0.006 | accepted baseline |
| est0p75 | 6.350 | 8.091 | -0.018 | faster, quality gate fail |
| est0p5 | 3.020 | 7.647 | -0.003 | faster, quality gate fail |
| est0p5_grid16 | 3.022 | 7.565 | 0.0003 | Regular performance baseline |

Conclusion: downscaling motion estimation can reduce total Jetson wall time by
about 11% on Regular05. `est0p5_grid16` is human-accepted on all five Regular
review clips and passed objective gates on all five `nus_regular_gate_v1` clips.

Keep two baselines distinct:

```text
quality-safe baseline:
  estimate_scale=1.0, feature_grid_size=12

Regular performance baseline:
  estimate_scale=0.5, feature_grid_size=16
```

The performance baseline does not erase the quality-safe baseline. Use the
quality-safe baseline when the priority is conservatism; use the Regular
performance baseline when the priority is the measured Regular-gate speedup.

Regular gate validation:

| Clip | SR_pose | residual_improve | second_top5_improve | grade | layered |
|---|---:|---:|---:|---|---|
| regular_gate01 | 19.516 | 0.758 | 0.527 | A/B | pass |
| regular_gate02 | 5.912 | 0.398 | 0.683 | A/B | pass |
| regular_gate03 | 19.323 | 0.804 | 0.743 | A/B | pass |
| regular_gate04 | 16.304 | 0.760 | 0.757 | C | pass |
| regular_gate05 | 6.031 | 0.610 | 0.000 | A/B | pass |

### High-Resolution VPI Module Evidence

VPI CUDA remains useful at module scale when the warp workload is large enough:

| Resolution | OpenCV CPU ms | VPI CUDA ms | Speedup |
|---|---:|---:|---:|
| 1280x720 | 6.118 | 4.523 | 1.35x |
| 1920x1080 | 13.569 | 7.398 | 1.83x |
| 2560x1440 | 22.920 | 10.651 | 2.15x |
| 3840x2160 | 48.452 | 20.836 | 2.33x |

This supports a careful claim: VPI CUDA accelerates high-resolution warp-heavy
modules, but the current small full pipeline does not benefit from a simple
backend swap.

### GStreamer / NVMM Probe

The Jetson has a working minimum hardware decode / NVMM / conversion path:

```text
filesrc -> qtdemux -> h264parse -> nvv4l2decoder -> NVMM -> nvvidconv -> BGRx -> fakesink
```

The 1080p probe reached EOS successfully in about 1.60s. This is only a dataflow
readiness result, not EIS acceleration.

Python-in-the-loop boundary:

| Path | Result |
|---|---:|
| appsink BGRx readback | 7.93 ms/frame |
| appsink -> appsrc -> encode pass-through | 15.81 ms/frame |

Conclusion: direct Python GStreamer integration is not the next best way to
accelerate the current CPU EIS pipeline. If this direction resumes, prefer a
C++/CUDA or device-side dataflow path.

### Device-Side Matrix Warp Boundary

The current non-Python device-side path uses Jetson Multimedia API and VPI CUDA:

```text
H264 input -> decode/NvBufSurface -> pitch-linear NV12_ER scratch
-> VPI CUDA warp -> block-linear NV12 -> NVENC
```

Same-source matrix tests showed that the forward CPU matrix creates excessive
black border on the device path, while the inverse matrix gives normal sampled
black-border sanity:

| Output | Black ratio | Decision |
|---|---:|---|
| device forward matrix | about 0.303 | reject |
| device inverse matrix | about 0.028 to 0.029 | current default |

The device path is still a scoped stage boundary. A local 120-frame panel
comparison between CPU stabilized and device inverse output has
`mean_abs_center_avg=37.033757` and `p95_abs_center_avg=138.416667`, so the
project must not claim CPU-output equivalence. The main known gap is that the
device path currently uses linear VPI warp with zero border and does not
reproduce CPU post-processing such as dynamic zoom, fixed crop/resize, Lanczos
interpolation, and sharpen.

The next device-side A/B test was run with generated 120-row matrix candidates:

```text
device_matrices_inverse_aligned_identity_first.csv
device_matrices_inverse_with_post_geometry.csv
```

Result:

| Candidate | mean_abs_center_avg vs CPU | p95_abs_center_avg vs CPU | Decision |
|---|---:|---:|---|
| old inverse | 44.739667 | 156.975000 | valid path, poor parity |
| aligned identity first | 46.884302 | 159.958333 | worse |
| post geometry | 30.688605 | 116.958333 | strong improvement |
| post geometry, identity first | 30.241568 | 115.866667 | current best device candidate |
| post geometry, identity first, Catmull-Rom | 30.902334 | 117.875000 | slower and worse |

The post-geometry matrix shows that composing CPU dynamic zoom + crop geometry
into the device matrix is the right direction. An identity transcode baseline
already has `mean_abs_center_avg=25.664099` versus source, so raw pixel diff has
a high codec/colorspace floor. The best device output still does not reach
CPU-output equivalence, so real-time motion estimation remains premature.

## Control Plane

Harness and evaluation files:

```text
configs/harness/gates.json
configs/harness/contracts/jetson_regular05_perf.json
configs/harness/contracts/regular_performance_baseline_est0p5_grid16.json
configs/harness/contracts/regular05_estimate_scale_quality_perf.json
configs/harness/contracts/regular_gate_est0p5_grid16_validation_v1.json
configs/harness/contracts/gst_nvmm_decode_convert_latency_v1.json
configs/harness/contracts/device_matrix_warp_demo_v1.json
configs/harness/evaluation_datasets.json
configs/harness/metric_schema.json
docs/harness_engineering_v1.md
docs/loop_engineering_v2.md
docs/evaluation_system_v1.md
```

Useful checks:

```powershell
py -3.12 scripts\harness_runner.py doctor
py -3.12 scripts\harness_runner.py list-gates
py -3.12 scripts\harness_runner.py check-evaluation-datasets
py -3.12 scripts\harness_runner.py validate-evidence results\evidence\20260718_jetson_regular05_perf --date 20260718
```

Important gate roles:

| Gate | Role |
|---|---|
| `nus_regular_gate_v1` | main quality gate |
| `nus_running_gate_v1` | challenge / model-boundary gate |
| `regular05_perf_gate` | same-input Jetson performance gate |

Do not use Running, QuickRotation, Parallax, Zooming, or Crowd as headline pass
rates. They are challenge or diagnostic sets unless a future evaluation contract
promotes a specific claim.

## Evidence

Local evidence and videos are intentionally ignored by Git.

Key local paths:

```text
results/evidence/20260718_jetson_regular05_perf/
results/perf_backend_compare_20260718/backend_compare_summary.md
results/estimate_scale_regular05_20260718/estimate_scale_summary.md
results/estimate_scale_quality_perf_20260718/quality_perf_summary.md
results/regular_gate_est0p5_grid16_validation_20260718/regular_gate_validation_summary.md
results/vpi_resolution_scaling_benchmark/vpi_module_summary.md
results/gst_nvmm_probe_20260718_summary.md
results/gst_appsrc_encode_boundary_20260718/summary.md
results/same_source_matrix_20260719/device_matrix_inverse.log
results/device_matrix_warp_demo_20260719/triptych_cpu_vs_device/summary.md
docs/stage_result_regular_performance_baseline_2026-07-18.md
docs/device_matrix_warp_demo_2026-07-19.md
docs/gstreamer_nvmm_latency_plan_2026-07-18.md
C:\Users\Admin\Videos\orin nx\review\quality\20260718_regular05_new_method\
C:\Users\Admin\Videos\orin nx\review\performance\20260718_jetson_regular05_perf\
C:\Users\Admin\Videos\orin nx\review\performance\20260718_backend_compare\
C:\Users\Admin\Videos\orin nx\review\performance\20260718_estimate_scale_regular05\
C:\Users\Admin\Videos\orin nx\review\performance\20260718_estimate_scale_quality_perf\
C:\Users\Admin\Videos\orin nx\review\performance\20260718_regular_gate_est0p5_grid16_validation\
```

## Next Engineering Direction

Do not continue blind global affine/rigid parameter sweeps on `regular05`.

The current device-side acceleration path should stay scoped:

```text
1. keep CPU quality-safe and Regular performance baselines distinct;
2. keep Challenge sets as model-boundary evidence, not headline pass rates;
3. keep high-resolution VPI warp/remap as module-level acceleration evidence;
4. use MMAPI/NvBufSurface scratch-buffer device-side flow for the next
   acceleration path;
5. keep same-source inverse-matrix device output as a warp/encode boundary until
   CPU post-processing parity or a direct raw-video diff supports a stronger
   claim;
6. do not return to Python appsink/appsrc EIS integration.
```
