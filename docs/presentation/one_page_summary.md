# One-Page Summary

## Project

Jetson Orin NX EIS video stabilization and heterogeneous acceleration project.

Goal:

```text
Build a controllable EIS pipeline, measure quality and latency, optimize the
real bottleneck, and explain both acceleration boundaries and model boundaries.
```

## Current Baselines

```text
quality-safe baseline:
  lp_rigid_strength080_dynzoom106
  estimate_scale=1.0
  feature_grid_size=12

Regular performance baseline:
  lp_rigid_strength080_dynzoom106
  estimate_scale=0.5
  feature_grid_size=16
```

## Main Result

Regular performance baseline:

```text
NUS Regular gate: 5/5 objective pass
Human review: accepted
Regular05 estimate time: 8.568 ms -> 3.022 ms
Regular05 wall time: 8.473 s -> 7.565 s
```

## Hardware Acceleration Boundary

VPI:

```text
640x360 full Python EIS pipeline:
  VPI backend swap is slower than OpenCV CPU.

720p -> 4K warp-heavy module:
  VPI CUDA speedup grows from 1.35x to 2.33x.
```

GStreamer / NVMM:

```text
appsink readback: about 7.93 ms/frame
appsink -> appsrc -> encode pass-through: about 15.81 ms/frame
```

Device-side MMAPI/VPI/NVENC:

```text
offline inverse-matrix warp/encode path works;
not yet full real-time EIS or CPU-output equivalence.
post-geometry + first-frame identity is current best device candidate:
  mean_abs_center_avg vs CPU = 30.241568
identity transcode floor vs source:
  mean_abs_center_avg = 25.664099
```

Conclusion:

```text
Python-in-the-loop GStreamer EIS integration is not the next acceleration path;
the current acceleration frontier is the C++ device-side MMAPI/VPI/NVENC path.
```

## Model Boundary

Challenge-set result:

```text
Running:
  high-frequency motion creates FOV and black-border pressure.

QuickRotation:
  fast rotation exceeds crop/FOV budget.

Parallax:
  one global transform cannot represent depth variation cleanly.

Crowd:
  foreground motion contaminates global estimation.
```

## Best Interview Framing

```text
This is not just a stabilizer demo. I built a measurement loop: Regular is the
in-domain success case, Challenge sets define the model boundary, VPI shows where
hardware acceleration helps, GStreamer/NVMM measurements explain why direct
Python dataflow integration is not currently worthwhile, and the MMAPI/VPI/NVENC
path shows the next device-side integration boundary.
```

## Evidence

```text
docs/stage_result_regular_performance_baseline_2026-07-18.md
docs/challenge_boundary_report_2026-07-18.md
docs/vpi_warp_module_report_2026-07-18.md
docs/presentation/hardware_acceleration_boundary.md
docs/device_matrix_warp_demo_2026-07-19.md
```
