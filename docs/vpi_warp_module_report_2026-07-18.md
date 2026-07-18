# VPI Warp Module Report - 2026-07-18

## Purpose

This report explains where VPI CUDA helps in the Orin NX EIS project and where it
does not.

It separates two claims:

```text
full Regular05 Python EIS pipeline:
  VPI backend swap is slower than OpenCV CPU.

high-resolution warp-heavy module:
  VPI CUDA is faster than OpenCV CPU and scales better with resolution.
```

## Full-Pipeline Boundary

Same-input `regular_gate05_regular_6` backend comparison:

| Backend | avg_warp_ms | total_wall_time_s | Result |
|---|---:|---:|---|
| opencv_cpu | 7.936 | 8.473 | current best |
| vpi_cuda | 9.621 | 9.382 | slower |
| vpi_cpu | 11.934 | 9.640 | slower |
| vpi_vic | 14.531 | 10.132 | slower |

Reasonable explanation:

```text
At 640x360, the VPI call is too small to amortize BGR/NV12 conversion,
synchronization, and CPU readback overhead inside the current Python pipeline.
```

## Module-Level VPI Value

High-resolution warp-heavy benchmark:

| Resolution | OpenCV CPU ms | VPI CUDA ms | Speedup |
|---|---:|---:|---:|
| 1280x720 | 6.118 | 4.523 | 1.35x |
| 1920x1080 | 13.569 | 7.398 | 1.83x |
| 2560x1440 | 22.920 | 10.651 | 2.15x |
| 3840x2160 | 48.452 | 20.836 | 2.33x |

Interpretation:

```text
VPI CUDA becomes useful when the warp workload is large enough. The speedup grows
from 1.35x at 720p to 2.33x at 4K.
```

## Correct Interview Wording

```text
I did not claim VPI accelerated the whole stabilizer. I measured both the
full-pipeline path and a high-resolution module path. The full pipeline was
slower with a simple VPI backend swap, but the high-resolution warp module showed
clear CUDA scaling. That tells me the real optimization problem is dataflow and
operator placement, not just replacing one API call.
```

## Claims To Avoid

```text
VPI accelerated the full EIS pipeline.
VPI is always faster than OpenCV.
The 4K module benchmark proves the Regular baseline is accelerated.
```

## Evidence

```text
results/perf_backend_compare_20260718/backend_compare_summary.md
results/vpi_resolution_scaling_benchmark/summary.csv
results/vpi_resolution_scaling_benchmark/vpi_module_summary.md
```

## Next Step

Connect this module result to the GStreamer/NVMM latency plan only after the
dataflow boundary is measured. Do not merge VPI into the Regular performance
baseline unless a same-input full-pipeline speedup is measured.
