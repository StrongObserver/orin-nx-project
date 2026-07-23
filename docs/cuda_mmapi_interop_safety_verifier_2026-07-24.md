# CUDA MMAPI Interop Safety Verifier - 2026-07-24

## Decision

The minimum CUDA/NvBufSurface/EGLImage scratch interop verifier passed.

This closes the narrow safety question after the standalone CUDA dynamic warp
probe: CUDA can read/write the pitch-linear NV12_ER scratch stage through
EGLImage interop in the MMAPI transcode sample without immediate unreadable
output, green output, or obvious identity-path black-border regression.

Boundary:

```text
This is a safety/dataflow verifier only. It is not EIS quality improvement, not
zero-copy, not full real-time EIS, and not accepted MMAPI CUDA acceleration.
```

## Scope

Tracked patch script:

```text
scripts/patch_mmapi_cuda_interop_safety_verifier.py
```

Jetson sample copy used:

```text
/home/nvidia/orin-nx-project/_mmapi_work/jetson_multimedia_api/samples/99_vpi_transcode_cuda_interop_safety_verifier_20260724_02
```

Input:

```text
/home/nvidia/orin-nx-project/results/regular_gate_safe103_crop98_validation_20260720/regular_gate05_regular_6/source.h264
```

Evidence:

```text
results/cuda_mmapi_interop_safety_verifier_20260724/
C:\Users\Admin\Videos\orin nx\review\diagnostic\20260724_cuda_mmapi_interop_safety_verifier\20260724_cuda_mmapi_interop_regular05_jetson_identity_shift_dynamic_grid.mp4
```

## What Was Verified

The patch keeps the existing device-stage boundary:

```text
block-linear NV12 main chain
-> NvBufSurfTransform to pitch-linear NV12_ER scratch
-> CUDA EGLImage interop diagnostic
-> NvBufSurfTransform back to block-linear NV12
-> NVENC
```

Modes:

```text
identity: copy input scratch to output scratch
shift_dx8: shift the scratch content by 8 pixels with zero fill
dynamic_shift: per-frame dx/dy shift with zero fill
```

Identity is the safety gate. Shift modes only prove non-identity CUDA writes are
active; their black border is expected zero-fill behavior and is not a quality
candidate.

## Results

All three runs returned `rc=0`, produced readable 640x360 H264 output, and
completed 180 frames.

| Mode | rc | Frame100 CUDA elapsed | Frame100 process | Frame100 total stage | Avg total stage | Black-border p95 | Decision |
|---|---:|---:|---:|---:|---:|---:|---|
| identity | 0 | 1.353660 ms | 0.844692 ms | 3.354930 ms | 4.095380 ms | 0.000000000 | Primary safety gate passed |
| shift_dx8 | 0 | 1.452710 ms | 0.836533 ms | 3.432850 ms | 4.096300 ms | 0.191930556 | Non-identity write path active; high black border expected |
| dynamic_shift | 0 | 1.290720 ms | 0.841781 ms | 3.210320 ms | 4.445920 ms | 0.237383898 | Per-frame CUDA write parameters active; high black border expected |

The first-frame stage has initialization spikes, so frame100 and average values
should be read as diagnostic timing rather than a final performance claim.

## Interpretation

What this proves:

```text
CUDA driver API EGL interop can register the scratch EGLImages, map them as
CUeglFrame pitch frames, perform device-to-device NV12 plane copy/shift, sync,
unregister resources, transform back to the main chain, and encode readable
output.
```

What this does not prove:

```text
It does not prove custom CUDA warp kernel quality.
It does not prove full MMAPI CUDA acceleration.
It does not prove zero-copy.
It does not prove a full real-time EIS pipeline.
It does not improve Regular EIS quality.
```

## Next Contract Boundary

If this route continues, the next contract should be separate and narrower than
"make CUDA the pipeline":

```text
CUDA affine kernel MMAPI diagnostic:
  identity kernel
  translate kernel
  dynamic affine kernel
  same input, same scratch format, same readability and black-border checks
```

Only after that would it be valid to compare stage timing against VPI Remap
dynamic payload rebuild or PerspectiveWarp stage timing. Even then, the claim
would remain device-stage/operator evidence unless end-to-end same-input EIS
semantics are measured.
