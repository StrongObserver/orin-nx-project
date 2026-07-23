# VPI C++ Remap Probe - 2026-07-23

## Decision

The C++ route changes the Remap boundary:

```text
Python VPI Image.remap:
  native aborts with double free / corruption on this setup

C++ VPI Remap:
  CPU and CUDA backends run successfully
  CUDA is faster than OpenCV CPU on tested identity and local-wave maps
  NV12_ER input/output also works on CPU and CUDA
```

This is useful Orin NX heterogeneous-video-compute evidence. It is still a
module/operator result, not full EIS pipeline acceleration and not mesh/local EIS
quality.

## Why This Was Worth Doing

The earlier Python probe failed for every backend:

```text
results/vpi_remap_minimal_probe_20260722/summary.md
```

The failure was a Python binding/native path abort:

```text
double free or corruption (out)
```

That did not prove that VPI Remap itself was impossible. NVIDIA's C++ sample and
headers show the supported API path:

```text
/opt/nvidia/vpi2/samples/11-fisheye/main.cpp
/opt/nvidia/vpi2/include/vpi/WarpMap.h
/opt/nvidia/vpi2/include/vpi/algo/Remap.h
```

Important API facts:

```text
vpiWarpMapAllocData
vpiWarpMapGenerateIdentity
vpiCreateRemap
vpiSubmitRemap
supported backends: CPU / CUDA / VIC
supported formats include BGR8, NV12, and NV12_ER on CPU/CUDA
```

## Probe

Tracked probe source:

```text
experiments/vpi_cpp_remap_probe/remap_probe.cpp
```

Remote build command used on Jetson:

```bash
cd /home/nvidia/orin-nx-project/experiments/vpi_cpp_remap_probe
g++ -std=c++17 remap_probe.cpp -o remap_probe \
  -I/opt/nvidia/vpi2/include \
  -L/opt/nvidia/vpi2/lib/aarch64-linux-gnu -lnvvpi \
  $(pkg-config --cflags --libs opencv4)
```

The probe builds a synthetic BGR image, constructs a `VPIWarpMap`, and can run:

```text
identity map
horizontal shift map
local wave map
pinch map
```

The C++ probe avoids the Python binding path entirely.

## Backend Sanity

Minimal 640x368 BGR8 identity run:

| Backend | Status | Avg remap ms | Notes |
|---|---|---:|---|
| VPI CPU | pass | 0.988688 | C++ Remap works |
| VPI CUDA | pass | 0.610031 | C++ Remap works |
| VPI VIC | fail | n/a | `BGR8` unsupported by VIC |

Interpretation:

```text
CPU/CUDA Remap is available. VIC needs a VIC-supported format path; BGR8 is not
the right input for VIC.
```

## OpenCV vs VPI C++ Remap Benchmark

Evidence:

```text
results/vpi_remap_cpp_probe_20260723/benchmark/
```

| Mode | Resolution | OpenCV CPU ms | VPI CPU ms | VPI CUDA ms | CUDA speedup vs OpenCV |
|---|---:|---:|---:|---:|---:|
| identity | 640x368 | 1.817510 | 0.988688 | 0.610031 | 2.979x |
| identity | 1920x1088 | 8.096360 | 7.988430 | 2.410080 | 3.359x |
| identity | 3840x2160 | 31.127200 | 31.452200 | 9.423580 | 3.303x |
| wave | 640x368 | 1.772240 | 0.975930 | 0.704285 | 2.516x |
| wave | 1920x1088 | 8.105170 | 7.968380 | 2.978840 | 2.721x |
| wave | 3840x2160 | 31.064200 | 32.921700 | 9.516820 | 3.264x |

Interpretation:

```text
VPI CUDA Remap is a positive module-level acceleration result on this Jetson.
The local-wave map proves the path is not limited to identity remap.
```

## NV12_ER / MMAPI Relevance

Evidence:

```text
results/vpi_remap_cpp_probe_20260723/nv12_er/
```

| Mode | Format | VPI CPU ms | VPI CUDA ms | VIC |
|---|---|---:|---:|---|
| identity | NV12_ER | 0.753977 | 0.213389 | pre-convert failed in this probe |
| wave | NV12_ER | 0.760223 | 0.135011 | pre-convert failed in this probe |

Interpretation:

```text
CPU/CUDA Remap can run on NV12_ER, which matches the current VPI scratch format
used by the accepted MMAPI/VPI/NVENC device path.
```

VIC failed in this probe because the probe tried to convert a BGR8 OpenCV image
to NV12_ER using VIC, which is not supported. That is a probe-format issue, not
proof that VIC Remap can never work with a native NV12/NV12_ER input.

## Review Evidence

Small diagnostic review copies:

```text
C:\Users\Admin\Videos\orin nx\review\diagnostic\20260723_vpi_remap_cpp_probe\
```

Files:

```text
20260723_vpi_remap_cpp_probe_640x368_opencv_wave.png
20260723_vpi_remap_cpp_probe_640x368_vpi_cuda_wave.png
```

These are operator-demo images, not EIS quality assets.

## MMAPI Integration Boundary

Current accepted device path:

```text
block-linear NV12 main chain
-> NvBufSurfTransform to pitch-linear NV12_ER scratch
-> VPI CUDA PerspectiveWarp
-> NvBufSurfTransform back to block-linear NV12
-> NVENC
```

Remap integration is plausible because CPU/CUDA Remap accepts NV12_ER. The next
integration step, if opened later, should be a scoped contract:

```text
replace PerspectiveWarp with Remap on pitch-linear NV12_ER scratch
use the same source/matrix or a clearly diagnostic map
verify output readability and black-border behavior
do not change EIS quality semantics
```

Do not directly jump to product mesh EIS.

## Claim Boundary

Allowed:

```text
VPI C++ Remap works on CPU/CUDA on this Jetson.
VPI CUDA Remap is faster than OpenCV CPU remap in the tested module benchmark.
VPI C++ Remap can run on NV12_ER, so it is a plausible future device-stage
scratch-buffer operator.
```

Forbidden:

```text
Python Remap works.
VIC Remap is validated for this pipeline.
Remap accelerates the full EIS pipeline.
Mesh/local-warp EIS quality is solved.
MMAPI integration is complete.
```
