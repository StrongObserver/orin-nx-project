# Device-Stage Lifecycle/Dataflow V2 - 2026-07-23

## Decision

This loop produced two useful engineering outcomes and one bounded negative
result.

Benefits:

```text
1. Remap NvBuffer wrapper is viable:
   VPI Remap pad/crop can run through VPI_IMAGE_BUFFER_NVBUFFER wrappers on
   format-matched pitch-linear NV12_ER scratch buffers.

2. Remap NvBuffer wrapper preserved diagnostic output semantics:
   identity output matched the EGLImage baseline exactly in the direct diff,
   and identity/wave_safe both had black-border p95 = 0.

3. Five-Regular stream-only PerspectiveWarp safety check passed:
   all five Regular clips returned rc=0, fallback=0, and frame-index mismatch=0.
```

Bounded negative result:

```text
Remap pad/crop stream-only reuse was healthy but did not improve timing.
The PerspectiveWarp stream-only lifecycle win does not directly transfer to
Remap pad/crop in this single-run diagnostic.
```

Claim boundary:

```text
This is device-stage lifecycle/dataflow evidence. It is not zero-copy, not full
real-time EIS, not Remap EIS quality improvement, and not a proof that queue
depth or double buffering would help.
```

## Frozen Scope

```text
source:
  results/regular_gate_safe103_crop98_validation_20260720/<clip>/source.h264

quality/device matrices:
  results/regular_gate_nvbuffer_pair_resid_20260723/<clip>/resid_r15_s07.csv

Remap diagnostic source:
  regular_gate05_regular_6 source.h264

main chain:
  640x360 block-linear NV12 decode/encode

VPI scratch:
  pitch-linear NV12_ER
  Remap pad/crop scratch 640x368
```

## P1 - Remap Pad/Crop Stream-Only Reuse

Tracked patch:

```text
scripts/patch_mmapi_vpi_transcode_eglimage_remap_stream_reuse_pad_crop.py
```

Compared against the existing EGLImage Remap pad/crop baseline.

| Mode | Path | rc | Remap Avg | Stage Frame100 | Stage Avg | Black P95 | Identity Diff |
|---|---|---:|---:|---:|---:|---:|---:|
| identity | EGLImage baseline | 0 | 1.614520 ms | 8.196200 ms | 11.039800 ms | 0.000000000 | reference |
| identity | stream-only reuse | 0 | 2.090140 ms | 10.598200 ms | 11.704200 ms | 0.000000000 | 0 |
| wave_safe | EGLImage baseline | 0 | 1.652440 ms | 7.269890 ms | 10.751300 ms | 0.000000000 | n/a |
| wave_safe | stream-only reuse | 0 | 1.996950 ms | 10.073000 ms | 11.785700 ms | 0.000003906 | n/a |

Interpretation:

```text
Stream-only reuse is safe for Remap pad/crop output readability, but it does not
improve timing in this run. Keep it as negative transfer evidence, not as an
accepted Remap optimization.
```

## P2 - Five-Regular Stream-Only Safety Extension

The accepted PerspectiveWarp stream-only lifecycle route was extended across the
five Regular clips with the accepted `resid_r15_s07` matrices.

| Clip | rc | Fallback | Mismatch | Warp Avg | Stage Avg | Black P95 | Black Max | Frames > 1% |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| regular_gate01_regular_10 | 0 | 0 | 0 | 1.683600 ms | 9.960280 ms | 0.010199653 | 0.014561632 | 10 |
| regular_gate02_regular_19 | 0 | 0 | 0 | 1.935790 ms | 8.197080 ms | 0.004552518 | 0.008524306 | 0 |
| regular_gate03_regular_13 | 0 | 0 | 0 | 1.758080 ms | 10.576800 ms | 0.000243056 | 0.003537326 | 0 |
| regular_gate04_regular_8 | 0 | 0 | 0 | 1.589150 ms | 9.861810 ms | 0.002896484 | 0.009049479 | 0 |
| regular_gate05_regular_6 | 0 | 0 | 0 | 1.605700 ms | 9.785990 ms | 0.000673177 | 0.005598958 | 0 |

Interpretation:

```text
Stream-only reuse remains device-consumer healthy across the Regular gate.
Regular01 is still metric-conditional because the gray black-border metric is
sensitive to dark edge content; this mirrors earlier Regular01 behavior and does
not by itself prove a new visual regression.
```

Review copy:

```text
C:\Users\Admin\Videos\orin nx\review\diagnostic\20260723_device_stage_lifecycle_dataflow_v2\20260723_regular_gate_stream_reuse_resid_5clip_grid.mp4
```

## P3 - Remap NvBuffer Wrapper Diagnostic

Tracked patch:

```text
scripts/patch_mmapi_vpi_transcode_nvbuffer_remap_pad_crop_probe.py
```

Result:

```text
VPI Remap accepts VPI_IMAGE_BUFFER_NVBUFFER wrappers for this format-matched
pitch-linear NV12_ER scratch pair.
```

| Mode | rc | Remap Avg | Stage Frame100 | Stage Avg | Black P95 | Baseline Identity Diff |
|---|---:|---:|---:|---:|---:|---:|
| identity | 0 | 1.568190 ms | 7.678090 ms | 10.433000 ms | 0.000000000 | 0 |
| wave_safe | 0 | 1.529150 ms | 6.330020 ms | 10.387900 ms | 0.000000000 | n/a |

Compared with the EGLImage Remap baseline:

| Mode | EGLImage Stage Avg | NvBuffer Stage Avg | Change |
|---|---:|---:|---:|
| identity | 11.039800 ms | 10.433000 ms | +5.50% |
| wave_safe | 10.751300 ms | 10.387900 ms | +3.38% |

Interpretation:

```text
This is the useful positive result of the loop. Remap is not limited to the
EGLImage wrapper path; a format-matched NvBuffer wrapper path is viable and
shows small stage-average improvement in this diagnostic.
```

Review copy:

```text
C:\Users\Admin\Videos\orin nx\review\diagnostic\20260723_device_stage_lifecycle_dataflow_v2\20260723_remap_nvbuffer_regular05_jetson_grid.mp4
```

## P4 - Activity Check

The activity check wrapped wave_safe EGLImage Remap and NvBuffer Remap with
`tegrastats --interval 100`.

| Case | rc | Wall | Remap Avg | Stage Avg | Stage Frame100 | Samples | GR3D Avg | GR3D Max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| EGLImage Remap wave_safe | 0 | 1.914553 s | 1.551030 ms | 10.359700 ms | 7.432840 ms | 20 | 25.800% | 42% |
| NvBuffer Remap wave_safe | 0 | 1.924300 s | 1.597530 ms | 10.355000 ms | 7.436430 ms | 20 | 25.800% | 43% |

Interpretation:

```text
Under this bounded activity wrapper, EGLImage and NvBuffer Remap are effectively
tied. This is activity evidence only. It does not support a FPS/W claim because
no reliable INA rail power was collected in this loop.
```

## Evidence

Local ignored evidence:

```text
results/device_stage_lifecycle_dataflow_v2_20260723/
```

Review copies:

```text
C:\Users\Admin\Videos\orin nx\review\diagnostic\20260723_device_stage_lifecycle_dataflow_v2\20260723_remap_stream_reuse_regular05_jetson_grid.mp4
C:\Users\Admin\Videos\orin nx\review\diagnostic\20260723_device_stage_lifecycle_dataflow_v2\20260723_remap_nvbuffer_regular05_jetson_grid.mp4
C:\Users\Admin\Videos\orin nx\review\diagnostic\20260723_device_stage_lifecycle_dataflow_v2\20260723_regular_gate_stream_reuse_resid_5clip_grid.mp4
```

## Next Boundary

Allowed next step:

```text
Treat NvBuffer Remap pad/crop as a viable diagnostic dataflow alternative and
reuse it only when a future dynamic Remap/mesh model has a real quality
verifier.
```

Do not do:

```text
Do not claim Remap improves EIS quality.
Do not claim zero-copy.
Do not open broad queue-depth/double-buffering work from this evidence alone.
```
