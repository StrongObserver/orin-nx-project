# Remap Native-Size Pad/Crop Probe - 2026-07-23

## Decision

The native-size Remap-MMAPI size boundary is closed for a minimal diagnostic
path.

Result:

```text
Regular05 native source:
  main decode/encode chain stays 640x360 block-linear NV12
  VPI scratch stage is padded to 640x368 pitch-linear NV12_ER
  VPI Remap payload/grid is 640x368
  output is transformed/cropped back to 640x360 main chain before NVENC

identity mode:
  rc=0, readable output, 180 frames read by validation scripts

wave_safe mode:
  rc=0, readable output, 180 frames read by validation scripts
```

This is a size/layout/dataflow diagnostic result. It is not Regular EIS quality,
not mesh/local-warp stabilization, not zero-copy, and not full-pipeline
acceleration.

## Why This Was Needed

The previous Remap-MMAPI probe proved that Remap could replace PerspectiveWarp
inside a diagnostic MMAPI/VPI/NVENC sample when the source was padded to
640x368.

The missing native-size question was:

```text
Can the encoder-facing main chain remain 640x360 while only the VPI scratch
stage is padded to the WarpGrid-compatible 640x368 size?
```

This matters because the accepted device path should not change the main
decode/encode surface shape just to satisfy a VPI Remap payload size rule.

## Implementation

Tracked patch script:

```text
scripts/patch_mmapi_vpi_transcode_eglimage_remap_pad_crop_probe.py
```

Remote diagnostic sample:

```text
/home/nvidia/orin-nx-project/_mmapi_work/jetson_multimedia_api/samples/99_vpi_transcode_matrix_eglimage_remap_pad_crop_probe/
```

Input:

```text
/home/nvidia/orin-nx-project/results/regular_gate_safe103_crop98_validation_20260720/regular_gate05_regular_6/source.h264
```

The patch keeps the encoder-facing `ctx->width` / `ctx->height` at 640x360, but
allocates pitch-linear NV12_ER scratch buffers with aligned dimensions:

```text
REMAP_PAD_CROP_SCRATCH_ALLOC main_width=640 main_height=360 scratch_width=640 scratch_height=368
```

The VPI Remap payload is then created at the scratch size:

```text
VPI_REMAP_PAD_CROP_PAYLOAD_READY mode=identity width=640 height=368 grid_width=640 grid_height=368 points=41x25
VPI_REMAP_PAD_CROP_PAYLOAD_READY mode=wave_safe width=640 height=368 grid_width=640 grid_height=368 points=41x25
```

## Timing

Evidence:

```text
results/remap_native_size_pad_crop_probe_20260723/
```

| Mode | rc | Remap Frame100 | Remap Running Avg | Input Transform | Wrapper Call | Output Transform | Stage Frame100 | Stage Running Avg |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| identity | 0 | 1.594870 ms | 1.614520 ms | 0.940161 ms | 6.068380 ms | 1.063240 ms | 8.196200 ms | 11.039800 ms |
| wave_safe | 0 | 1.575290 ms | 1.652440 ms | 0.869247 ms | 5.302210 ms | 1.009250 ms | 7.269890 ms | 10.751300 ms |

The first frame still has a large initialization spike, consistent with the
previous EGLImage and Remap diagnostic probes. The steady-state lesson is the
same as the Nsight/NVTX work: the cost is dominated by wrapper/sync/transform
lifecycle, not only by the Remap kernel.

## Readability And Black Border

The output videos were downloaded back to Windows and checked with project
scripts.

Edge-connected near-black border summary, threshold 8:

| Video | Frames | Mean Black Border | P95 Black Border | Max Black Border | Frames > 0.001 |
|---|---:|---:|---:|---:|---:|
| source | 180 | 0.000000121 | 0.000000000 | 0.000008681 | 0 |
| identity pad/crop | 180 | 0.000000217 | 0.000000000 | 0.000013021 | 0 |
| wave_safe pad/crop | 180 | 0.000000000 | 0.000000000 | 0.000000000 | 0 |

Identity-vs-source diff sanity:

| Frames | Mean Abs All | P95 Abs All | Mean Abs Center | P95 Abs Center | Max Abs All | Max Abs Center |
|---:|---:|---:|---:|---:|---:|---:|
| 180 | 2.294825 | 5.922222 | 2.426476 | 6.111111 | 47 | 31 |

Interpretation:

```text
The native-size pad/crop path is readable and does not introduce a large
black-border regression in identity mode. The remaining small identity diff is a
codec/dataflow sanity difference, not a geometry collapse.
```

## Review Evidence

Project-local ignored review asset:

```text
results/remap_native_size_pad_crop_probe_20260723/review/remap_native_pad_crop_source_identity_wavesafe_grid.mp4
```

User-review copy:

```text
C:\Users\Admin\Videos\orin nx\review\diagnostic\20260723_remap_native_size_pad_crop_probe\20260723_remap_native_size_pad_crop_regular05_jetson_source_identity_wavesafe_grid.mp4
```

Panel order:

```text
source / identity_pad_crop / wave_safe_pad_crop
```

## Boundary

Allowed claim:

```text
The VPI Remap scratch-stage size issue can be handled without changing the
encoder-facing 640x360 main chain: pad only the pitch-linear VPI scratch stage
to 640x368, run Remap, then crop/transform back to the native main chain.
```

Not allowed:

```text
Remap improves EIS quality.
Remap solves mesh/local-warp stabilization.
This proves full-pipeline acceleration.
This proves zero-copy.
This changes the accepted resid_r15_s07 quality anchor.
```

## Next Boundary

This result makes Remap a cleaner future device-stage operator option, but it
does not reopen the static local-warp correction route. A serious quality route
would need a dynamic mesh/depth/RS/gyro model and a separate contract.
