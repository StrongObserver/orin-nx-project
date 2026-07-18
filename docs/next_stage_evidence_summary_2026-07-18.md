# Next-Stage Evidence Summary - 2026-07-18

## Summary Decision

The next-stage evidence loop produced three useful conclusions:

```text
VPI module line:
  Keep as high-resolution module acceleration evidence.

Challenge boundary line:
  Keep as model-boundary / operating-envelope evidence.

GStreamer/NVMM line:
  Keep as dataflow boundary evidence; do not integrate into EIS yet.
```

## VPI Module Line

Existing scaling data remains the core evidence:

| Resolution | OpenCV CPU ms | VPI CUDA ms | Speedup |
|---|---:|---:|---:|
| 1280x720 | 6.118 | 4.523 | 1.35x |
| 1920x1080 | 13.569 | 7.398 | 1.83x |
| 2560x1440 | 22.920 | 10.651 | 2.15x |
| 3840x2160 | 48.452 | 20.836 | 2.33x |

Correctness sanity check on encoded benchmark outputs:

| Region | Mean abs diff | Avg p95 abs diff | Max abs diff |
|---|---:|---:|---:|
| Full frame | 16.817 | 82.326 | 255 |
| Center crop | 9.153 | 34.481 | 182 |

Decision:

```text
Use this as module-level acceleration evidence only. The output-difference check
is not strict pixel equivalence because the existing outputs include encoding,
format conversion, and border-mode differences.
```

## Challenge Boundary Line

Challenge result:

| Category | Result | Boundary label |
|---|---|---|
| Running | 1 pass, 1 black-border hard fail | boundary |
| QuickRotation | 2 black-border hard fails | fail / boundary |
| Parallax | 2 black-border hard fails | fail / boundary |
| Crowd | 2 black-border hard fails | diagnostic boundary |

Decision:

```text
Use this as operating-envelope evidence. Regular is the in-domain success gate;
challenge sets expose global-warp model limits and must not be merged into the
headline pass rate.
```

## GStreamer / NVMM Line

Measured dataflow anchors:

| Case | EOS | Wall time |
|---|---|---:|
| decode/NVMM/convert/fakesink, avg of 3 | 3/3 | 1.931 s |
| hardware encode path | 1/1 | 1.299 s |
| CPU-readable boundary | 1/1 | 1.960 s |

Decision:

```text
The Jetson dataflow path is available and measurable. Do not integrate into
cpu_stabilize.py yet. The next useful step would be an appsink/appsrc boundary
with frame counting.
```

## Next Execution Choice

Recommended next loop:

```text
Challenge-set boundary packaging and presentation polish.
```

Reason:

```text
It turns an already measured result into a strong engineering story with low
implementation risk.
```

Secondary next loop:

```text
GStreamer appsink/appsrc boundary measurement.
```

Defer:

```text
Mesh/grid warp implementation.
Full EIS GStreamer integration.
```

## Evidence

```text
docs/vpi_warp_module_report_2026-07-18.md
docs/challenge_boundary_report_2026-07-18.md
results/gst_nvmm_decode_convert_latency_20260718/summary.md
results/challenge_boundary_package_20260718/eval/challenge_boundary_eval.csv
```
