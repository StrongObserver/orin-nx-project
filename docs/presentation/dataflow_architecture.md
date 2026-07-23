# Dataflow Architecture

## Project Shape

The current project is organized as:

```text
EIS representative workload
-> Regular / Challenge quality boundary
-> CPU baseline and matrix generation
-> VPI module acceleration evidence
-> C++ MMAPI/VPI/NVENC device-side stage
-> Nsight/NVTX bottleneck attribution
```

EIS is the workload used to make quality and matrix semantics concrete. The
resume-facing claim is heterogeneous video compute and device-side dataflow
optimization on Jetson Orin NX.

## Quality And Matrix Layer

```text
NUS Regular clips
-> CPU/OpenCV EIS pipeline
-> quality-safe or performance baseline
-> device-ready source_to_dest matrices
-> accepted quality anchor: resid_r15_s07
```

Current boundaries:

| Item | Current State |
|---|---|
| Main quality gate | `nus_regular_gate_v1` |
| Challenge / diagnostic sets | Running, QuickRotation, Parallax, Crowd |
| Performance baseline | `lp_rigid_strength080_dynzoom106`, `estimate_scale=0.5`, `feature_grid_size=16` |
| Stabilization-strength anchor | `resid_r15_s07` |
| Regular matrix convention | `source_to_dest` |

Outdoor-car inverse/post-geometry results are historical dataflow smoke only.
They must not be reused as Regular05 EIS-quality evidence.

## Accepted C++ Device Path

The accepted C++ consumer path is:

```text
H264 input
-> MMAPI/NVDEC decode
-> block-linear NV12 main NvBufSurface
-> NvBufSurfTransform to pitch-linear NV12_ER scratch
-> VPI CUDA PerspectiveWarp
-> NvBufSurfTransform back to block-linear NV12 main chain
-> NVENC encode
-> H264 output
```

This path is accepted because it avoids the rejected pitch-pointer wrapper route
that caused visible block tearing under non-identity matrices.

## Memory Format Boundary

| Surface / Buffer | Layout | Role |
|---|---|---|
| Main decode / encode surface | block-linear NV12 | Required for the MMAPI/NVENC main chain |
| VPI scratch surface | pitch-linear NV12_ER | Required for the current VPI PerspectiveWarp path |
| EGLImage wrapper path | per-frame VPI image wrappers | Accepted but wrapper lifecycle is costly |
| Stream-only reuse | reuse VPI stream, recreate image wrappers | Small accepted lifecycle optimization |
| Format-matched NvBuffer pair | pitch-linear NV12_ER input/output pair | Small dataflow alternative; not zero-copy |

Rejected routes:

```text
pitch-linear main encoder chain -> near-solid green output
block-linear VPI scratch pair -> rejected by VPI PerspectiveWarp support
direct mismatched NvBuffer input -> format mismatch failure
EGLImage image-wrapper reuse -> tearing or runtime failures
old pitch-pointer wrapper -> non-identity matrix tearing
```

## Profiling Interpretation

The most important profiling result is that the project should not optimize the
wrong stage.

```text
VPI submit call: about 0.02 ms
VPI PerspectiveWarp range: about 0.76-0.81 ms under Nsight
wrap + submit + sync: about 10 ms under Nsight
transform sandwich: about 0.87-0.97 ms each direction under Nsight
```

Practical meaning:

```text
The PerspectiveWarp kernel is not the main bottleneck.
The remaining cost is host/device dataflow: wrapper lifecycle, CUDA/EGL resource
registration/free, stream sync, and NvBufSurfTransform.
```

## NvBuffer Pair Position

NvBuffer pair is useful, but its claim is narrow:

```text
same source
same resid_r15_s07 matrix
same crop/postprocess boundary
same output readability
small stage timing gain
```

It is not a zero-copy chain. It still keeps the block-linear main chain,
pitch-linear scratch buffers, transforms, VPI wrappers, and sync.

## Stream-Only Reuse Position

Stream-only reuse is now the safest promoted lifecycle optimization:

```text
reuse VPI stream
recreate EGLImage image wrappers per frame
keep source, matrix, crop/postprocess, and output semantics unchanged
```

Same-source Regular05 repeat:

```text
accepted EGLImage wall mean: 1.946819 s
stream-only reuse wall mean: 1.843571 s
stage running avg: 10.336381 ms -> 9.680414 ms
wrapper mean: 5.877429 ms -> 5.365920 ms
```

Boundary:

```text
This is not EGLImage image-wrapper reuse. That route remains rejected because it
caused tearing or runtime failures. Stream-only reuse is a small lifecycle win,
not zero-copy and not a broad scheduler rewrite.
```

## Interview Diagram Text

Use this in slides or a whiteboard:

```text
Quality semantics:
  Regular gate -> CPU EIS -> resid_r15_s07 source_to_dest matrices

Device execution:
  H264 -> MMAPI decode -> block-linear NV12
       -> transform to pitch-linear NV12_ER
       -> VPI CUDA warp
       -> transform back to block-linear NV12
       -> NVENC

Measured bottleneck:
  not vpiSubmit, not only PerspectiveWarp
  wrapper / sync / transform / lifecycle dominate

Optimization result:
  VPI CUDA gives module-level high-res warp speed and FPS/W gains
  NvBuffer pair gives small quality-preserving device-stage gain
```

## Next-Route Policy

The current stage is sealed for presentation. If future engineering is requested,
the next route should be a new scoped contract, not an open-ended loop.

Reasonable future contracts:

```text
wrapper/register/free/sync lifecycle A/B under the same source and matrix
VPI Remap C++ official-sample probe
longer fixed-mode perf/watt run
presentation diagram refresh
```

Routes that should stay closed unless the user changes the objective:

```text
global affine/rigid quality sweeps
lim/R/LP/safe103/inclusion tuning
VPI optical-flow acceleration claims
mesh/grid warp route
broad C++ MMAPI rewrite
zero-copy claim work without a format-stable verifier
```
