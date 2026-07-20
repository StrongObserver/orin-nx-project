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
outdoor-car smoke:
  offline matrix warp/encode path works, but not EIS quality evidence.

Regular05 EIS replay:
  source_to_dest convention fixed device black borders.
  black_border_p95 = 0.000972005
  CPU-vs-device mean_abs_center_avg = 4.512432

Regular05 FIFO handoff:
  Python producer / CSV stream -> FIFO -> MMAPI/VPI/NVENC consumer works.
  fallback_count = 0, frame_index_mismatch_count = 0
  VPI warp running avg at frame 100 = 0.647185 ms
  stream black_border_p95 = 0

Regular05 producer alignment:
  fixed CSV through FIFO is pixel-identical to fixed replay.
  original live producer gap = 35.890052 px mean translation.
  offline LP-rigid upper bound gap = 0.501640 px mean translation.

Regular gate inclusion viewport:
  safe103_crop98 failed as a general five-clip producer.
  geometry-valid coverage = 5/5, p95/max invalid ratio = 0.
  The first MMAPI EGL pitch-wrapper VPI output was rejected because non-identity
  matrices caused block-like tearing.
  VPI Python allocated-image output with explicit BGR8 input fixes the visible
  tearing and the green/cyan color shift on all five Regular clips.
  The user accepted all five BGR8 review grids, so it is now the frozen visual
  correctness candidate for Regular gate inclusion.

C++ EGLImage-wrapper candidate:
  Replacing the manual CUDA pitch-pointer wrapper with VPI EGLImage wrappers on
  pitch-linear NvBuffer scratch surfaces ran all five Regular inclusion matrices
  with rc=0, fallback=0, and no sampled frame-index mismatch. The user accepted
  the five review grids, so this is the frozen C++ MMAPI/VPI/NVENC path for
  Regular gate inclusion.

EGLImage timing boundary:
  Regular05 C++ path wall time was about 2002 ms for 180 frames. VPI warp-only
  avg was about 1.55 ms, while the larger EGLImage scratch-buffer stage averaged
  about 10.5 ms. The next performance target is dataflow, not the warp kernel.

Wrapper reuse boundary:
  VPI stream reuse is safe, but EGLImage image-wrapper reuse is closed for this
  MMAPI path after single-wrapper, per-buffer, input-only, output-only,
  persistent-mapping, and explicit-sync variants failed or tore. The next target
  is NvBufSurfTransform/dataflow cost.

Transform cost probe:
  Three NvBufSurfTransform calls cost about 2.7 ms steady-state on Regular05,
  so the full EGLImage stage cost is not explained by transforms alone. The next
  target is wrapper/map/submit/sync overhead around VPI.

EGL map probe:
  EGLImage map/unmap is small, about 0.14 ms combined at the frame-100 sample.
  The remaining cost is more likely VPI wrapper creation plus submit/sync.

Wrapper lifecycle:
  Creating and destroying the input/output VPI EGLImage wrappers costs about
  3.7 ms at frame 100, with a large first-frame initialization spike. This is a
  real cost, but image-wrapper reuse was unsafe in this MMAPI path.

Identity warp:
  Identity PerspectiveWarp is only slightly faster than the inclusion matrix
  path, so matrix complexity is not the current bottleneck.

Surface formats:
  Main DMABUF and VPI scratch differ in color format, layout, and pitch. Direct
  NvBuffer wrapping must use a format-matched pair; the current mismatch explains
  the earlier direct-wrap failure.

Block-linear probe:
  VPI rejected the tested block-linear scratch pairs, including full-range
  NV12_ER. The current VPI-compatible scratch format remains pitch-linear
  NV12_ER.

Pitch encoder probe:
  Pitch-linear main-chain encoding returned success but produced near-solid
  green output. The current block-linear main chain plus pitch-linear VPI scratch
  sandwich is a hard boundary for this stage.

Producer matrices on C++ path:
  Fixed replay, offline-LP, and delay90 Regular05 matrices all ran through the
  accepted C++ EGLImage consumer with rc=0, fallback=0, mismatch=0, and
  black-border p95 below 1%. Next step is concurrent FIFO/live streaming.

Concurrent FIFO/live:
  The FIFO-enabled accepted consumer also handled fixed CSV, delay90 CSV, and
  concurrent live delay90 matrices with healthy handoff and black-border gates.
  The live run took about 68.7 s for 180 frames, making producer compute the
  next bottleneck.
```

Conclusion:

```text
Python-in-the-loop GStreamer EIS integration is not the next acceleration path;
the current acceleration frontier is the C++ device-side MMAPI/VPI/NVENC path.
The next unresolved issue is bounded-delay live producer quality, not FIFO
delivery.
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
path now has a Regular05 source_to_dest replay checkpoint.
```

## Evidence

```text
docs/stage_result_regular_performance_baseline_2026-07-18.md
docs/challenge_boundary_report_2026-07-18.md
docs/vpi_warp_module_report_2026-07-18.md
docs/presentation/hardware_acceleration_boundary.md
docs/device_matrix_warp_demo_2026-07-19.md
docs/regular05_hybrid_matrix_handoff_2026-07-20.md
docs/regular05_live_producer_alignment_2026-07-20.md
docs/regular_gate_inclusion_validation_2026-07-20.md
docs/regular_gate_vpi_distortion_fix_2026-07-20.md
```
