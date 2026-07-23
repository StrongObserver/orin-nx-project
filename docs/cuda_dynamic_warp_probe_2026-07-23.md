# CUDA Dynamic Warp Probe - 2026-07-23

## Decision

Standalone CUDA dynamic warp is a strong execution candidate for future
per-frame dynamic warp work, but MMAPI integration should not be opened yet.

Benefits:

```text
1. CUDA dynamic affine warp is much faster than VPI dynamic Remap payload rebuild
   in the standalone 640x368 diagnostic.

2. The Y-plane kernel is closer to NV12/NV12_ER scratch semantics and is also
   much faster than the measured VPI NV12_ER dynamic Remap path.

3. Identity output is exact after fixing border sampling, so the kernel has a
   clean correctness baseline.
```

Boundary:

```text
This is standalone CUDA operator evidence. It is not MMAPI integration, not
zero-copy, not full real-time EIS, and not an EIS quality improvement claim.
```

## Context

The previous dynamic Remap loop showed that VPI Remap can run dynamic per-frame
maps, but the local VPI C API route requires rebuilding Remap payloads:

```text
standalone NV12_ER dynamic Remap: 2.913010 ms/frame
MMAPI dynamic Remap stage avg: about 13.1 ms/frame
```

This loop asks whether a custom CUDA kernel can update per-frame transform
parameters without rebuilding a VPI Remap payload.

## Standalone CUDA Result

Tracked source:

```text
experiments/cuda_dynamic_warp_probe/cuda_dynamic_warp_probe.cu
```

Evidence:

```text
results/cuda_dynamic_warp_probe_20260723/
```

640x368, 180 frames:

| Format | Mode | Matrix Update Avg | Kernel Avg | Total Avg | Mean Abs vs OpenCV | Max Abs |
|---|---|---:|---:|---:|---:|---:|
| RGBA | identity | 0.009335 ms | 0.176908 ms | 0.197498 ms | 0.000000 | 0 |
| RGBA | static_affine | 0.007325 ms | 0.063892 ms | 0.080645 ms | 0.242490 | 255 |
| RGBA | dynamic_affine | 0.009759 ms | 0.172509 ms | 0.194142 ms | 0.261900 | 255 |
| Y8 | identity | 0.009147 ms | 0.120000 ms | 0.140242 ms | 0.000000 | 0 |
| Y8 | static_affine | 0.005203 ms | 0.090537 ms | 0.116469 ms | 0.096818 | 224 |
| Y8 | dynamic_affine | 0.009215 ms | 0.117309 ms | 0.138282 ms | 0.103431 | 233 |

The non-zero `max_abs` values for affine modes are concentrated around border and
interpolation differences. Identity is exact.

## CUDA vs VPI Dynamic Remap

Same resolution and frame count:

| Route | Comparable Mode | Total Avg |
|---|---|---:|
| CUDA RGBA dynamic affine | dynamic matrix update + kernel | 0.194142 ms |
| VPI BGR8 dynamic Remap | per-frame WarpMap/payload rebuild | 2.250150 ms |
| CUDA Y8 dynamic affine | dynamic matrix update + kernel | 0.138282 ms |
| VPI NV12_ER dynamic Remap | per-frame WarpMap/payload rebuild | 2.913010 ms |

Interpretation:

```text
For this simplified affine dynamic-warp diagnostic, CUDA avoids the VPI Remap
payload rebuild path and is an order of magnitude faster at 640x368.
```

This does not mean CUDA is automatically the final MMAPI path. It means CUDA is
a worthwhile execution route to evaluate before paying the cost of a real
dynamic mesh/local-warp pipeline.

## MMAPI Decision

The MMAPI CUDA branch was not opened in this loop.

Reason:

```text
The project already has evidence that unsafe low-level CUDA/pitch-wrapper
routes can produce non-identity tearing. A standalone CUDA win is not enough to
accept direct MMAPI scratch writeback without a separate NvBufSurface/EGLImage
interop safety verifier.
```

Next safe route:

```text
Create a separate contract for CUDA/NvBufSurface/EGLImage scratch interop:
identity first, then translate, then dynamic matrix. Stop immediately on tearing,
green output, cache/sync ambiguity, or unreadable output.
```

## Review Evidence

Review copy:

```text
C:\Users\Admin\Videos\orin nx\review\diagnostic\20260723_cuda_dynamic_warp_probe\20260723_cuda_dynamic_warp_standalone_grid.jpg
```

Panel role:

```text
RGBA source / OpenCV reference / CUDA output / absdiff
Y8 OpenCV reference / Y8 CUDA output
```

## Claim Boundary

Allowed:

```text
Standalone CUDA dynamic warp avoids the VPI Remap per-frame payload rebuild cost
in this affine diagnostic, and is a promising execution route for future dynamic
mesh/local-warp exploration.
```

Not allowed:

```text
CUDA warp is integrated into MMAPI.
CUDA warp improves EIS quality.
CUDA warp is zero-copy.
CUDA warp proves full real-time EIS.
```
