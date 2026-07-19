# Regular Gate VPI Distortion Fix - 2026-07-20

## Decision

The visible block-like distortion in the previous Regular gate inclusion review
videos is fixed by switching the visual correctness path from the C++ MMAPI EGL
pitch-wrapper integration to a VPI allocated-image path.

Current corrected review directory:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_vpi_python_fix\
```

## User-Reported Problem

The user reviewed:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_inclusion_validation\
```

and found:

```text
source: normal
inc_local: normal
safe103: block-like distortion soon after playback starts
inclusion_csv: block-like distortion soon after playback starts
```

The user also confirmed that the red regions in the previous Regular01 and
Regular04 gray-metric worst-frame sheets were not real black borders; those
areas were dark in the source.

## Root Cause Scope

The failure is not caused by the inclusion algorithm.

Evidence:

| Test | Result |
|---|---|
| OpenCV local inclusion warp | normal |
| MMAPI/VPI/NVENC identity matrix | normal |
| MMAPI/VPI/NVENC pure translation | distorted |
| MMAPI/VPI/NVENC pure scale | distorted |
| MMAPI/VPI/NVENC pure rotation | distorted |
| MMAPI/VPI/NVENC safe103 matrix | distorted |
| MMAPI/VPI/NVENC inclusion matrix | distorted |
| MMAPI/VPI/NVENC inverse matrix | not a fix |
| MMAPI/VPI/NVENC `VPI_WARP_INVERSE` diagnostic | not a fix |
| MMAPI/VPI/NVENC `VPI_PRECISE` diagnostic | not a fix |
| VPI Python allocated-image path with same matrices | normal geometry, no block tearing |

The current bad path is:

```text
MMAPI decode
-> NvBufSurface / EGL pitch wrapper
-> in-place VPI CUDA PerspectiveWarp through scratch buffer
-> transform back to encoder DMABUF
-> NVENC
```

The corrected visual path is:

```text
OpenCV decode
-> VPI CUDA wrap as explicit BGR8
-> VPI CUDA convert to NV12_ER allocated image
-> VPI CUDA PerspectiveWarp
-> VPI CUDA convert to RGB8
-> OpenCV mp4 writer
```

This corrected path is a visual correctness path, not a final hardware
acceleration claim.

## Color Shift Fix

The first VPI Python correction removed block tearing, but the user found a
new color issue: `fixed_vpipy` made weak green/yellow regions much deeper,
especially the grass in `regular_gate05_regular_6`.

Root cause:

```text
OpenCV frames are BGR.
The first VPI Python script wrapped the OpenCV array without an explicit source
format, so VPI interpreted the input as the wrong channel order before
BGR/RGB -> NV12 conversion.
```

Fix:

```text
vpi.asimage(frame_bgr, vpi.Format.BGR8).convert(vpi.Format.NV12_ER)
```

This is implemented in:

```text
scripts/apply_matrix_video_vpi.py --input-format bgr8
```

## Corrected Output Metrics

Source CSV:

```text
results/regular_gate_distortion_diagnosis_20260720/regular_gate_vpipy_fix_summary.csv
```

| Clip | Frames | p95 black | max black | frames > 0.01 | Distortion |
|---|---:|---:|---:|---:|---|
| regular_gate01_regular_10 | 180 | 0.009632596 | 0.016358507 | 9 | fixed |
| regular_gate02_regular_19 | 300 | 0.000256293 | 0.000464410 | 0 | fixed |
| regular_gate03_regular_13 | 180 | 0.000321181 | 0.000403646 | 0 | fixed |
| regular_gate04_regular_8 | 180 | 0.002131944 | 0.002361111 | 0 | fixed |
| regular_gate05_regular_6 | 180 | 0.000000000 | 0.000008681 | 0 | fixed |

Regular01 has a small gray-threshold tail, but the earlier user review already
confirmed this class of dark-edge signal is not a real black border. Geometry
coverage remains the hard border check for this matrix-driven output.

Color-fixed source CSV:

```text
results/regular_gate_color_fix_20260720/regular_gate_bgr8_color_fix_summary.csv
```

| Clip | Frames | p95 black | mean abs vs local | p95 abs vs local | Color |
|---|---:|---:|---:|---:|---|
| regular_gate01_regular_10 | 180 | 0.017633898 | 2.179464 | 5.850000 | fixed |
| regular_gate02_regular_19 | 300 | 0.000225911 | 2.157899 | 5.773333 | fixed |
| regular_gate03_regular_13 | 180 | 0.000247830 | 2.032374 | 5.688889 | fixed |
| regular_gate04_regular_8 | 180 | 0.001918837 | 1.795264 | 4.855556 | fixed |
| regular_gate05_regular_6 | 180 | 0.000000000 | 1.950458 | 5.066667 | fixed |

Regular05 color-channel means after the fix are nearly identical to
`inc_local`; the old `fixed_vpipy` had blue/red swapped behavior and visible
green/cyan deepening.

## Review Assets

Corrected five-clip review videos:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_vpi_python_fix\20260720_regular_gate_vpi_python_fix_regular_gate01_regular_10_jetson_source_badmmapi_fixedvpipy_grid.mp4
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_vpi_python_fix\20260720_regular_gate_vpi_python_fix_regular_gate02_regular_19_jetson_source_badmmapi_fixedvpipy_grid.mp4
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_vpi_python_fix\20260720_regular_gate_vpi_python_fix_regular_gate03_regular_13_jetson_source_badmmapi_fixedvpipy_grid.mp4
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_vpi_python_fix\20260720_regular_gate_vpi_python_fix_regular_gate04_regular_8_jetson_source_badmmapi_fixedvpipy_grid.mp4
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_vpi_python_fix\20260720_regular_gate_vpi_python_fix_regular_gate05_regular_6_jetson_source_badmmapi_fixedvpipy_grid.mp4
```

Color-fixed review directory:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_vpi_bgr8_color_fix\
```

Color-fixed review videos:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_vpi_bgr8_color_fix\20260720_regular_gate_vpi_bgr8_color_fix_regular_gate01_regular_10_source_oldcolor_fixedbgr8_grid.mp4
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_vpi_bgr8_color_fix\20260720_regular_gate_vpi_bgr8_color_fix_regular_gate02_regular_19_source_oldcolor_fixedbgr8_grid.mp4
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_vpi_bgr8_color_fix\20260720_regular_gate_vpi_bgr8_color_fix_regular_gate03_regular_13_source_oldcolor_fixedbgr8_grid.mp4
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_vpi_bgr8_color_fix\20260720_regular_gate_vpi_bgr8_color_fix_regular_gate04_regular_8_source_oldcolor_fixedbgr8_grid.mp4
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_vpi_bgr8_color_fix\20260720_regular_gate_vpi_bgr8_color_fix_regular_gate05_regular_6_source_oldcolor_fixedbgr8_grid.mp4
```

Fast color-fixed scan sheet:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_vpi_bgr8_color_fix\20260720_regular_gate_vpi_bgr8_color_fix_fixed_bgr8_5clip_contact_sheet.jpg
```

Fast scan sheet:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_vpi_python_fix\20260720_regular_gate_vpi_python_fix_fixed_vpipy_5clip_contact_sheet.jpg
```

Root-cause sheets:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_vpi_python_fix\20260720_regular_gate_vpi_python_fix_regular_gate01_regular_10_frame_diagnosis_sheet.jpg
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_vpi_python_fix\20260720_regular_gate_vpi_python_fix_regular_gate01_regular_10_root_cause_minimal_matrix_sheet.jpg
```

Each corrected review video shows:

```text
source / bad_mmapi / fixed_vpipy / inc_local
```

## Claim Boundary

Allowed:

```text
The previous MMAPI EGL pitch-wrapper output is rejected because it tears under
non-identity matrices.
The same inclusion matrices render without block tearing through the VPI
allocated-image path.
The VPI Python path with explicit `BGR8` input is the current visual correctness
candidate for human review.
```

Forbidden:

```text
Do not claim the MMAPI/NVENC path is fixed.
Do not claim final real-time EIS.
Do not claim this as hardware acceleration.
Do not reuse the distorted MMAPI outputs as quality evidence.
```

## Next Step

Ask the user to review the five corrected videos in:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_vpi_bgr8_color_fix\
```

If accepted, freeze the VPI Python allocated-image + explicit BGR8 output as
the Regular gate visual correctness candidate. The next engineering task is a
separate C++ fix for the MMAPI/VPI/NVENC path, likely by replacing the fragile
EGL pitch-wrapper warp with a VPI-allocated image or a correct NvBufSurface/VPI
integration.
