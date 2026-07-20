# Regular Gate EGLImage Timing - 2026-07-20

## Decision

The accepted C++ EGLImage-wrapper path has a first Regular05 timing breakdown.
The main finding is that VPI CUDA PerspectiveWarp itself is not the bottleneck;
the larger cost is the device-side scratch-buffer stage around it.

This is still a stage-level timing result. It should not be described as full
real-time EIS because online motion estimation and full live producer scheduling
are not included here.

## Input

```text
clip: regular_gate05_regular_6
matrix: inclusion_source_to_dest.csv
path: C++ MMAPI/VPI/NVENC EGLImage-wrapper sample
sample: /home/nvidia/orin-nx-project/_mmapi_work/jetson_multimedia_api/samples/99_vpi_transcode_matrix_eglimage_timing
```

## Evidence

Remote evidence:

```text
/home/nvidia/orin-nx-project/results/regular_gate_eglimage_timing_20260720
```

Local evidence:

```text
results/regular_gate_eglimage_timing_20260720
```

## Timing

| Layer | Metric | Result |
|---|---|---:|
| Full command wall time | 180-frame transcode run | 2002 ms |
| Matrix handoff | avg sampled elapsed | 1.099636 us |
| Matrix handoff | fallback / mismatch | 0 / 0 |
| VPI warp only | running avg at frame 100 | 1.554940 ms |
| EGLImage device stage | running avg total at frame 100 | 10.504100 ms |
| EGLImage device stage | frame-100 input transform | 0.910515 ms |
| EGLImage device stage | frame-100 wrapper+warp call | 6.437180 ms |
| EGLImage device stage | frame-100 output transform | 0.954736 ms |

Quality sanity:

```text
black_border_p95: 0.000000000
black_border_max: 0.000008681
frames_gt_0p01: 0
```

## Interpretation

The C++ path is much healthier than Python readback for the warp stage, but the
stage cost is not just the VPI kernel. The measured `VPI_EGLIMAGE_WARP` internal
running average is about 1.55 ms, while the larger EGLImage stage including
scratch transforms and wrapper call averages about 10.5 ms. The next optimization
question is therefore the memory/dataflow around the warp, not the warp kernel
alone.

## Claim Boundary

Allowed:

```text
The accepted C++ EGLImage-wrapper path has a Regular05 stage timing breakdown.
VPI warp-only timing is about 1.55 ms in the sampled log.
The scratch-buffer stage around VPI costs about 10.5 ms in the sampled log.
Regular05 black-border hard-gate sanity remains clean.
```

Forbidden:

```text
Full real-time EIS.
End-to-end product FPS for the complete online stabilizer.
Zero-copy full chain.
VPI optical-flow acceleration.
```

## Next Step

If continuing performance work, keep the frozen correctness path fixed and
measure or reduce the scratch-buffer stage. The simplest direct-NvBuffer-input
probe was attempted and rejected because VPI required input and output images to
have the same format while the main-chain DMABUF did not match the pitch-linear
NV12_ER output scratch.

Good next candidates are:

```text
1. reduce duplicate NvBufSurfTransform calls;
2. test format-matched NvBuffer input and output pairs before removing
   transforms;
3. compare repeated wrapper creation vs reusable wrappers;
4. only after dataflow cost is understood, revisit online producer timing.
```
