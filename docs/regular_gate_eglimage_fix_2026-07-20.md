# Regular Gate EGLImage Fix - 2026-07-20

## Decision

The C++ MMAPI/VPI/NVENC non-identity warp tearing has a validated replacement
candidate across all five Regular inclusion clips: replace the fragile CUDA
pitch-pointer wrapper with VPI's official EGLImage wrapper on pitch-linear
scratch NvBuffers.

The user accepted the five Regular EGLImage-wrapper review grids. This is now
the frozen C++ device-side path for Regular gate inclusion.

## What Changed

New patch script:

```text
scripts/patch_mmapi_vpi_transcode_eglimage_warp.py
```

New Jetson sample:

```text
/home/nvidia/orin-nx-project/_mmapi_work/jetson_multimedia_api/samples/99_vpi_transcode_matrix_eglimage
```

Old rejected path:

```text
NvBufSurface / EGL pitch pointer
-> manual CUDA pitch-linear VPI wrapper
-> VPI warp to cudaMallocPitch scratch
-> cudaMemcpy2D back to EGL pitch pointer
```

New candidate path:

```text
decoder DMABUF
-> NvBufSurfTransform to pitch-linear NV12_ER input scratch NvBuffer
-> VPI EGLImage wrapper(input scratch)
-> VPI EGLImage wrapper(output scratch)
-> VPI CUDA PerspectiveWarp
-> NvBufSurfTransform output scratch back to encoder DMABUF
-> NVENC
```

The important change is that VPI owns the EGLImage wrapping for both input and
output scratch surfaces. The code no longer registers the EGL image with CUDA
and manually reconstructs `VPI_IMAGE_BUFFER_CUDA_PITCH_LINEAR` from
`CUeglFrame` pitch pointers.

## Evidence

Remote evidence directory:

```text
/home/nvidia/orin-nx-project/results/regular_gate_eglimage_fix_20260720
```

Local evidence directory:

```text
results/regular_gate_eglimage_fix_20260720
```

Review copies:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_eglimage_fix\
```

Validated runs:

| Clip / matrix | Result | Notes |
|---|---|---|
| Regular01 translation10 | ran | non-identity minimal repro candidate |
| Regular01 scale110 | ran | non-identity minimal repro candidate |
| Regular01 inclusion | ran | actual inclusion matrix; gray black-border metric still follows the known Regular01 dark-edge caveat |
| Regular05 inclusion | ran | clean hard-gate sanity |
| Regular gate 5-clip inclusion batch | ran | all five clips completed with rc=0, fallback=0, frame-index mismatch=0 |

Five-clip batch summary:

| Clip | rc | fallback | mismatch | VPI avg ms | black p95 | frames > 1% |
|---|---:|---:|---:|---:|---:|---:|
| regular_gate01_regular_10 | 0 | 0 | 0 | 1.545450 | 0.013856771 | 10 |
| regular_gate02_regular_19 | 0 | 0 | 0 | 1.534620 | 0.000130859 | 0 |
| regular_gate03_regular_13 | 0 | 0 | 0 | 1.546050 | 0.000091363 | 0 |
| regular_gate04_regular_8 | 0 | 0 | 0 | 1.510270 | 0.000330078 | 0 |
| regular_gate05_regular_6 | 0 | 0 | 0 | 1.548090 | 0.000000000 | 0 |

Regular05 inclusion result:

```text
fallback_count: 0
frame_index_mismatch: none observed in MATRIX_HANDOFF samples
VPI_EGLIMAGE_WARP avg at frame 100: 1.52244 ms
black_border_p95: 0.000000000
black_border_max: 0.000008681
frames_gt_0p01: 0
```

Representative review assets:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_eglimage_fix\20260720_regular_gate_eglimage_fix_regular_gate01_translate10_source_bad_egl_grid.mp4
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_eglimage_fix\20260720_regular_gate_eglimage_fix_regular_gate01_scale110_source_bad_egl_grid.mp4
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_eglimage_fix\20260720_regular_gate_eglimage_fix_regular_gate01_inclusion_source_bad_egl_bgr8_grid.mp4
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_eglimage_fix\20260720_regular_gate_eglimage_fix_regular_gate05_inclusion_source_bad_egl_bgr8_grid.mp4
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_eglimage_fix\20260720_regular_gate_eglimage_fix_regular_gate01_regular_10_source_bad_egl_bgr8_grid.mp4
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_eglimage_fix\20260720_regular_gate_eglimage_fix_regular_gate02_regular_19_source_bad_egl_bgr8_grid.mp4
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_eglimage_fix\20260720_regular_gate_eglimage_fix_regular_gate03_regular_13_source_bad_egl_bgr8_grid.mp4
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_eglimage_fix\20260720_regular_gate_eglimage_fix_regular_gate04_regular_8_source_bad_egl_bgr8_grid.mp4
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_eglimage_fix\20260720_regular_gate_eglimage_fix_regular_gate05_regular_6_source_bad_egl_bgr8_grid.mp4
```

## Human Review

```text
2026-07-20: user accepted all five Regular EGLImage-wrapper review grids.
```

## Claim Boundary

Allowed:

```text
The rejected MMAPI EGL pitch-pointer path has a replacement C++ candidate using
official VPI EGLImage wrappers on pitch-linear NvBuffer scratch surfaces.
The candidate compiles and runs on Jetson.
All five Regular inclusion matrices ran through the EGLImage-wrapper path with
rc=0, fallback=0, and frame-index mismatch=0.
Four of five clips have clean gray-threshold black-border p95; Regular01 keeps
the known dark-edge gray-metric caveat and must be judged by visual review.
```

Forbidden:

```text
Full real-time EIS.
Zero-copy full chain.
VPI optical-flow acceleration.
CPU-output pixel equivalence.
```

## Next Step

Use this as the Regular gate C++ MMAPI/VPI/NVENC path and keep the Python BGR8
path as the correctness reference. The next engineering task is end-to-end
timing: separate matrix handoff, VPI warp, NvBufSurfTransform, encode, and wall
time under the same Regular gate semantics.
