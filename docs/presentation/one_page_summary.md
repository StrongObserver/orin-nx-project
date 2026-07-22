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

High-resolution PerspectiveWarp module:
  1080p: 36.926 ms -> 18.426 ms, 2.00x
  1440p: 29.045 ms -> 15.778 ms, 1.84x
  4K:    69.742 ms -> 27.617 ms, 2.53x

4K stable workload with INA3221 board-input power:
  OpenCV CPU: 48.995 ms, 20.410 FPS, 12.136 W, 1.682 FPS/W
  VPI CUDA:   20.514 ms, 48.747 FPS, 11.118 W, 4.385 FPS/W
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

Regular05 FIFO/live handoff:
  fixed/offline-LP/delay90 CSV, fixed FIFO, delay90 FIFO, and concurrent
  live delay90 all pass through the accepted C++ consumer with rc=0,
  fallback=0, mismatch=0, and black-border p95 below 1%.
  live_delay90 took about 68.7 s for 180 frames, so producer compute/scheduling
  is the next bottleneck.

Producer scheduling optimization:
  repeated LP prefix solving was the dominant live producer cost.
  A new optional lp-prefix stride keeps the original stride1 behavior by
  default. On Jetson Regular05 delay90, stride5 reduced producer-only time from
  about 68.5 s to about 15.7 s for 180 frames, while the accepted EGLImage FIFO
  consumer kept rc=0, fallback=0, mismatch=0, and black-border p95 below 1%.
  Concurrent live stride5 completed in 17.5 s for 180 frames and matched the
  precomputed stride5 output exactly. This is a bounded-delay Regular05
  optimization candidate, not zero-latency full real-time EIS.

Regular gate viewport-stable extension:
  Regular05 safe103_crop98 was accepted by human review as the viewport-stable
  candidate. The same stride5 bounded-delay producer plus fixed-scale/crop98
  viewport rule was extended to all five Regular clips. All five device runs
  have rc=0, fallback=0, and mismatch=0. Four clips pass the gray black-border
  hard gate; Regular01 is conditional because gray p95 is 0.026323350 while
  geometry p95 invalid is 0.000003906.

Pose smoothing:
  Human review then found abrupt translation/rotation jumps. The pose_smooth_r4
  candidate smooths tx/ty/angle while keeping fixed scale and crop98. It ran
  5/5 through the accepted EGLImage FIFO path with rc=0, fallback=0, and
  mismatch=0, and reduces translation p95 on every clip. Human review rejected
  R4 because it weakens stabilization too much. lim8 then tested local delta
  limiting, but the user rejected it because abrupt pose jumps remain. The active
  direction is root-cause recovery for camera-path planning, not another limiter.

Bounded QP and spike-repair history:
  `bqp_w90_s15_w2_20_w3_200` changed only matrix/path generation while keeping
  the accepted C++ EGLImage FIFO consumer fixed. It improved Regular05 matrix
  continuity, but human review found the stabilization too weak. The next
  `spike_mid_t6_b70_r2_i2` candidate preserved 5/5 Jetson FIFO
  rc/fallback/mismatch health and improved Regular05 residual translation mean
  from BQP `3.915` to `2.788`, but it was also rejected as insufficient for the
  current quality target. These candidates are retained as diagnostic history,
  not current review targets.

Residual closed-loop recovery:
  Human review then rejected spike_mid. Residual-grid diagnostics did not show a
  strong local-motion/parallax-only signature, so the mesh route remains closed.
  The current candidate is `resid_r15_s07`: estimate residual motion from
  safe103crop98 output, smooth that residual path, and compose it back into the
  device matrix. It runs five Regular clips through Jetson FIFO with rc=0,
  fallback=0, and mismatch=0. On Regular05, residual trans mean improves to
  `1.033`, stronger than safe103crop98 `2.103`, BQP `3.915`, and spike_mid
  `2.788`. Human review accepted it as visibly stronger than BQP/spike_mid,
  with no hard pose snaps and no visible black borders. This closes the current
  Regular gate stabilization-strength recovery loop.

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
  about 10.5 ms. A later submit/sync probe split the stage further: frame100
  total was about 7.80 ms, with wrapper lifecycle about 3.82 ms, submit+sync
  about 1.53 ms, and input/output transforms about 1.86 ms. VPI submit itself
  was only about 0.02 ms, so the target is wrapper/sync/transform dataflow, not
  the PerspectiveWarp kernel.

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

First-frame amortization:
  The submit/sync probe showed a roughly 245 ms first-frame initialization spike.
  A three-iteration long run reduced wall time from about 12.69 ms/frame for one
  180-frame run to about 9.41 ms/frame, but steady dataflow still remains around
  7.5-8.5 ms/frame.

NvBuffer pair follow-up:
  The current quality anchor is `resid_r15_s07`, not the earlier inclusion or
  safe103 matrices. After the weaker inclusion-matrix review, `resid_r15_s07`
  was run through the format-matched NvBuffer pair path on all five Regular
  clips with rc=0 and fallback=0. Same-source Regular05 EGLImage vs NvBuffer
  comparison aligned exactly in time and geometry after crop98. NvBuffer pair
  preserves the accepted quality anchor and gives a small dataflow-stage gain:
  frame100 stage 7.535 ms -> 7.230 ms, and running average 9.589 ms -> 9.401 ms.
  This is a quality-preserving dataflow improvement, not zero-copy or full
  pipeline acceleration.

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
  black-border p95 below 1%.

Concurrent FIFO/live:
  The FIFO-enabled accepted consumer also handled fixed CSV, delay90 CSV, and
  concurrent live delay90 matrices with healthy handoff and black-border gates.
  The live run took about 68.7 s for 180 frames, making producer compute the
  next bottleneck.

Producer scheduling:
  Profiling showed LP prefix solving, not handoff or VPI warp, was the dominant
  producer cost. Stride5 reduced LP calls from 89 to 19 and Jetson producer-only
  total time from about 68.5 s to about 15.7 s for 180 frames. The stride5 FIFO
  device output kept fallback=0, mismatch=0, VPI warp avg about 1.53 ms, and
  black-border p95=0.000784288. Concurrent live stride5 wall time was 17.5 s
  for 180 frames and produced the same device output as precomputed stride5.

Five Regular viewport-stable check:
  The accepted EGLImage FIFO consumer ran all five stride5 fixed-scale/crop98
  candidates with rc=0, fallback=0, and mismatch=0. Regular02-05 pass current
  black-border gates. Regular01 is conditional and needs human visual review.

Pose smoothing check:
  R4 reduces the visible-risk matrix jumps, for example Regular04 trans p95
  6.50 px -> 2.71 px and Regular05 trans p95 12.26 px -> 7.24 px, while keeping
  the device consumer healthy. It is rejected because the stabilization becomes
  too weak. lim8 caps local deltas but remains visually jumpy, so it is also
  rejected and kept only as diagnostic evidence.

PyrLK / Remap backend boundary:
  VPI PyrLK CPU/CUDA can run, but in the current same-keypoint probe OpenCV is
  the better motion-estimation path: OpenCV PyrLK averaged 1.378 ms with about
  111 valid points, while VPI CUDA averaged 1.672 ms with about 37 valid points.
  Dense Optical Flow is not implemented in the current Python probe. VPI Remap
  exists as an API, but the Python WarpMap/Image.remap path aborts in the native
  binding; future Remap work should use a C++/official sample route.
```

Conclusion:

```text
Python-in-the-loop GStreamer EIS integration is not the next acceleration path.
The strongest acceleration evidence is now PerspectiveWarp module-level
latency/perf-watt, while the C++ MMAPI/VPI/NVENC path explains the device
dataflow boundary. The accepted consumer/FIFO path is healthy, but it is not
zero-copy: wrapper lifecycle, sync, and transform sandwich costs are still
measured. The accepted quality recovery result is resid_r15_s07.
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
path now has an accepted Regular gate EGLImage device path, a Regular05
FIFO/live handoff checkpoint, and a format-matched NvBuffer pair follow-up that
keeps the `resid_r15_s07` quality anchor while shaving a small measured portion
of the device-side stage cost.
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
docs/regular_gate_eglimage_fix_2026-07-20.md
docs/regular05_eglimage_wrapper_reuse_root_cause_2026-07-20.md
docs/regular05_live_eglimage_path_2026-07-20.md
docs/regular05_producer_scheduling_optimization_2026-07-20.md
docs/regular_gate_stride5_viewport_stable_validation_2026-07-20.md
docs/regular_gate_pose_smooth_r4_validation_2026-07-20.md
docs/regular_gate_pose_delta_limiter_validation_2026-07-20.md
results/vpi_warp_module_rerun_20260722/
results/power_probe_20260722_sudo/
results/pyr_lk_opencv_vpi_compare_20260722_v2/
results/regular05_submit_sync_probe_20260722/
results/regular_gate_nvbuffer_pair_resid_20260723/
results/regular05_eglimage_timing_resid_compare_20260723/
```
