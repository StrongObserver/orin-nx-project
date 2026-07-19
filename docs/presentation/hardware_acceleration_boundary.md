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

High-resolution warp-heavy benchmark:

![VPI resolution scaling](assets/vpi_resolution_scaling.svg)

| Resolution | OpenCV CPU ms | VPI CUDA ms | Speedup |
|---|---:|---:|---:|
| 1280x720 | 6.118 | 4.523 | 1.35x |
| 1920x1080 | 13.569 | 7.398 | 1.83x |
| 2560x1440 | 22.920 | 10.651 | 2.15x |
| 3840x2160 | 48.452 | 20.836 | 2.33x |

Conclusion:

```text
VPI CUDA helps when the warp workload is large enough to amortize conversion and
readback costs.
```

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

## Interview Wording

```text
I measured both where hardware acceleration fails and where it starts to help.
In the small Python EIS pipeline, VPI was slower because conversion and
synchronization dominated. In a high-resolution warp module, VPI CUDA scaled well
and reached 2.33x at 4K. I then moved away from Python appsink/appsrc and
validated a C++ MMAPI/VPI/NVENC device-side warp path. The outdoor-car tests
were dataflow smoke. On the real Regular05 EIS clip, source_to_dest matrix
convention fixed the device replay black-border problem. The honest claim is
device-side warp/encode readiness plus Regular05 replay correctness, not full
real-time EIS.
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
```
