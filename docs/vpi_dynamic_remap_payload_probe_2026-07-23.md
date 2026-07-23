# VPI Dynamic Remap Payload Probe - 2026-07-23

## Decision

Dynamic VPI Remap is technically viable, including inside the current
MMAPI/VPI/NVENC native-size pad/crop shape, but it has a material per-frame
payload rebuild cost.

Benefits:

```text
1. The API boundary is now clear:
   VPI Remap exposes vpiCreateRemap(payload from VPIWarpMap) and vpiSubmitRemap,
   but no separate payload/map update API was found in the local VPI C headers.

2. Standalone dynamic payload rebuild works:
   BGR8 and NV12_ER both ran with per-frame WarpMap/payload rebuild.

3. Matrix-to-WarpMap direction is validated:
   Remap maps output coordinates back into input coordinates. For a source_to_dest
   EIS matrix, fill WarpMap keypoints with inverse(matrix) applied to output
   grid points.

4. MMAPI dynamic Remap works:
   EGLImage and NvBuffer dynamic Remap pad/crop both ran 180 frames with rc=0.
```

Boundary:

```text
This is operator/dataflow evidence. It does not prove EIS quality improvement,
mesh/local-warp stabilization, zero-copy, or full real-time EIS.
```

## API Boundary

Local VPI 2.2 headers expose:

```text
vpiCreateRemap(uint64_t backends, const VPIWarpMap *warpMap, VPIPayload *payload)
vpiSubmitRemap(VPIStream stream, uint64_t backend, VPIPayload payload, ...)
```

No API was found to update a Remap payload in place after creation. The measured
dynamic route in this loop is therefore:

```text
per frame:
  allocate/fill VPIWarpMap
  vpiCreateRemap
  vpiSubmitRemap + vpiStreamSync
  vpiPayloadDestroy
  vpiWarpMapFreeData
```

This is conservative and measurable. It may not be the only possible industrial
route, but it is the local VPI C API route available in this project.

## Standalone Dynamic Remap

Tracked source:

```text
experiments/vpi_cpp_remap_dynamic_probe/dynamic_remap_probe.cpp
```

Evidence:

```text
results/vpi_dynamic_remap_payload_probe_20260723/standalone/
```

640x368, CUDA backend, 180 frames:

| Format | Mode | Map Build Avg | Payload Create Avg | Submit/Sync Avg | Payload Destroy Avg | Total Avg |
|---|---|---:|---:|---:|---:|---:|
| BGR8 | static payload | 0.000223 ms | 0.012636 ms | 0.839550 ms | 0.000000 ms | 0.839870 ms |
| BGR8 | dynamic recreate payload | 0.039433 ms | 1.544170 ms | 0.457110 ms | 0.207204 ms | 2.250150 ms |
| NV12_ER | static payload | 0.000178 ms | 0.009695 ms | 0.181342 ms | 0.000000 ms | 0.181523 ms |
| NV12_ER | dynamic recreate payload | 0.062102 ms | 2.155590 ms | 0.411961 ms | 0.279786 ms | 2.913010 ms |

Interpretation:

```text
The dynamic route works, but payload creation dominates. For NV12_ER at 640x368,
dynamic recreate is roughly 2.91 ms/frame versus 0.18 ms/frame for static
payload reuse in this standalone probe.
```

## Matrix-To-WarpMap Direction

Tracked source:

```text
experiments/vpi_cpp_remap_dynamic_probe/matrix_remap_direction_probe.cpp
```

Evidence:

```text
results/vpi_dynamic_remap_payload_probe_20260723/matrix_direction/
```

| Matrix | Mean Abs vs OpenCV Remap | Max Abs | Decision |
|---|---:|---:|---|
| identity | 0.000000 | 0 | exact match |
| translate | 0.000000 | 0 | exact match |
| scale_rotate | 0.180803 | 255 | direction correct; edge/interpolation differences remain |

Interpretation:

```text
VPIWarpMap stores input sampling coordinates for each output grid point.
For source_to_dest matrices, use inverse(matrix) when filling Remap keypoints.
```

## MMAPI Dynamic Remap

Tracked patch:

```text
scripts/patch_mmapi_vpi_transcode_eglimage_dynamic_remap_pad_crop.py
scripts/patch_mmapi_vpi_transcode_nvbuffer_dynamic_remap_pad_crop.py
```

Evidence:

```text
results/vpi_dynamic_remap_payload_probe_20260723/mmapi_dynamic_eglimage/
results/vpi_dynamic_remap_payload_probe_20260723/mmapi_dynamic_nvbuffer/
```

Both routes keep the native-size pad/crop boundary:

```text
main chain: 640x360 block-linear NV12
VPI scratch: 640x368 pitch-linear NV12_ER
mode: wave_safe dynamic map
frames: 180
```

| Path | rc | Remap Avg | Payload Create Frame100 | Stage Frame100 | Stage Avg | Black P95 |
|---|---:|---:|---:|---:|---:|---:|
| EGLImage dynamic Remap | 0 | 1.586130 ms | 1.761130 ms | 9.847630 ms | 13.139300 ms | 0.002375217 |
| NvBuffer dynamic Remap | 0 | 1.550540 ms | 1.878210 ms | 10.830800 ms | 13.159600 ms | 0.002375217 |

Direct EGLImage-vs-NvBuffer dynamic output diff:

```text
frames_compared=180
mean_abs_center_avg=0
p95_abs_center_avg=0
max_abs_center=0
```

Review copy:

```text
C:\Users\Admin\Videos\orin nx\review\diagnostic\20260723_vpi_dynamic_remap_payload_probe\20260723_dynamic_remap_regular05_eglimage_nvbuffer_grid.mp4
```

Interpretation:

```text
Dynamic Remap is viable in the MMAPI pad/crop shape, but stage average rises to
about 13.1 ms because payload rebuild is now part of the per-frame path.
NvBuffer remains output-equivalent to EGLImage, but in the dynamic route it does
not recover the payload rebuild cost.
```

## What This Means

Allowed claim:

```text
The project measured the cost of moving Remap from static diagnostic maps to
per-frame dynamic maps. The dynamic route works, but per-frame payload rebuild is
a material cost that must be considered before opening a real mesh/local-warp EIS
quality loop.
```

Do not claim:

```text
Dynamic Remap improves EIS quality.
Mesh/local-warp stabilization is solved.
This is zero-copy.
This proves full real-time EIS.
```

## Next Boundary

The next quality-oriented route should not start with a full MMAPI mesh
implementation. It should first answer one of these narrower questions:

```text
1. Is there a lower-cost VPI/CUDA method to update dynamic map data without
   rebuilding a Remap payload every frame?
2. Would a custom CUDA warp kernel be a better fit for per-frame mesh updates?
3. Can a dynamic mesh model produce a measurable quality gain on a selected
   parallax/RS boundary before paying the MMAPI integration cost?
```

If this road fork must be decided for production-style design, use the internal
AI prompt from the oral-template planning discussion and ask specifically about
dynamic mesh warp implementation on Jetson/VPI/CUDA/MMAPI.
