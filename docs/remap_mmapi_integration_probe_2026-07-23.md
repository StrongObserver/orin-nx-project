# Remap MMAPI Integration Probe - 2026-07-23

## Decision

VPI C++ Remap can be inserted into the accepted MMAPI/VPI/NVENC scratch-buffer
shape as a diagnostic operator, after respecting VPI WarpGrid size constraints.

Result:

```text
640x360 source:
  fails because WarpGrid height is aligned to 368 and Remap requires output size
  to match the warp map.

640x368 padded diagnostic source:
  identity Remap: rc=0, readable output
  wave Remap:     rc=0, readable output
  wave_safe Remap: rc=0, readable output, edge black-border removed in frame90 check
```

This is an operator/device-stage integration result. It is not EIS quality, not
mesh/local-warp stabilization, not zero-copy, and not full-pipeline acceleration.

## What The Review Video Means

The first triptych showed:

```text
source / Remap identity / Remap wave
```

`Remap identity` does not show stabilization because it is supposed to preserve
the source geometry. It is only a format/dataflow sanity check.

`Remap wave` intentionally applies a local horizontal wave map. It is an
operator diagnostic, not a stabilizer. The visible curved black borders came
from map coordinates sampling outside the input image while Remap used zero
border.

Frame-90 edge-black check from the first review:

| Panel | Left edge black | Right edge black | Meaning |
|---|---:|---:|---|
| source | about 2.17% | about 2.17% | padded source baseline |
| identity | about 2.17% | about 2.17% | no new edge black |
| wave | about 8.39% | about 7.47% | local map samples outside input |

Fix:

```text
wave_safe = local wave map plus FOV-safe centering/scaling before wave offset
```

Frame-90 check after the fix:

| Panel | Total black | Left edge black | Right edge black |
|---|---:|---:|---:|
| source | 0.021769 | 0.021739 | 0.021739 |
| identity | 0.021773 | 0.021739 | 0.021739 |
| wave | 0.031297 | 0.083880 | 0.074703 |
| wave_safe | 0.000004 | 0.000000 | 0.000000 |

Interpretation:

```text
The original wave black border was a map/FOV boundary issue, not Remap-MMAPI
data corruption. wave_safe removes that diagnostic black-border artifact.
```

## Why 640x360 Failed

The first run used the native Regular05 640x360 H264 source.

Failure:

```text
VPI_REMAP_PAYLOAD_READY mode=identity width=640 height=360 grid_width=640 grid_height=368 points=41x25
VPI EGLImage remap failed status=2 msg=Output image must have same size corresponding to the warp map passed during payload creation
```

Cause:

```text
VPI WarpGrid has region alignment requirements.
The 360-pixel height was aligned to 368.
vpiSubmitRemap requires output image size to match the warp map dimensions.
```

Interpretation:

```text
This is a size/alignment boundary, not evidence that MMAPI Remap is impossible.
```

## Successful Diagnostic Run

To isolate the operator/device-stage question, the source was padded to 640x368:

```text
results/remap_mmapi_integration_probe_20260723/source_640x368_pad.h264
```

The patched sample keeps the MMAPI decode/encode structure and pitch-linear
NV12_ER scratch buffers, then replaces `vpiSubmitPerspectiveWarp` with
`vpiSubmitRemap`.

Tracked patch script:

```text
scripts/patch_mmapi_vpi_transcode_eglimage_remap_probe.py
```

Remote diagnostic sample:

```text
/home/nvidia/orin-nx-project/_mmapi_work/jetson_multimedia_api/samples/99_vpi_transcode_matrix_eglimage_remap_probe/
```

## Timing

Evidence:

```text
results/remap_mmapi_integration_probe_20260723/
```

| Mode | rc | Payload | Remap Frame100 | Remap Running Avg | Input Transform | Wrapper Call | Output Transform | Stage Frame100 | Stage Running Avg |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| identity | 0 | 640x368, grid 640x368, 41x25 | 1.584280 ms | 1.589380 ms | 0.928095 ms | 6.505630 ms | 0.956544 ms | 8.529760 ms | 10.524300 ms |
| wave | 0 | 640x368, grid 640x368, 41x25 | 1.630130 ms | 1.591480 ms | 0.919006 ms | 6.322320 ms | 0.943231 ms | 8.323730 ms | 10.573700 ms |
| wave_safe | 0 | 640x368, grid 640x368, 41x25 | 1.512610 ms | 1.544110 ms | 0.851702 ms | 5.427940 ms | 0.894070 ms | 7.278550 ms | 9.769750 ms |

The timings are close to the existing EGLImage/PerspectiveWarp device-stage
range. The cost remains dominated by wrapper/sync/transform/lifecycle rather
than the Remap kernel alone.

## Review Evidence

Review copy:

```text
C:\Users\Admin\Videos\orin nx\review\diagnostic\20260723_remap_mmapi_integration_probe\20260723_remap_mmapi_regular05_jetson_source_identity_wave_triptych.mp4
C:\Users\Admin\Videos\orin nx\review\diagnostic\20260723_remap_mmapi_integration_probe\20260723_remap_mmapi_regular05_jetson_source_identity_wave_wavesafe_quad.mp4
```

Panel order:

```text
old: source 640x368 padded / Remap identity / Remap wave
new: source 640x368 padded / Remap identity / Remap wave / Remap wave_safe
```

This review asset is for operator sanity only. It is not a stabilization-quality
review.

## Integration Boundary

Allowed claim:

```text
VPI Remap can replace PerspectiveWarp in a minimal MMAPI/VPI/NVENC diagnostic
sample when the source dimensions satisfy WarpGrid/output-size requirements.
```

Not allowed:

```text
Remap is integrated into the accepted Regular EIS path.
Remap improves防抖 quality.
Remap proves mesh/local-warp EIS quality.
Remap proves full-pipeline acceleration.
Remap is zero-copy.
VIC Remap is validated.
```

## Next Engineering Route

If this route continues, the next scoped contract should not start with EIS
quality. It should first solve the size/layout question:

```text
Option A: keep diagnostic inputs at WarpGrid-compatible sizes such as 640x368.
Option B: add explicit pad/crop around the VPI Remap stage.
Option C: test native NV12/NV12_ER VIC-compatible input without BGR pre-convert.
```

Only after those are stable should Remap be considered for a real local/mesh
warp experiment.
