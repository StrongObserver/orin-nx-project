# Regular05 EGLImage Wrapper Reuse Root Cause - 2026-07-20

## Decision

EGLImage image-wrapper reuse is not safe to promote in the current
MMAPI/NvBufSurface/VPI path. The accepted path remains:

```text
reuse VPI stream: allowed
recreate VPI EGLImage wrappers per frame: required for correctness
```

This is not a retreat from the C++ device path. It is a scoped dead end for
`vpiImageSetWrapper` over changing EGLImage / NvBuffer scratch surfaces in this
pipeline.

## Why This Is Enough Evidence

The user correctly pointed out that one failure is not enough to abandon a route.
The wrapper-reuse route was therefore tested across several root-cause variants:

| Variant | Result | Interpretation |
|---|---|---|
| single input/output wrapper reused across all frames | visible block tearing | unsafe |
| per-buffer-index wrapper reuse | VPI error, then failure | not solved by matching V4L2 buffer index |
| input-wrapper-only reuse | ran but visible block tearing remains | input wrapper reuse alone can corrupt output |
| output-wrapper-only reuse | ran but visible block tearing remains | output wrapper reuse alone can corrupt output |
| persistent EGLImage mapping + per-buffer wrapper reuse | ran but visible block tearing remains | repeated unmap/remap is not the only cause |
| stream-only reuse | ran clean by visual/metric sanity | reusing stream is safe; reusing image wrappers is the risky part |
| explicit NvBufSurfaceSyncForDevice around full wrapper reuse | `Bad parameter`, rc=139 | sync API is not a usable fix here |

The common failure factor is `vpiImageSetWrapper` on VPI image wrappers over
changing EGLImage/NvBufSurface-backed images. The safe control is recreating the
image wrappers per frame.

## Evidence

Local evidence:

```text
results/reuse_tearing_diagnosis_20260720
results/reuse_tearing_fix_probe_20260720
results/wrapper_reuse_root_cause_20260720
results/regular_gate_eglimage_stream_reuse_validation_20260720
```

Representative review assets:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260720_reuse_tearing_fix_probe\20260720_reuse_tearing_fix_probe_regular_gate04_source_accepted_fullreuse_streamreuse_grid.mp4
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_eglimage_stream_reuse_validation\
```

The clearest diagnostic image is:

```text
results/reuse_tearing_diagnosis_20260720/reuse_vs_accepted_contact_sheet.jpg
```

It shows `reuse` rows with block displacement while `accepted` rows are normal.

## Technical Boundary

VPI documents `vpiImageSetWrapper` as requiring the new wrapped memory to have
the same dimensions, format, and buffer type, and the wrapped memory must not be
deallocated while wrapped. Those conditions are not sufficient in this MMAPI
EGLImage/NvBufSurface ring-buffer path: even per-buffer and persistent mapping
variants still produced tearing or VPI errors.

Therefore the project should not use wrapper reuse for correctness-critical
Regular gate evidence.

## Claim Boundary

Allowed:

```text
VPI stream reuse is safe in this path.
VPI EGLImage image-wrapper reuse is rejected for this MMAPI path after multiple
root-cause variants.
The accepted C++ path remains per-frame EGLImage wrapper creation.
```

Forbidden:

```text
Full wrapper reuse is safe.
This proves VPI itself is broken.
This affects the accepted C++ EGLImage path.
Full real-time EIS.
Zero-copy full chain.
```

## Next Step

Continue performance work from the accepted per-frame-wrapper EGLImage path.
The next promising direction is not wrapper reuse; it is reducing or better
accounting for `NvBufSurfTransform` / dataflow cost, or testing format-matched
NvBuffer input/output pairs with clear format parity.
