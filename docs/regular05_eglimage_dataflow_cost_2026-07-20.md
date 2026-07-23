# Regular05 EGLImage Dataflow Cost - 2026-07-20

## Decision

This note is superseded by the later wrapper-reuse root-cause investigation.
The timing observation below remains useful as historical negative evidence, but
EGLImage image-wrapper reuse is not safe to promote in the accepted C++
MMAPI/NvBufSurface/VPI path.

Current accepted policy:

```text
reuse VPI stream: allowed
recreate VPI EGLImage image wrappers per frame: required for correctness
```

The wrapper-reuse probe reduced Regular05 same-input wall time and measured
stage cost, but later variants showed visible tearing or VPI failures when image
wrappers were reused over changing EGLImage/NvBuffer-backed surfaces. See
`docs/regular05_eglimage_wrapper_reuse_root_cause_2026-07-20.md`.

This is a Regular05 dataflow diagnostic, not a current optimization claim and
not a full real-time EIS claim.

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

## Historical Interpretation

Reusing VPI stream and EGLImage wrappers appeared to reduce the dataflow stage,
but that route was later rejected because image-wrapper reuse is not correctness
safe in this pipeline. After frame 1, sampled frames showed the stage often in
the 4-6 ms range instead of the previous 10.5 ms average, which helped motivate
the later wrapper lifecycle, submit/sync, and NvBuffer pair probes.

The current performance question is how to reduce wrapper/sync/transform
overhead while keeping the accepted per-frame-wrapper output semantics, or by
using an explicitly format-matched NvBuffer pair path.

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
Wrapper reuse was a useful diagnostic that exposed wrapper lifecycle cost.
VPI stream reuse is safe in this path.
EGLImage image-wrapper reuse is rejected for correctness-critical Regular gate evidence.
Regular05 output remains readable and black-border hard-gate sanity remains
below 1%.
```

Forbidden:

```text
Promoting EGLImage image-wrapper reuse as the current optimization path.
Full real-time EIS.
Zero-copy full chain.
All-scene EIS quality.
VPI optical-flow acceleration.
```

## Next Step

The next useful experiment is one of:

```text
1. keep using the accepted per-frame-wrapper EGLImage path for correctness;
2. use the later format-matched NvBuffer pair result as the current follow-up
   when the source, matrix, crop/postprocess, and review boundary are identical;
3. only open a new dataflow A/B contract if it keeps `resid_r15_s07` as the
   quality anchor and does not mix matrix-quality changes with transport changes.
```
