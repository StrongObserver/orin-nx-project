# Regular Gate Inclusion Validation - 2026-07-20

## Stage Decision

The fixed `safe103_crop98` Regular05 candidate did not generalize, but the
follow-up inclusion-constrained viewport strategy removes the real geometry
black-border root cause across all five Regular clips.

Current status:

```text
candidate: bounded_delay_lp_rigid delay90 + safe103 + inclusion scale
matrix convention: source_to_dest
bad Jetson consumer: MMAPI EGL pitch-wrapper -> in-place VPI warp -> NVENC
corrected Jetson candidate: VPI Python allocated-image path
geometry coverage: 5/5 pass, invalid output coverage = 0
visual distortion: fixed by VPI Python allocated-image path
human review: pending for five corrected review grids
```

Do not claim this as final accepted Regular gate quality until the user reviews
the five copied videos.

## Root Cause Found

Two separate issues were mixed together:

1. `safe103_crop98` failed because fixed scale/crop does not guarantee that the
   warped output footprint stays inside the source frame on every clip.
2. Early inclusion Jetson tests were accidentally run with `VPI_MATRIX_FIFO`,
   while the active `99_vpi_transcode_matrix_handoff` sample only loads
   `VPI_MATRIX_CSV`. Those runs used the sample's default matrix and were not
   valid inclusion evidence.

After rerunning with `VPI_MATRIX_CSV`, every clip loaded the intended matrix
CSV, returned `rc=0`, and kept `fallback=0`.

The user then found a more serious issue in the copied review grids:
`safe103` and `inclusion_csv` distorted immediately after playback started,
while `source` and `inc_local` remained normal. Frame extraction showed severe
block-like tearing in the MMAPI output around frame 30.

The distortion root cause is now scoped:

```text
identity matrix through MMAPI/VPI/NVENC: normal
pure translation / scale / rotation through MMAPI EGL pitch-wrapper VPI path: distorted
source_to_dest EIS matrices through the same MMAPI path: distorted
inverse matrix and VPI_WARP_INVERSE diagnostics: still not a valid fix
VPI Python allocated-image path using the same CSV matrices: normal geometry, no block tearing
```

So the inclusion algorithm and VPI PerspectiveWarp are not the problem. The
bad path is the current C++ MMAPI EGL pitch-wrapper / scratch-buffer in-place
warp integration. The corrected visual candidate uses VPI-allocated images and
VPI format conversion, matching the official VPI sample style.

## Frozen Candidate

```text
producer: bounded_delay_lp_rigid
producer_delay_frames: 90
base viewport: safe103
inclusion scale:
  safety_px=1
  lookahead=90
  rate_limit=0.003
  hysteresis=0.002
matrix composition: center scale pre-composed as S @ H
matrix convention: source_to_dest
device path: MMAPI decode -> VPI CUDA perspective warp -> NVENC
VPI env var: VPI_MATRIX_CSV
border mode: VPI_BORDER_ZERO
```

Corrected visual candidate:

```text
implementation: scripts/apply_matrix_video_vpi.py on Jetson
path: OpenCV decode -> VPI CUDA convert to NV12_ER -> VPI CUDA perspective warp
      -> VPI CUDA convert to RGB8 -> OpenCV mp4 writer
role: correctness/visual validation path, not final MMAPI/NVENC acceleration path
```

## Jetson Results

Source CSV:

```text
results/regular_gate_safe103_crop98_validation_20260720/inclusion_regular_gate_summary.csv
```

| Clip | Frames | rc | loaded | gray p95 black | gray max black | geometry p95 invalid | geometry max invalid | planned scale max |
|---|---:|---:|---|---:|---:|---:|---:|---:|
| regular_gate01_regular_10 | 180 | 0 | yes | 0.031259983 | 0.034991319 | 0.000000000 | 0.000000000 | 1.014401308 |
| regular_gate02_regular_19 | 300 | 0 | yes | 0.000296658 | 0.001228299 | 0.000000000 | 0.000000000 | 1.223233403 |
| regular_gate03_regular_13 | 180 | 0 | yes | 0.000816406 | 0.002174479 | 0.000000000 | 0.000000000 | 1.011314755 |
| regular_gate04_regular_8 | 180 | 0 | yes | 0.014146267 | 0.060481771 | 0.000000000 | 0.000000000 | 1.015951162 |
| regular_gate05_regular_6 | 180 | 0 | yes | 0.000365017 | 0.000742188 | 0.000000000 | 0.000000000 | 1.016772415 |

Interpretation:

```text
geometry-valid coverage: 5/5 pass
gray threshold black-border metric: 3/5 pass, 01/04 flagged
```

The 01/04 gray-threshold flags are not supported by the geometry coverage
check. They are currently treated as likely dark-edge or metric false positives,
not proof of out-of-source black borders.

## Distortion Fix Result

Source CSV:

```text
results/regular_gate_distortion_diagnosis_20260720/regular_gate_vpipy_fix_summary.csv
```

| Clip | Frames | fixed VPI Python p95 black | max black | frames_gt_0p01 | Distortion |
|---|---:|---:|---:|---:|---|
| regular_gate01_regular_10 | 180 | 0.009632596 | 0.016358507 | 9 | fixed |
| regular_gate02_regular_19 | 300 | 0.000256293 | 0.000464410 | 0 | fixed |
| regular_gate03_regular_13 | 180 | 0.000321181 | 0.000403646 | 0 | fixed |
| regular_gate04_regular_8 | 180 | 0.002131944 | 0.002361111 | 0 | fixed |
| regular_gate05_regular_6 | 180 | 0.000000000 | 0.000008681 | 0 | fixed |

Regular01's residual gray-threshold max is still treated as the same dark-edge
metric issue, not geometry black border. The corrected frames no longer show
the block-like tearing seen in the MMAPI path.

## Rejected Detours

The following were tested and rejected as final explanations:

| Attempt | Result |
|---|---|
| stronger fixed crop95/crop92 on safe103 | did not fix Regular01/02 |
| `VPI_MATRIX_FIFO` inclusion run | invalid because sample did not read FIFO |
| `post` composition | fixed Regular01 but worsened Regular04 |
| uniform margin103/margin106 | did not solve 01/04 and could worsen gray metric |
| crop98 after inclusion output | did not fix gray-threshold flags |
| MMAPI EGL pitch-wrapper VPI warp | corrupts non-identity matrix output with block-like tearing |

## Review Assets

Review directory:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_inclusion_validation\
```

Main review videos:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_inclusion_validation\20260720_regular_gate_inclusion_validation_regular_gate01_regular_10_jetson_source_safe103_inclusion_grid.mp4
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_inclusion_validation\20260720_regular_gate_inclusion_validation_regular_gate02_regular_19_jetson_source_safe103_inclusion_grid.mp4
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_inclusion_validation\20260720_regular_gate_inclusion_validation_regular_gate03_regular_13_jetson_source_safe103_inclusion_grid.mp4
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_inclusion_validation\20260720_regular_gate_inclusion_validation_regular_gate04_regular_8_jetson_source_safe103_inclusion_grid.mp4
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_inclusion_validation\20260720_regular_gate_inclusion_validation_regular_gate05_regular_6_jetson_source_safe103_inclusion_grid.mp4
```

Corrected distortion-fix review directory:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_vpi_python_fix\
```

Corrected review videos:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_vpi_python_fix\20260720_regular_gate_vpi_python_fix_regular_gate01_regular_10_jetson_source_badmmapi_fixedvpipy_grid.mp4
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_vpi_python_fix\20260720_regular_gate_vpi_python_fix_regular_gate02_regular_19_jetson_source_badmmapi_fixedvpipy_grid.mp4
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_vpi_python_fix\20260720_regular_gate_vpi_python_fix_regular_gate03_regular_13_jetson_source_badmmapi_fixedvpipy_grid.mp4
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_vpi_python_fix\20260720_regular_gate_vpi_python_fix_regular_gate04_regular_8_jetson_source_badmmapi_fixedvpipy_grid.mp4
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_vpi_python_fix\20260720_regular_gate_vpi_python_fix_regular_gate05_regular_6_jetson_source_badmmapi_fixedvpipy_grid.mp4
```

Each corrected review grid shows:

```text
source / bad_mmapi / fixed_vpipy / inc_local
```

Focused gray-metric worst-frame sheets:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_inclusion_validation\20260720_regular_gate_inclusion_validation_regular_gate01_regular_10_jetson_gray_metric_worst_sheet.jpg
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_inclusion_validation\20260720_regular_gate_inclusion_validation_regular_gate04_regular_8_jetson_gray_metric_worst_sheet.jpg
```

Each review grid shows:

```text
source / safe103 / inclusion_csv / local inclusion reference
```

## Claim Boundary

Allowed:

```text
safe103_crop98 failed as a general Regular producer.
The inclusion-constrained matrix strategy gives 5/5 geometry-valid coverage on
the Regular gate under Jetson MMAPI/VPI/NVENC replay.
The MMAPI EGL pitch-wrapper VPI integration is currently a rejected acceleration
path because non-identity matrices produce block-like tearing.
The VPI Python allocated-image path fixes the visible distortion and is the
current correctness candidate.
Gray-threshold black-border metric can false-positive on dark edge content and
should be demoted to an auxiliary diagnostic when geometry coverage is zero.
```

Forbidden:

```text
Regular gate is fully accepted before human review.
Per-clip pre/post composition or crop tuning as one frozen strategy.
Full real-time EIS.
VPI optical-flow acceleration.
All-scene EIS quality.
```

## Next Step

Ask the user to review the five corrected `regular_gate_vpi_python_fix` grids.
If accepted, freeze the VPI Python allocated-image output as the visual
correctness candidate, and keep the MMAPI EGL pitch-wrapper path as a rejected
acceleration boundary until a C++ allocated-image or correct NvBufSurface/VPI
integration is implemented.
