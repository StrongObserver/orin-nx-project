# Hardware Acceleration Boundary

## VPI Full-Pipeline Result

Same-input `regular_gate05_regular_6` backend swap:

| Backend | avg_warp_ms | total_wall_time_s | Result |
|---|---:|---:|---|
| opencv_cpu | 7.936 | 8.473 | current best |
| vpi_cuda | 9.621 | 9.382 | slower |
| vpi_cpu | 11.934 | 9.640 | slower |
| vpi_vic | 14.531 | 10.132 | slower |

Conclusion:

```text
Simple VPI backend replacement does not accelerate the current 640x360 Python
full pipeline.
```

## VPI Module-Level Result

High-resolution warp-heavy benchmark. Two timing modes now exist:

- earlier scaling probe, used for the trend chart;
- 2026-07-22 rerun, used as the current checkpoint evidence.

Earlier scaling probe:

| Resolution | OpenCV CPU ms | VPI CUDA ms | Speedup |
|---|---:|---:|---:|
| 1280x720 | 6.118 | 4.523 | 1.35x |
| 1920x1080 | 13.569 | 7.398 | 1.83x |
| 2560x1440 | 22.920 | 10.651 | 2.15x |
| 3840x2160 | 48.452 | 20.836 | 2.33x |

2026-07-22 module rerun, no video output:

| Resolution | OpenCV CPU ms | VPI CUDA ms | Speedup |
|---|---:|---:|---:|
| 1920x1080 | 36.926 | 18.426 | 2.00x |
| 2560x1440 | 29.045 | 15.778 | 1.84x |
| 3840x2160 | 69.742 | 27.617 | 2.53x |

2026-07-22 video-output sanity path:

| Resolution | OpenCV CPU ms | VPI CUDA ms | Speedup | center mean abs diff | center p95 abs diff |
|---|---:|---:|---:|---:|---:|
| 1920x1080 | 27.177 | 14.040 | 1.94x | 12.459 | 34.283 |
| 3840x2160 | 60.776 | 23.895 | 2.54x | 12.469 | 35.133 |

Conclusion:

```text
VPI CUDA helps when the warp workload is large enough to amortize conversion and
readback costs. The output is not pixel-equivalent to OpenCV CPU; the observed
differences are consistent with color conversion, interpolation, border handling,
and encoding differences.
```

## VPI Power / Perf-Per-Watt

4K PerspectiveWarp stable workload, 600 frames, INA3221 `VDD_IN` board-input
power:

| Path | Avg ms | FPS | VDD_IN avg | FPS/W | CPU avg | GR3D avg |
|---|---:|---:|---:|---:|---:|---:|
| OpenCV CPU | 48.995 | 20.410 | 12.136 W | 1.682 | 77.74% | 1.31% |
| VPI CUDA | 20.514 | 48.747 | 11.118 W | 4.385 | 32.06% | 18.96% |

Interpretation:

```text
For this 4K warp-heavy workload, VPI CUDA is about 2.39x faster and about 2.61x
better in FPS/W. This is module-level perf/watt evidence, not full EIS pipeline
power evidence.
```

## VPI Operator Boundary

Current Jetson VPI 2.2.7 Python backend probe:

| Operator | CPU | CUDA | PVA | VIC | OFA | Decision |
|---|---|---|---|---|---|---|
| PerspectiveWarp | pass | pass | not current Python path | not current Python path | n/a | Main module-level acceleration result |
| PyrLK | pass | pass | fail | fail | fail | Not a current OpenCV replacement; OpenCV was faster and kept more valid points |
| Dense Optical Flow | fail | fail | fail | fail | fail | Python binding path unavailable |
| Remap | native abort | native abort | native abort | native abort | native abort | Future C++/official sample route only |

## GStreamer / NVMM Readiness

Minimum Jetson path reached EOS:

```text
filesrc -> qtdemux -> h264parse -> nvv4l2decoder -> NVMM -> nvvidconv -> BGRx -> fakesink
```

This proves dataflow readiness, not EIS acceleration.

Measured latency anchors:

| Case | EOS | Wall time |
|---|---|---:|
| decode/NVMM/convert/fakesink, avg of 3 | 3/3 | 1.931 s |
| hardware encode path | 1/1 | 1.299 s |
| CPU-readable boundary | 1/1 | 1.960 s |
| Python appsink BGRx pull | 240 frames | 1.904 s / 7.93 ms per frame |
| Python appsink -> appsrc -> encode | 240 frames | 3.793 s / 15.81 ms per frame |

Interpretation:

```text
The Jetson dataflow path is available and measurable. Python appsink readback is
about 7.93 ms/frame, and the full Python appsink -> appsrc -> encode
pass-through costs about 15.81 ms/frame before any EIS computation. This is a
strong boundary signal: direct Python-in-the-loop GStreamer EIS integration is
not the next best acceleration path.
```

## Device-Side MMAPI / VPI / NVENC Path

The next non-Python path has now been validated as a scoped device-side warp and
encode boundary:

```text
H264 input -> MMAPI decode / NvBufSurface
-> pitch-linear NV12_ER scratch
-> VPI CUDA warp
-> block-linear NV12
-> NVENC
```

Historical outdoor-car result:

```text
On the outdoor-car smoke source, inverse/post-geometry matrices validated the
MMAPI/VPI/NVENC dataflow shape. This is not the current EIS-quality convention.
```

Current boundary:

```text
This is an offline CPU-matrix-driven device warp/encode demo. It is not yet a
real-time full EIS pipeline, and it is not pixel-equivalent to the CPU stabilized
output because CPU crop, dynamic zoom, Lanczos resize, and sharpen are not yet
reproduced on the device path.
```

Device matrix A/B result:

```text
old inverse:
  mean_abs_center_avg vs CPU = 44.739667

120-row aligned identity-first:
  mean_abs_center_avg vs CPU = 46.884302

120-row post-geometry:
  mean_abs_center_avg vs CPU = 30.688605

120-row post-geometry with first-frame identity:
  mean_abs_center_avg vs CPU = 30.241568

Catmull-Rom interpolation:
  mean_abs_center_avg vs CPU = 30.902334
  VPI warp avg at frame 100 = 2.980040 ms
```

For EIS-quality replay on Regular05, the current convention is `source_to_dest`.
It fixed the large black-border issue:

```text
Regular05 inverse convention:
  black_border_p95 = 0.281428602
  CPU-vs-device mean_abs_center_avg = 35.618840

Regular05 source_to_dest convention:
  black_border_p95 = 0.000972005
  CPU-vs-device mean_abs_center_avg = 4.512432
```

Catmull-Rom interpolation remains rejected because it was slower and worse than
linear on the outdoor-car smoke test.

## EGLImage Dataflow Breakdown

The accepted C++ EGLImage-wrapper path has now been decomposed beyond
"VPI warp time". Regular05 submit/sync probe, frame 100:

| Stage | Time |
|---|---:|
| input transform | 0.914 ms |
| EGL map | 0.080 ms |
| stream create | 0.465 ms |
| wrapper create | 3.289 ms |
| VPI submit | 0.019 ms |
| VPI sync | 1.513 ms |
| destroy | 0.527 ms |
| unmap | 0.046 ms |
| output transform | 0.943 ms |
| total | 7.798 ms |

Cost grouping:

```text
wrapper lifecycle: about 3.82 ms
submit + sync:     about 1.53 ms
input/output xform: about 1.86 ms
```

The first frame has a large initialization spike, about 245 ms in this probe.
With a three-iteration long run, wall time drops from about 12.69 ms/frame for a
single run to about 9.41 ms/frame. The spike can be amortized, but steady-state
dataflow still remains around 7.5-8.5 ms.

## NvBuffer Pair Follow-Up

Format-matched pitch-linear NV12_ER input/output scratch buffers can also be
wrapped with `VPI_IMAGE_BUFFER_NVBUFFER`. The important quality correction is
that the current comparison baseline is `resid_r15_s07`, not the older
`inclusion_source_to_dest` or `safe103_crop98` matrices.

Five Regular clips were run through NvBuffer pair with `resid_r15_s07`:

| Clip | rc | fallback | trans_mean | trans_p95 | black_p95 |
|---|---:|---:|---:|---:|---:|
| regular_gate01_regular_10 | 0 | 0 | 0.973 | 2.211 | 0.027436 |
| regular_gate02_regular_19 | 0 | 0 | 0.787 | 2.006 | 0.000422 |
| regular_gate03_regular_13 | 0 | 0 | 0.751 | 1.646 | 0.000343 |
| regular_gate04_regular_8 | 0 | 0 | 0.490 | 0.893 | 0.003435 |
| regular_gate05_regular_6 | 0 | 0 | 1.025 | 3.042 | 0.000000 |

Regular01 remains visual-conditional because the gray-threshold black-border
metric is sensitive to dark edges. The 5-clip review asset is:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260723_regular_gate_nvbuffer_pair_resid_r15_s07_5clip\20260723_regular_gate_nvbuffer_resid_r15_s07_5clip_overview_grid.mp4
```

Same-source Regular05 timing, `resid_r15_s07`:

| Metric | EGLImage | NvBuffer pair | Improvement |
|---|---:|---:|---:|
| VPI warp avg | 1.518510 ms | 1.491370 ms | 1.79% |
| stage frame100 | 7.535330 ms | 7.230350 ms | 4.05% |
| stage running avg | 9.588980 ms | 9.401090 ms | 1.96% |

Interpretation:

```text
NvBuffer pair preserves the accepted resid_r15_s07 quality anchor and gives a
small but measurable device-side dataflow-stage gain. It is not a zero-copy
full chain: block-linear main surfaces, pitch-linear scratch buffers,
NvBufSurfTransform, VPI wrapper creation, and sync costs still remain.
```

## Interview Wording

```text
I measured both where hardware acceleration fails and where it helps. In the
small Python EIS pipeline, a simple VPI backend swap was slower because
conversion, sync, and readback dominated. In a high-resolution PerspectiveWarp
module, VPI CUDA reached about 2.0x at 1080p and about 2.5x at 4K, and the 4K
workload improved FPS/W from 1.68 to 4.39. I then moved away from Python
appsink/appsrc and validated a C++ MMAPI/VPI/NVENC device-side path. The honest
claim is module-level VPI acceleration plus measured device dataflow boundaries,
not full real-time EIS or zero-copy.
```

## Evidence

```text
docs/vpi_warp_module_report_2026-07-18.md
docs/gstreamer_nvmm_latency_plan_2026-07-18.md
docs/device_matrix_warp_demo_2026-07-19.md
results/gst_nvmm_decode_convert_latency_20260718/summary.md
results/gst_nvmm_decode_convert_latency_20260718/appsink_summary.csv
results/gst_appsrc_encode_boundary_20260718/summary.md
results/perf_backend_compare_20260718/backend_compare_summary.md
results/vpi_resolution_scaling_benchmark/vpi_module_summary.md
results/gst_nvmm_probe_20260718_summary.md
results/device_matrix_warp_demo_20260719/triptych_cpu_vs_device/summary.md
results/vpi_warp_module_rerun_20260722/
results/vpi_warp_correctness_20260722/
results/power_probe_20260722_sudo/
results/regular05_submit_sync_probe_20260722/
results/regular05_submit_sync_longrun_20260722/
results/regular_gate_nvbuffer_pair_resid_20260723/
results/regular05_eglimage_timing_resid_compare_20260723/
```
