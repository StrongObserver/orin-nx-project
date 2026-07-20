# Regular05 Identity Warp Probe - 2026-07-20

## Decision

Identity matrix PerspectiveWarp is not materially cheaper than the Regular05
inclusion matrix in the accepted C++ EGLImage path. Matrix complexity is not the
main source of the remaining EGLImage stage cost.

## Probe

Input:

```text
regular_gate05_regular_6 source.h264
regular05_identity_180.csv
```

Path:

```text
accepted C++ MMAPI/VPI/NVENC EGLImage-wrapper sample
```

The probe uses an identity 3x3 matrix for all 180 frames.

## Results

```text
rc: 0
wall_time_ms: 1842
fallback_count: 0
frame_index_mismatch_count: 0
black_border_p95: 0.000000000
black_border_max: 0.000004340
```

Warp timing:

| Probe | VPI warp running avg |
|---|---:|
| Regular05 inclusion matrix | about 1.554940 ms |
| Regular05 identity matrix | 1.488830 ms |

The difference is small. The VPI submit/sync path has a baseline cost even for
identity matrices.

## Interpretation

The accepted EGLImage stage cost is not driven by matrix complexity. Combining
the recent probes:

```text
three transforms: about 2.735 ms at frame 100
EGL map/unmap: about 0.136 ms at frame 100
VPI wrapper create/destroy: about 3.692 ms at frame 100
VPI warp submit/sync: about 1.49-1.55 ms
```

These components explain most of the accepted EGLImage stage cost. Further
optimization needs a structural dataflow change, not a different warp matrix.

## Claim Boundary

Allowed:

```text
Identity warp is only slightly faster than the inclusion warp.
Warp matrix complexity is not the current bottleneck.
```

Forbidden:

```text
VPI warp is free for identity matrices.
Changing matrices alone will fix dataflow performance.
Full real-time EIS.
Zero-copy full chain.
```

## Next Step

The remaining meaningful route is format-stable dataflow: either reduce wrapper
lifecycle overhead without unsafe `vpiImageSetWrapper`, or test format-matched
NvBuffer input/output pairs.
