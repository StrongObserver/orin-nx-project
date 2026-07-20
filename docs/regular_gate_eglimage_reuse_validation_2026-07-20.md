# Regular Gate EGLImage Reuse Validation - 2026-07-20

## Decision

Wrapper reuse improves Regular05 performance and runs across all five Regular
inclusion clips, but it is not frozen as the replacement C++ path yet. Five
review grids were generated and need human visual review because Regular03 and
Regular04 show gray-threshold border flags that require visual classification.

## Input

```text
sample: /home/nvidia/orin-nx-project/_mmapi_work/jetson_multimedia_api/samples/99_vpi_transcode_matrix_eglimage_reuse
matrix convention: source_to_dest
matrix: inclusion_source_to_dest.csv per Regular clip
```

## Summary

| Clip | rc | wall ms | fallback | mismatch | VPI avg ms | stage avg ms | black p95 | frames > 1% |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| regular_gate01_regular_10 | 0 | 1510 | 0 | 0 | 1.778200 | 7.868190 | 0.014461154 | 10 |
| regular_gate02_regular_19 | 0 | 2129 | 0 | 0 | 1.808630 | 5.956170 | 0.000075087 | 0 |
| regular_gate03_regular_13 | 0 | 1405 | 0 | 0 | 1.572630 | 6.930200 | 0.001649956 | 5 |
| regular_gate04_regular_8 | 0 | 1536 | 0 | 0 | 2.018780 | 7.891210 | 0.009744575 | 8 |
| regular_gate05_regular_6 | 0 | 1344 | 0 | 0 | 1.626620 | 6.803270 | 0.000894531 | 0 |

## Evidence

Remote evidence:

```text
/home/nvidia/orin-nx-project/results/regular_gate_eglimage_reuse_validation_20260720
```

Local evidence:

```text
results/regular_gate_eglimage_reuse_validation_20260720
```

Review copies:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_eglimage_reuse_validation\
```

Review grids:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_eglimage_reuse_validation\20260720_regular_gate_eglimage_reuse_validation_regular_gate01_regular_10_source_accepted_reuse_bgr8_grid.mp4
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_eglimage_reuse_validation\20260720_regular_gate_eglimage_reuse_validation_regular_gate02_regular_19_source_accepted_reuse_bgr8_grid.mp4
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_eglimage_reuse_validation\20260720_regular_gate_eglimage_reuse_validation_regular_gate03_regular_13_source_accepted_reuse_bgr8_grid.mp4
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_eglimage_reuse_validation\20260720_regular_gate_eglimage_reuse_validation_regular_gate04_regular_8_source_accepted_reuse_bgr8_grid.mp4
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_eglimage_reuse_validation\20260720_regular_gate_eglimage_reuse_validation_regular_gate05_regular_6_source_accepted_reuse_bgr8_grid.mp4
```

Each grid compares:

```text
source / accepted_egl / reuse_egl / fixed_bgr8
```

## Interpretation

Wrapper reuse is technically viable across all five Regular clips:

```text
rc=0
fallback=0
frame_index_mismatch=0
```

Regular02 and Regular05 are clean by gray-threshold black-border metrics.
Regular01 follows the known dark-edge caveat. Regular03 and Regular04 need
human review before promotion because they show some gray-threshold border
flags even though the outputs are readable.

## Claim Boundary

Allowed:

```text
Wrapper reuse runs across all five Regular inclusion clips.
Wrapper reuse reduces Regular05 dataflow cost relative to per-frame wrapper
creation.
Wrapper reuse is a performance candidate pending five-clip visual review.
```

Forbidden:

```text
Wrapper reuse is the frozen Regular gate C++ path before human review.
Full real-time EIS.
Zero-copy full chain.
VPI optical-flow acceleration.
All-scene EIS quality.
```

## Next Step

Ask the user to review the five wrapper reuse grids. If accepted, promote wrapper
reuse into the Regular gate C++ path. If any clip is visually worse than the
accepted EGLImage path, keep wrapper reuse as a performance experiment and do
not replace the frozen path.
