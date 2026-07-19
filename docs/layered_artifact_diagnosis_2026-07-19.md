# Layered Artifact Diagnosis - 2026-07-19

## Purpose

Diagnose the user-observed "gradually distorted / mosaic-like" device output in
the matrix handoff videos.

The key correction:

```text
sample_outdoor_car_1080p_10fps is not an EIS quality clip.
It is only a dataflow / handoff / MMAPI smoke source.
```

It is mostly fixed-view video with moving foreground objects. It should not be
used to prove stabilization quality.

## Layered Diagnosis On Outdoor Car

The same `source_120f.h264` was tested through three layers:

| Layer | Meaning | mean_abs_center_avg vs source | Decision |
|---|---|---:|---|
| MMAPI pass-through | decode -> encode, no VPI patch | 4.952358 | clean enough |
| VPI identity matrix | VPI warp path with identity matrices | 4.983676 | VPI identity path is clean enough |
| post_geometry_identity_first | accepted device matrix warp | 24.415487 vs VPI identity | artifact comes from matrix/geometry on this source |

Interpretation:

```text
The visible accumulation is not mainly caused by encoder pass-through or VPI
identity warp. It appears when nontrivial post-geometry matrices are applied to
this mostly static / foreground-motion source.
```

So the outdoor-car result should be described as:

```text
device dataflow and matrix handoff are validated;
this source is not valid EIS quality evidence;
post_geometry matrices on this source can create misleading accumulated warp.
```

## Regular05 Replay

The same device replay idea was repeated on a real NUS Regular clip:

```text
results/nus_regular_gate_v1/raw_clips/regular_gate05_regular_6.mp4
```

CPU baseline and matrix export were regenerated on Jetson with the frozen
`lp_rigid_strength080_dynzoom106` config.

Device replay:

```text
results/regular05_device_replay_20260719/remote_outputs/device_regular05_postgeom_idfirst.h264
```

Evidence:

| Metric | Value |
|---|---:|
| frames compared | 180 |
| CPU-vs-device mean_abs_center_avg | 35.618840 |
| source-vs-device mean_abs_center_avg | 28.838916 |
| VPI warp avg at frame 100 | 0.552255 ms |

Review copy:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260719_regular05_device_replay\20260719_regular05_device_replay_regular_gate05_regular_6_jetson_source_cpu_device_grid.mp4
```

Interpretation:

```text
Regular05 is the correct type of source for EIS quality review. The first
Regular05 device replay exposed a severe matrix-convention problem: the inverse
matrix convention used for outdoor-car produced large black borders on the real
EIS clip.
```

## Regular05 Matrix Direction Fix

The Regular05 device replay was rerun with `source_to_dest` matrix convention
instead of inverse convention:

```text
results/regular05_device_replay_20260719/remote_outputs/device_regular05_postgeom_idfirst_forward.h264
```

| Output | black p95 | black max | CPU-vs-device mean_abs_center_avg | VPI warp avg at frame 100 | Decision |
|---|---:|---:|---:|---:|---|
| inverse convention | 0.281428602 | 0.282070312 | 35.618840 | 0.552255 ms | reject |
| source_to_dest convention | 0.000972005 | 0.006250000 | 4.512432 | 0.615782 ms | current fixed replay |

Review copy:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260719_regular05_device_replay\20260719_regular05_device_replay_regular_gate05_regular_6_jetson_source_cpu_bad_fixed_grid.mp4
```

Interpretation:

```text
The Regular05 black-border issue was caused primarily by using the wrong matrix
direction for VPI PerspectiveWarp on this device replay path. For the real EIS
Regular05 replay, source_to_dest convention is the correct current convention.
```

## Current Boundary

Keep these roles separate:

```text
sample_outdoor_car:
  dataflow smoke
  matrix handoff smoke
  MMAPI/VPI/NVENC path validation

regular_gate05_regular_6:
  real EIS quality review
  device replay visual check
  current device replay convention: source_to_dest
```

Do not use `sample_outdoor_car` as a stabilization-quality claim.

## Next Step

The next decision should come from visual review of the Regular05 device replay:

```text
If Regular05 device replay is visually acceptable:
  use it as the device-side replay quality checkpoint.

If Regular05 device replay shows accumulated warp or artifacts:
  inspect matrix convention / post-geometry composition on the real EIS clip.

Do not continue optimizing the outdoor-car output for EIS quality.
```
