# Regular05 EGLImage Dataflow Cost - 2026-07-20

## Decision

Wrapper reuse is a valid first optimization for the accepted C++ EGLImage-wrapper
path. It reduces Regular05 same-input wall time and the measured EGLImage stage
cost without changing the accepted stabilization matrix or the C++ device path
claim boundary.

This is still a Regular05 dataflow result, not a full real-time EIS claim.

## Baseline

Accepted C++ EGLImage-wrapper path, one wrapper/stream create-destroy cycle per
frame:

| Metric | Result |
|---|---:|
| Wall time, 180 frames | 2002 ms |
| Matrix handoff avg | 1.099636 us |
| VPI warp-only avg | 1.554940 ms |
| EGLImage stage avg | 10.504100 ms |
| Black border p95 | 0.000000000 |

## Wrapper Reuse Probe

New probe script:

```text
scripts/patch_mmapi_vpi_transcode_eglimage_reuse_warp.py
```

Remote sample:

```text
/home/nvidia/orin-nx-project/_mmapi_work/jetson_multimedia_api/samples/99_vpi_transcode_matrix_eglimage_reuse
```

Evidence:

```text
results/regular05_eglimage_dataflow_cost_20260720
```

Results:

| Metric | Result |
|---|---:|
| Wall time, 180 frames | 1573 ms |
| Matrix handoff avg | 0.861091 us |
| Matrix handoff fallback / mismatch | 0 / 0 |
| VPI warp-only avg | 1.832560 ms |
| EGLImage stage avg | 7.868660 ms |
| Frame-100 input transform | 0.950693 ms |
| Frame-100 wrapper+warp call | 3.737140 ms |
| Frame-100 output transform | 0.972613 ms |
| Black border p95 | 0.001102647 |
| Frames > 1% black border | 0 |

Delta:

| Metric | Baseline | Wrapper reuse | Change |
|---|---:|---:|---:|
| Wall time, 180 frames | 2002 ms | 1573 ms | -429 ms |
| EGLImage stage avg | 10.504100 ms | 7.868660 ms | -2.635440 ms |
| VPI warp-only avg | 1.554940 ms | 1.832560 ms | +0.277620 ms |

## Interpretation

Reusing VPI stream and EGLImage wrappers reduces the dataflow stage, but the
first frame has a large initialization spike. After frame 1, sampled frames show
the stage often in the 4-6 ms range instead of the previous 10.5 ms average.

The next performance question is no longer whether wrapper reuse helps; it does.
The next question is how to remove or amortize remaining transform/synchronization
cost while keeping the same output semantics.

## Rejected Shortcut

The direct `VPI_IMAGE_BUFFER_NVBUFFER` input shortcut failed in a separate probe:

```text
Input and output images must have the same format
rc=139
```

Do not retry that exact path without first making input and output formats match.

## Claim Boundary

Allowed:

```text
Wrapper reuse reduces Regular05 C++ EGLImage dataflow cost under the same input
and matrix semantics.
Regular05 output remains readable and black-border hard-gate sanity remains
below 1%.
```

Forbidden:

```text
Full real-time EIS.
Zero-copy full chain.
All-scene EIS quality.
VPI optical-flow acceleration.
```

## Next Step

The next useful experiment is one of:

```text
1. reuse wrappers and stream in the accepted path if the code remains stable;
2. isolate NvBufSurfTransform cost with transform-only timing;
3. test format-matched NvBuffer input/output pairs;
4. run five-clip timing only after Regular05 reuse is visually accepted or at
   least no-regression checked.
```
