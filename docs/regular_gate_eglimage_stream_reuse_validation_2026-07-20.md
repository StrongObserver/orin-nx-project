# Regular Gate EGLImage Stream Reuse Validation - 2026-07-20

## Decision

The current full wrapper reuse implementation is rejected for quality. The user
observed block tearing in `reuse_egl`, and frame sheets confirmed block-like
tearing in the full wrapper reuse output while `accepted_egl` and `fixed_bgr8`
remained normal.

The safer control is stream-only reuse: reuse the VPI stream, but recreate
EGLImage wrappers per frame. This removes the observed tearing on the tested
gate04 probe and restores gray-threshold black-border sanity across the five
Regular clips. This does not prove the broader wrapper-reuse route is a dead
end. It only proves that the current single-wrapper `vpiImageSetWrapper`
implementation is unsafe.

## Root Cause Scope

The issue is not caused by the stabilization matrix or by the accepted C++ path:

```text
accepted_egl: normal
fixed_bgr8: normal
full_reuse_bad: block tearing / block displacement
stream_reuse: normal in the gate04 probe and clean by five-clip sanity metrics
```

The most likely root cause is unsafe reuse of one VPI image wrapper across
changing EGLImage / NvBuffer scratch surfaces. Reusing only the stream avoids
that wrapper-lifetime hazard. The next root-cause step is to test safer reuse
granularity, especially one wrapper pair per V4L2 buffer index, plus explicit
sync/lifetime variants.

## Evidence

Diagnosis output:

```text
results/reuse_tearing_diagnosis_20260720/reuse_vs_accepted_contact_sheet.jpg
results/reuse_tearing_fix_probe_20260720/regular_gate04_stream_reuse_fix_grid.mp4
```

Review copy for the direct fix probe:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260720_reuse_tearing_fix_probe\20260720_reuse_tearing_fix_probe_regular_gate04_source_accepted_fullreuse_streamreuse_grid.mp4
```

Five-clip stream-only reuse evidence:

```text
results/regular_gate_eglimage_stream_reuse_validation_20260720
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_eglimage_stream_reuse_validation\
```

## Five-Clip Summary

| Clip | rc | wall ms | fallback | mismatch | stage avg ms | black p95 | frames > 1% |
|---|---:|---:|---:|---:|---:|---:|---:|
| regular_gate01_regular_10 | 0 | 2016 | 0 | 0 | 10.512300 | 0.013856771 | 10 |
| regular_gate02_regular_19 | 0 | 2689 | 0 | 0 | 7.962510 | 0.000130859 | 0 |
| regular_gate03_regular_13 | 0 | 1842 | 0 | 0 | 9.980720 | 0.000091363 | 0 |
| regular_gate04_regular_8 | 0 | 1741 | 0 | 0 | 9.219770 | 0.000330078 | 0 |
| regular_gate05_regular_6 | 0 | 1768 | 0 | 0 | 9.195490 | 0.000000000 | 0 |

Review grids:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_eglimage_stream_reuse_validation\20260720_regular_gate_eglimage_stream_reuse_validation_regular_gate01_regular_10_source_accepted_fullreuse_streamreuse_grid.mp4
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_eglimage_stream_reuse_validation\20260720_regular_gate_eglimage_stream_reuse_validation_regular_gate02_regular_19_source_accepted_fullreuse_streamreuse_grid.mp4
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_eglimage_stream_reuse_validation\20260720_regular_gate_eglimage_stream_reuse_validation_regular_gate03_regular_13_source_accepted_fullreuse_streamreuse_grid.mp4
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_eglimage_stream_reuse_validation\20260720_regular_gate_eglimage_stream_reuse_validation_regular_gate04_regular_8_source_accepted_fullreuse_streamreuse_grid.mp4
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_eglimage_stream_reuse_validation\20260720_regular_gate_eglimage_stream_reuse_validation_regular_gate05_regular_6_source_accepted_fullreuse_streamreuse_grid.mp4
```

Each review grid shows:

```text
source / accepted_egl / full_reuse_bad / stream_reuse
```

## Claim Boundary

Allowed:

```text
The current single-wrapper reuse implementation is rejected because it causes
visible block tearing.
Stream-only reuse avoids the observed tearing in the tested evidence and keeps
five-clip fallback/mismatch at 0.
Stream-only reuse has limited performance value compared with the accepted path.
```

Forbidden:

```text
The full wrapper reuse route is proven impossible.
Stream-only reuse is a major acceleration result.
Full real-time EIS.
Zero-copy full chain.
VPI optical-flow acceleration.
```

## Next Step

Do not promote the current single-wrapper reuse implementation. Continue the
root-cause loop before abandoning wrapper reuse entirely. The next tests should
try per-buffer-index wrapper reuse and stricter sync/lifetime handling. If those
also fail with clear evidence, then wrapper reuse can be downgraded to a dead
end and performance work should target `NvBufSurfTransform` cost or
format-matched NvBuffer input/output.
