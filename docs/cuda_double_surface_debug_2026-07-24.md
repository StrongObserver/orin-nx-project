# CUDA Double-Surface Debug - 2026-07-24

## Decision

The internal-AI Test0-Test2 debug route isolated the CUDA/MMAPI corruption
boundary.

Passed:

```text
Test0: VIC round-trip
Test1: dual-surface CUDA full-frame copy with separate Y/UV kernels
```

Failed:

```text
Test2: dual-surface integer translate
```

Interpretation:

```text
The basic BL -> pitch-linear scratch -> BL round-trip is usable.
Full-frame CUDA copy over the EGL-mapped pitch-linear NV12_ER scratch is clean.
Spatial random sampling / remap over that current EGL scratch path still tears.
```

This closes the current route as negative evidence. It does not prove CUDA warp
acceleration, zero-copy, full real-time EIS, or EIS quality improvement.

## Scope

Contract:

```text
configs/harness/contracts/cuda_double_surface_debug_v1.json
```

Patch script:

```text
scripts/patch_mmapi_cuda_double_surface_debug.py
```

Input:

```text
/home/nvidia/orin-nx-project/results/regular_gate_safe103_crop98_validation_20260720/regular_gate05_regular_6/source.h264
```

Evidence:

```text
results/cuda_double_surface_debug_20260724/
```

## Results

| Test | Mode | rc | Visual | Black-border p95 | Diff / timing | Decision |
|---|---|---:|---|---:|---|---|
| Test0 | VIC round-trip | 0 | readable, no tearing | 0.024495226 | mean_abs_center_avg 14.597394 | pass as baseline round-trip sanity |
| Test1 | CUDA full-frame copy | 0 | readable, no tearing | 0.000000000 | mean_abs_center_avg 2.805186; frame100 CUDA elapsed 3.183370 ms; stage 5.490170 ms | pass |
| Test2 | CUDA integer translate | 0 | severe tearing/distortion | 0.024389757 | frame100 CUDA elapsed 1.757750 ms; stage 4.034090 ms | reject |

Test0 has visible codec/color/edge drift relative to source but no tearing. Test1
is much closer to source than Test0, which proves the dual-surface full-frame
CUDA copy path is clean. Test2 still tears, so the remaining issue is not the
basic decode/encode path or full-frame copy.

## Root Cause Boundary

What is now supported by evidence:

```text
safe:
  identity copy
  marker writes
  dynamic marker writes
  dual-surface full-frame CUDA copy

unsafe in current route:
  large-plane shift
  integer translate
  affine/random-sampling warp
```

Most likely boundary:

```text
spatial random sampling / remap over the current EGL-mapped pitch-linear NV12_ER
scratch path is not a valid MMAPI/NVENC warp integration route as currently
implemented.
```

This is narrower than saying CUDA is impossible. It says this specific surface
ownership and EGL-mapped random-write route is not accepted.

## Next Route

Do not keep patching the current EGL scratch random-sampling path. A useful next
contract must change the memory/surface model:

```text
1. CUDA-owned intermediate surface with an official/documented copy or transform
   back to encoder-compatible NvBufSurface.
2. VPI PerspectiveWarp/Remap for device-stage warp, because VPI owns the surface
   wrapper and synchronization model.
3. GStreamer NVMM + CUDA plugin route if the goal shifts toward product-style
   streaming pipeline integration.
```

The most conservative next engineering step is not more affine patching. It is
either a CUDA-owned intermediate-surface contract or a VPI-based warp contract
with the current evidence as the reason.
