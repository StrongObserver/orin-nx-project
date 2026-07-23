# CUDA MMAPI Interop Safety Verifier - 2026-07-24

## Decision

The corrected CUDA/NvSurface/EGLImage scratch interop verifier passed for
identity and small-marker diagnostics.

This closes the narrow safety question after the standalone CUDA dynamic warp
probe: CUDA can read/write the pitch-linear NV12_ER scratch stage through
EGLImage interop in the MMAPI transcode sample without immediate unreadable
output, green output, or identity-path black-border regression.

Important correction: the first attempt used `shift_dx8` and `dynamic_shift` to
move large NV12 planes with zero fill. Human review of the generated grid video
showed severe tearing/distortion. Those large-plane shift modes are rejected
diagnostics and are not evidence that non-identity CUDA warp is safe.

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
/home/nvidia/orin-nx-project/_mmapi_work/jetson_multimedia_api/samples/99_vpi_transcode_cuda_interop_safety_verifier_20260724_fix01
```

Input:

```text
/home/nvidia/orin-nx-project/results/regular_gate_safe103_crop98_validation_20260720/regular_gate05_regular_6/source.h264
```

Evidence:

```text
results/cuda_mmapi_interop_safety_verifier_20260724_fix01/
C:\Users\Admin\Videos\orin nx\review\diagnostic\20260724_cuda_mmapi_interop_safety_verifier\20260724_cuda_mmapi_interop_regular05_jetson_identity_marker_dynamicmarker_grid_fix01.mp4
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
marker: copy full frame, then write a small static Y-plane marker
dynamic_marker: copy full frame, then write a small moving Y-plane marker
```

Identity is the safety gate. Marker modes prove CUDA write activity while
keeping the frame structure intact. Large-plane shift modes are rejected because
they caused visible tearing/distortion despite `rc=0`.

## Results

The corrected three runs returned `rc=0`, produced readable 640x360 H264 output,
and completed 180 frames.

| Mode | rc | Frame100 CUDA elapsed | Frame100 process | Frame100 total stage | Avg total stage | Black-border p95 | Decision |
|---|---:|---:|---:|---:|---:|---:|---|
| identity | 0 | 1.700850 ms | 0.833623 ms | 3.967790 ms | 4.525640 ms | 0.000000000 | Primary safety gate passed |
| marker | 0 | 1.400010 ms | 0.828183 ms | 3.400640 ms | 4.305430 ms | 0.000000000 | Small ROI CUDA write activity passed |
| dynamic_marker | 0 | 1.547280 ms | 0.899545 ms | 3.516580 ms | 4.122590 ms | 0.000000000 | Per-frame small ROI CUDA write activity passed |

The first-frame stage has initialization spikes, so frame100 and average values
should be read as diagnostic timing rather than a final performance claim.

Rejected first attempt:

| Mode | rc | Black-border p95 | Visual decision |
|---|---:|---:|---|
| shift_dx8 | 0 | 0.191930556 | rejected, severe tearing/distortion |
| dynamic_shift | 0 | 0.237383898 | rejected, severe tearing/distortion |

## Interpretation

What this proves:

```text
CUDA driver API EGL interop can register the scratch EGLImages, map them as
CUeglFrame pitch frames, perform full-frame NV12 device-to-device copy plus
small Y-plane marker writes, sync, unregister resources, transform back to the
main chain, and encode readable output.
```

What this does not prove:

```text
It does not prove custom CUDA warp kernel quality.
It does not prove full MMAPI CUDA acceleration.
It does not prove zero-copy.
It does not prove a full real-time EIS pipeline.
It does not improve Regular EIS quality.
It does not prove that large-plane CUDA shifting or affine warp is safe.
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
