# Device Matrix Warp Demo Boundary - 2026-07-19

## Stage Decision

The current MMAPI/VPI/NVENC device-side path is validated as an offline
matrix-driven warp and encode boundary:

```text
H264 input
-> Jetson Multimedia API decode / NvBufSurface
-> NvBufSurfTransform to pitch-linear NV12_ER scratch
-> VPI CUDA perspective warp
-> NvBufSurfTransform back to block-linear NV12
-> NVENC
```

Use it as a device-side dataflow and warp module milestone. Do not present it as
a real-time full EIS pipeline.

## What Passed

Forward matrix is not the correct device default for this path:

| Output | Mean | Std | Black ratio | Decision |
|---|---:|---:|---:|---|
| source sampled frames | 103.448 | 68.162 | 0.0306 | normal |
| CPU stabilized sampled frames | 102.192 | 66.690 | 0.0313 | normal |
| device forward matrix sampled frames | 73.903 | 73.710 | 0.3034 | too much black border |
| device inverse matrix sampled frames | 106.045 | 66.147 | 0.0288 | current device default |

The useful device command path is therefore `matrices_inverse.csv`, not
`matrices.csv`.

Recorded device-side VPI timing:

```text
device inverse matrix run: avg around 1.42 ms by frame 100
device inverse matrix profile run: avg around 1.25 ms by frame 100
```

This timing is for the VPI warp section inside the MMAPI transcode path, not for
full online EIS.

## New Alignment Check

The first local alignment check used panels inside the review video before raw
Jetson outputs were copied back:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260719_same_source_matrix_device_warp\20260719_same_source_matrix_device_warp_raw_cpu_device_compare.mp4
```

The panel check uses `scripts/compare_triptych_regions.py`, ignores the label
band at the top of the video, and compares 120 frames.

Standardized review copy:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260719_same_source_matrix_device_warp\20260719_device_matrix_warp_demo_sample_outdoor_car_jetson_inverse_matrix_raw_cpu_device_compare.mp4
```

| Comparison | mean_abs_center_avg | p95_abs_center_avg | Interpretation |
|---|---:|---:|---|
| raw source vs CPU stabilized | 15.633184 | 61.750000 | CPU output differs moderately from raw |
| raw source vs device inverse | 36.398325 | 136.866667 | device output differs strongly from raw |
| CPU stabilized vs device inverse | 37.033757 | 138.416667 | not CPU-output equivalence |

Decision:

```text
The inverse-matrix device path has sane black-border behavior and runs through
NVENC, but it does not yet reproduce the CPU stabilized output closely.
```

## Panel Video Diff Fallback

Before direct raw-output comparison was available, the existing triptych review
video was split into three panel videos:

```text
results/device_matrix_warp_demo_20260719/panels/raw_panel.mp4
results/device_matrix_warp_demo_20260719/panels/cpu_panel.mp4
results/device_matrix_warp_demo_20260719/panels/device_panel.mp4
```

Those panel videos were then compared with `scripts/compare_videos_frame_diff.py`:

| Comparison | mean_abs_center_avg | p95_abs_center_avg | Interpretation |
|---|---:|---:|---|
| raw panel vs CPU panel | 16.471374 | 63.742500 | CPU panel differs moderately from raw |
| raw panel vs device panel | 39.184460 | 142.141667 | device panel differs strongly from raw |
| CPU panel vs device panel | 39.751371 | 143.175417 | still not CPU-output equivalence |

This is still not as strong as direct raw-video comparison, because the panel
videos are extracted from an already encoded review video. Keep it only as a
repeatable fallback; the later direct Jetson-output comparisons are stronger.

## Why The Difference Is Expected

The CPU pipeline applies more than the exported warp matrix:

```text
cv2.warpAffine(..., borderMode=cv2.BORDER_REFLECT)
fix_border(border_scale * dynamic_zoom)
fixed center crop and resize
Lanczos interpolation
optional sharpen
```

The current MMAPI/VPI path applies:

```text
VPI perspective warp
linear interpolation
VPI_BORDER_ZERO
NV12 device-side encode path
```

So the current result is not a strict parity test. It is a device-side warp and
encode boundary test.

## Minimal Parity Finding

Before implementing heavier device-side post-processing, fix the matrix timeline
first:

```text
cpu_stabilize.py writes 119 matrix rows for a 120-frame output, because the
first frame is written before the per-frame warp loop. The MMAPI patch applies
matrix row 0 to device frame 1, so the recorded 119-row device CSV can shift the
matrix timeline and leave the last device frame to identity fallback.
```

Two device-ready matrix candidates were generated locally:

| Candidate | Rows | Purpose |
|---|---:|---|
| `device_matrices_inverse_aligned_identity_first.csv` | 120 | prepend first-frame identity, then use the recorded inverse matrices |
| `device_matrices_inverse_with_post_geometry.csv` | 120 | prepend first-frame post-geometry and compose CPU dynamic zoom + crop geometry before inversion |

Commands:

```powershell
py -3.12 scripts\prepare_device_matrix_csv.py `
  --matrix-input results\same_source_matrix_20260719\matrices.csv `
  --metrics results\same_source_matrix_20260719\metrics.csv `
  --width 1920 `
  --height 1080 `
  --crop-ratio 0.90 `
  --border-scale 1.0 `
  --prepend-first-frame identity `
  --output-convention inverse `
  --output results\device_matrix_warp_demo_20260719\device_matrices_inverse_aligned_identity_first.csv

py -3.12 scripts\prepare_device_matrix_csv.py `
  --matrix-input results\same_source_matrix_20260719\matrices.csv `
  --metrics results\same_source_matrix_20260719\metrics.csv `
  --width 1920 `
  --height 1080 `
  --crop-ratio 0.90 `
  --border-scale 1.0 `
  --compose-post-geometry `
  --prepend-first-frame post_geometry `
  --output-convention inverse `
  --output results\device_matrix_warp_demo_20260719\device_matrices_inverse_with_post_geometry.csv
```

The aligned-identity candidate is numerically identical to the old inverse CSV
after skipping the prepended first row:

```text
old_rows=119
new_rows_after_first=119
max_abs_diff_old_vs_new_shifted=0.0
```

Next Jetson A/B order:

```text
1. Run aligned_identity_first first to isolate frame-timeline alignment.
2. Run with_post_geometry second to test whether CPU geometric post-processing
   should be composed into the VPI matrix.
3. Do not implement sharpen or online motion estimation until those two results
   are reviewed.
```

## Jetson A/B Result

Both 120-row candidates were run on Jetson with:

```text
/home/nvidia/orin-nx-project/_mmapi_work/jetson_multimedia_api/samples/99_vpi_transcode_matrix/multivideo_transcode
```

Important run detail:

```text
Do not add `--stats` for this sample path. In this session, `--stats` printed a
successful app log but produced a 0-byte output file. Running without `--stats`
produced valid H264 outputs and still printed VPI timing lines.
```

Timing and direct CPU-vs-device diff:

| Device output | Matrix rows loaded | VPI avg at frame 100 | mean_abs_center_avg vs CPU | p95_abs_center_avg vs CPU | Decision |
|---|---:|---:|---:|---:|---|
| old inverse | 119 | 1.416640 ms | 44.739667 | 156.975000 | valid path, poor parity |
| aligned identity first | 120 | 1.436010 ms | 46.884302 | 159.958333 | worse, not useful alone |
| post geometry | 120 | 1.455940 ms | 30.688605 | 116.958333 | strong improvement |
| post geometry, identity first | 120 | 1.442760 ms | 30.241568 | 115.866667 | current best device candidate |
| post geometry, identity first, Catmull-Rom | 120 | 2.980040 ms | 30.902334 | 117.875000 | slower and worse |

Interpretation:

```text
Frame-count alignment alone did not improve the device output. Composing CPU
dynamic zoom + crop geometry into the inverse matrix materially reduced the
CPU-vs-device gap. Using identity for the prepended first frame gives a small
additional improvement. Catmull-Rom interpolation is not worth adopting: it is
slower and does not improve the diff. The result is still not CPU-output
equivalence.
```

Review asset:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260719_same_source_matrix_device_warp\20260719_device_matrix_warp_demo_sample_outdoor_car_jetson_post_geometry_grid_compare.mp4
C:\Users\Admin\Videos\orin nx\review\performance\20260719_same_source_matrix_device_warp\20260719_device_matrix_warp_demo_sample_outdoor_car_jetson_post_geometry_identity_first_grid_compare.mp4
```

## Codec And Color Baseline

An identity/no-matrix MMAPI transcode was measured on Jetson to estimate the
pixel-diff floor introduced by decode/encode/colorspace handling:

| Comparison | mean_abs_center_avg | p95_abs_center_avg | Meaning |
|---|---:|---:|---|
| source vs identity transcode | 25.664099 | 97.133333 | codec/colorspace/dataflow diff floor |
| CPU stabilized vs identity transcode | 28.214566 | 107.591667 | CPU processing plus transcode baseline |
| CPU stabilized vs best device candidate | 30.241568 | 115.866667 | only modestly above the transcode floor |

This changes the interpretation of pixel diff:

```text
The best device output is not pixel-equivalent to CPU output, but most of the
remaining pixel difference is now close to the transcode/color baseline. Future
work should use visual review plus targeted region checks, not raw pixel diff
alone.
```

## Border And Interpolation Boundary

The installed VPI headers on Jetson show that `vpiSubmitPerspectiveWarp` accepts
only `VPI_BORDER_ZERO` for the border argument:

```text
PerspectiveWarp accepted border extensions:
  VPI_BORDER_ZERO
```

So the current VPI path cannot directly reproduce OpenCV
`cv2.BORDER_REFLECT`. Interpolation supports `NEAREST`, `LINEAR`, and
`CATMULL_ROM`; `CATMULL_ROM` was tested and rejected because it roughly doubled
VPI warp time while worsening the CPU-vs-device diff.

## Reproduction Chain

The recorded Jetson-side artifacts are:

```text
/home/nvidia/orin-nx-project/_mmapi_work/jetson_multimedia_api/data/Video/sample_outdoor_car_1080p_10fps.h264
/home/nvidia/orin-nx-project/results/same_source_matrix_20260719/source_120f.mp4
/home/nvidia/orin-nx-project/results/same_source_matrix_20260719/matrices.csv
/home/nvidia/orin-nx-project/results/same_source_matrix_20260719/matrices_inverse.csv
/home/nvidia/orin-nx-project/results/same_source_matrix_20260719/device_matrix_inverse_120f.h264
```

The matrix inversion step is reproducible with:

```powershell
py -3.12 scripts\invert_matrix_csv.py `
  --input results\same_source_matrix_20260719\matrices.csv `
  --output results\same_source_matrix_20260719\matrices_inverse.csv
```

This was checked locally against the recorded inverse CSV:

```text
rows_a=119
rows_b=119
max_abs_diff=0.0
```

Jetson-side rerun template, after copying or creating a patched
`16_multivideo_transcode` sample:

```bash
cd /home/nvidia/orin-nx-project

python3 scripts/patch_mmapi_vpi_transcode_scratch_warp.py \
  --sample-dir /home/nvidia/orin-nx-project/_mmapi_work/jetson_multimedia_api/samples/16_multivideo_transcode_device_matrix

cd /home/nvidia/orin-nx-project/_mmapi_work/jetson_multimedia_api/samples/16_multivideo_transcode_device_matrix
make

export VPI_MATRIX_CSV=/home/nvidia/orin-nx-project/results/same_source_matrix_20260719/matrices_inverse.csv
./multivideo_transcode \
  -i /home/nvidia/orin-nx-project/_mmapi_work/jetson_multimedia_api/data/Video/sample_outdoor_car_1080p_10fps.h264 \
  -o /home/nvidia/orin-nx-project/results/same_source_matrix_20260719/device_matrix_inverse_120f.h264
```

The exact `multivideo_transcode` CLI flags depend on the copied Jetson
Multimedia API sample version. Use the recorded logs as the verifier, not this
template alone:

```text
VPI_MATRIX_LOADED ... matrices_inverse.csv count=119
VPI_TRANSCODE_WARP ...
App run was successful
```

The local evidence paths are:

```text
results/same_source_matrix_20260719/device_matrix_inverse.log
results/same_source_matrix_20260719/device_matrix_inverse_profile.log
results/same_source_matrix_20260719/sanity/frame_sanity.csv
results/same_source_matrix_20260719/sanity/frame_sanity_inverse.csv
results/device_matrix_warp_demo_20260719/panel_video_diff_cpu_vs_device/correctness_summary.csv
results/device_matrix_warp_demo_20260719/triptych_cpu_vs_device/summary.md
results/device_matrix_warp_demo_20260719/triptych_raw_vs_cpu/summary.md
results/device_matrix_warp_demo_20260719/triptych_raw_vs_device/summary.md
results/device_matrix_warp_demo_20260719/timing_inverse_profile/summary.md
results/device_matrix_warp_demo_20260719/timing_inverse/summary.md
results/device_matrix_warp_demo_20260719/timing_scratch_transform/summary.md
results/device_matrix_warp_demo_20260719/timing_aligned_identity_first/summary.md
results/device_matrix_warp_demo_20260719/timing_post_geometry/summary.md
results/device_matrix_warp_demo_20260719/direct_video_diff_cpu_vs_aligned_identity_first/correctness_summary.csv
results/device_matrix_warp_demo_20260719/direct_video_diff_cpu_vs_post_geometry/correctness_summary.csv
results/device_matrix_warp_demo_20260719/direct_video_diff_cpu_vs_post_geometry_identity_first/correctness_summary.csv
results/device_matrix_warp_demo_20260719/jetson_diff_source_vs_identity_transcode/correctness_summary.csv
results/device_matrix_warp_demo_20260719/jetson_diff_cpu_vs_identity_transcode/correctness_summary.csv
results/device_matrix_warp_demo_20260719/jetson_diff_cpu_vs_post_geometry_idfirst_catmull/correctness_summary.csv
```

Local panel-diff command:

```powershell
py -3.12 scripts\compare_triptych_regions.py `
  --input "C:\Users\Admin\Videos\orin nx\review\performance\20260719_same_source_matrix_device_warp\20260719_same_source_matrix_device_warp_raw_cpu_device_compare.mp4" `
  --columns 3 `
  --left-index 1 `
  --right-index 2 `
  --left-label cpu_stabilized `
  --right-label device_inverse `
  --out-dir results\device_matrix_warp_demo_20260719\triptych_cpu_vs_device `
  --max-frames 120 `
  --sample-frames 0,30,60,90
```

## Correct Wording

```text
I moved beyond Python readback experiments and validated a C++ Jetson Multimedia
API path where decoded NV12 frames are transformed into a VPI-compatible scratch
buffer, warped by VPI CUDA, converted back to the encoder's block-linear path,
and encoded by NVENC. The current run uses offline CPU-generated inverse
matrices, so it proves the device-side warp/encode path, not a full real-time
EIS pipeline.
```

## Claims To Avoid

```text
This is real-time full EIS.
The device output is pixel-equivalent to CPU stabilized output.
The CPU crop, dynamic zoom, Lanczos resize, and sharpen stages are already
reproduced on device.
The result proves full-pipeline VPI acceleration.
```

## Next Step

There are two valid next paths after reviewing the post-geometry identity-first
video:

1. Keep `post_geometry_identity_first` as the current device-side stage demo
   candidate.
2. Continue parity work only if the next scoped change targets a clear remaining
   gap, such as border workaround or colorspace/encoding differences. Do not
   spend more time on Catmull-Rom interpolation.

Do not move to real-time motion estimation yet. The current evidence says device
geometry parity is improving, but CPU-output equivalence is still not achieved.
