# Evidence Reader Path

Use this document when you know the question but not the evidence location.

## I Want The Short Version

Read:

```text
README.md
docs/presentation/final_benchmark_table.md
docs/presentation/claim_boundary.md
docs/backend_decision_table_2026-07-24.md
```

Best one-sentence framing:

```text
This is a Jetson Orin NX heterogeneous video-compute project that uses EIS as a
real-time workload to measure quality, VPI/CUDA module acceleration,
MMAPI/VPI/NVENC dataflow, and wrapper/sync/transform lifecycle costs.
```

## I Want Quality Evidence

Read:

```text
docs/presentation/baseline_and_metrics.md
docs/stage_result_regular_performance_baseline_2026-07-18.md
docs/regular_gate_residual_closed_loop_2026-07-21.md
```

Evidence:

```text
results/regular_gate_est0p5_grid16_validation_20260718/
results/evidence/20260718_jetson_regular05_perf/
C:\Users\Admin\Videos\orin nx\review\performance\20260718_regular_gate_est0p5_grid16_validation\
C:\Users\Admin\Videos\orin nx\review\performance\20260721_regular_gate_residual_closed_loop_full\
```

Claim:

```text
Regular-gate quality is accepted. Challenge scenes are model boundaries.
```

Do not claim:

```text
all-scene EIS
product-grade stabilization
running/parallax/crowd solved
```

## I Want CPU Performance Evidence

Read:

```text
docs/presentation/performance_optimization.md
docs/stage_result_regular_performance_baseline_2026-07-18.md
```

Key result:

```text
Regular05 estimate time: 8.568 ms -> 3.022 ms
Regular05 wall time: 8.473 s -> 7.565 s
```

Claim:

```text
CPU motion-estimation downscaling plus denser features reduced cost inside the
Regular gate.
```

## I Want VPI / Hardware Acceleration Evidence

Read:

```text
docs/presentation/hardware_acceleration_boundary.md
docs/vpi_warp_module_report_2026-07-18.md
docs/vpi_remap_cpp_probe_2026-07-23.md
docs/remap_mmapi_integration_probe_2026-07-23.md
docs/remap_native_size_pad_crop_probe_2026-07-23.md
```

Evidence:

```text
results/vpi_warp_module_rerun_20260722/
results/vpi_warp_correctness_20260722/
results/power_probe_20260722_sudo/
```

Key result:

```text
4K PerspectiveWarp:
  OpenCV CPU: 48.995 ms, 20.410 FPS, 1.682 FPS/W
  VPI CUDA:   20.514 ms, 48.747 FPS, 4.385 FPS/W
```

Claim:

```text
VPI CUDA helps on high-resolution PerspectiveWarp modules.
VPI C++ Remap works on CPU/CUDA and accelerates tested identity/wave remap maps.
Remap can be inserted into the MMAPI/VPI/NVENC scratch stage as a diagnostic
operator, including native 640x360 main-chain pad/crop handling.
```

Do not claim:

```text
full EIS pipeline acceleration
VPI optical-flow acceleration
pixel-equivalent output
Regular EIS quality improved by Remap
```

## I Want Device-Side Dataflow Evidence

Read:

```text
docs/presentation/dataflow_architecture.md
docs/regular_gate_eglimage_fix_2026-07-20.md
docs/regular05_eglimage_dataflow_cost_2026-07-20.md
docs/regular05_live_eglimage_path_2026-07-20.md
```

Accepted path:

```text
H264 -> MMAPI/NVDEC -> block-linear NV12
-> NvBufSurfTransform -> pitch-linear NV12_ER scratch
-> VPI CUDA PerspectiveWarp
-> NvBufSurfTransform -> block-linear NV12
-> NVENC
```

Claim:

```text
The C++ device-stage path is measured and explainable.
```

Do not claim:

```text
zero-copy
full real-time EIS
pitch-linear main encode works
image-wrapper reuse is safe
```

## I Want Profiling Evidence

Read:

```text
docs/nsight_device_stage_profile_result_2026-07-23.md
docs/device_stage_lifecycle_budget_2026-07-23.md
```

Evidence:

```text
results/nsight_device_stage_profile_20260723/
results/device_stage_lifecycle_probe_20260723/repeat/
```

Key result:

```text
vpiSubmitPerspectiveWarp: about 0.022-0.024 ms
VPI:Perspective Warp: about 0.763-0.805 ms
dominant cost: wrapper / sync / transform / lifecycle
```

Claim:

```text
The bottleneck is around dataflow and lifecycle, not the submit call alone.
```

## I Want The Latest Lifecycle Optimization

Read:

```text
docs/device_stage_lifecycle_perf_result_2026-07-23.md
docs/device_stage_stability_p99_repeat_2026-07-24.md
docs/device_stage_endurance_50run_2026-07-24.md
docs/presentation/hardware_acceleration_boundary.md
```

Evidence:

```text
results/device_stage_lifecycle_perf_20260723/
```

Key result:

```text
accepted EGLImage:
  wall mean = 1.946819 s
  stage avg = 10.336381 ms

stream-only reuse:
  wall mean = 1.843571 s
  stage avg = 9.680414 ms

benefit:
  wall mean +5.303%
  stage avg +6.346%
  wrapper +8.703%
```

Claim:

```text
Stream-only reuse is a small accepted lifecycle optimization.
Existing repeat evidence supports small mean lifecycle gains and clean
rc/fallback behavior, but it does not prove a tail-latency win or 30-minute
endurance.
The 50-run repeat extends health evidence: EGLImage, stream-only reuse, and
NvBuffer pair all complete 50/50 with rc=0 and fallback=0. It still does not
prove stream-only p99 improvement.
The hardening run adds a true 1802-second repeat. EGLImage, stream-only reuse,
and NvBuffer pair each complete 243/243 runs with rc=0, fallback=0, mismatch=0,
and readable 180-frame output. Stream-only improves mean wall time by about
0.51% but regresses p99 by about 2.68%.
Three interleaved INA3221 VDD_IN blocks measure stream-only at 11.626 FPS/W
versus EGLImage at 11.306 FPS/W, a small 2.83% board-input efficiency gain.
```

Do not claim:

```text
zero-copy
image-wrapper reuse
queue-depth or double-buffering proven useful
```

## I Want Remap / Operator Extension Evidence

Read:

```text
docs/vpi_remap_cpp_probe_2026-07-23.md
docs/remap_mmapi_integration_probe_2026-07-23.md
docs/remap_native_size_pad_crop_probe_2026-07-23.md
docs/cuda_mmapi_interop_safety_verifier_2026-07-24.md
docs/cuda_affine_mmapi_diagnostic_2026-07-24.md
docs/cuda_double_surface_debug_2026-07-24.md
docs/backend_decision_table_2026-07-24.md
docs/cuda_mmapi_route_recovery_2026-07-24.md
docs/cuda_mmapi_official_verifier_2026-07-24.md
experiments/vpi_cpp_remap_probe/remap_probe.cpp
```

Evidence:

```text
results/vpi_remap_cpp_probe_20260723/
results/remap_mmapi_integration_probe_20260723/
results/remap_native_size_pad_crop_probe_20260723/
results/cuda_mmapi_interop_safety_verifier_20260724/
results/cuda_affine_mmapi_diagnostic_20260724/
results/cuda_double_surface_debug_20260724/
C:\Users\Admin\Videos\orin nx\review\diagnostic\20260723_vpi_remap_cpp_probe\
C:\Users\Admin\Videos\orin nx\review\diagnostic\20260723_remap_mmapi_integration_probe\
C:\Users\Admin\Videos\orin nx\review\diagnostic\20260723_remap_native_size_pad_crop_probe\
C:\Users\Admin\Videos\orin nx\review\diagnostic\20260724_cuda_mmapi_interop_safety_verifier\
```

Key results:

```text
Python VPI Remap:
  native abort, remains a negative boundary

C++ VPI Remap:
  CPU/CUDA pass
  CUDA speedup vs OpenCV CPU: about 2.5x-3.4x on tested maps
  NV12_ER CPU/CUDA pass at 640x368

Remap-MMAPI padded diagnostic:
  640x360 source fails because WarpGrid aligns height to 368
  640x368 padded diagnostic source runs identity/wave/wave_safe with rc=0

Remap native-size pad/crop closure:
  main decode/encode chain remains native 640x360
  only the VPI scratch stage is padded to 640x368
  identity and wave_safe both rc=0 and readable
  black-border p95 is 0 in the recorded checks

CUDA/MMAPI interop safety verifier:
  CUDA driver API EGL interop can read/write the pitch-linear NV12_ER scratch
  stage and encode readable 640x360 output
  corrected identity, marker, and dynamic_marker modes all rc=0
  all three corrected modes have black-border p95 0
  the older large-plane shift/dynamic_shift modes are rejected after visual
  review because they caused severe tearing/distortion despite rc=0

CUDA affine MMAPI diagnostic:
  identity CUDA kernel path is readable and has black-border p95 0
  translate / affine random-sampling kernels over the current EGL-mapped NV12_ER
  scratch repeatedly tear or show unrelated visual corruption
  this is negative integration evidence, not an accepted CUDA warp path

CUDA double-surface debug:
  VIC round-trip and dual-surface full-frame CUDA copy are readable
  dual-surface integer translate still tears
  the blocker is narrowed to spatial random sampling/remap over the current
  EGL-mapped NV12_ER scratch route

CUDA-MMAPI route recovery:
  failed CUDA-owned bridge is not reused
  next possible route is an official-sample-shaped CUDA-to-encoder verifier
  identity/marker must pass before translate, and translate must pass before
  affine or matrix replay

CUDA-MMAPI official verifier:
  official 03_video_cuda_enc ownership shape is positive
  marker output is readable and black-border healthy
  translate dx8 and affine dx8 pass spatial-coherence checks
  this does not fix the rejected transcode scratch route by itself

Chroma-aware CUDA verifier:
  complete Y/U/V copy and dx8 translate match decoded references exactly
  bounded affine Y/U/V MAE is about 1.515/0.671/0.536
  CUDA affine processing averages about 0.362 ms

Block-linear CUDA array bridge:
  array copy is exact
  all-intra dx8 passes with 0.103 px spread and 0.104 px shift error
  normal inter-frame H264 accumulates the warp because in-place writes alter
  decoder reference surfaces
  a separate encoder surface pool is required before normal-H264 promotion
```

Claim:

```text
VPI C++ Remap is a valid module/operator-level route for future local warp or
pitch-linear scratch probing.
The native 640x360 MMAPI main chain can use a padded 640x368 VPI Remap scratch
stage and crop/transform back before NVENC.
```

Do not claim:

```text
full-pipeline EIS acceleration
mesh EIS quality solved
VIC validated for this pipeline
Regular EIS quality improved by Remap
zero-copy
accepted MMAPI CUDA acceleration from the safety verifier alone
accepted MMAPI CUDA acceleration from the CUDA-owned bridge
full-pipeline acceleration from the official encoder verifier
```

## I Want Startup Black Fix Evidence

Read:

```text
docs/regular05_startup_black_fix_closeout_2026-07-24.md
```

Evidence:

```text
results/vpi_cuda_owned_bridge_20260724/startup_black_fix_const_full/
C:\Users\Admin\Videos\orin nx\review\performance\20260724_regular05_startup_black_fix\20260724_regular05_startup_black_fix_source_old_const90_constfull_grid_30fps.mp4
```

Claim:

```text
The `constant FOV full` candidate removes the measured Regular05 startup
left-edge black exposure and was accepted by human review on Regular05.
The five-Regular technical extension ran with rc=0, fallback=0, and mismatch=0;
Regular01 remains visual-conditional.
```

Do not claim:

```text
five-clip human acceptance before Regular01 review
EIS quality improvement
CUDA-owned bridge success
full real-time EIS
```

## I Want Producer Boundary Evidence

Read:

```text
docs/producer_boundary_and_next_route_2026-07-24.md
docs/producer_first_row_latency_audit_2026-07-24.md
docs/regular05_producer_scheduling_optimization_2026-07-20.md
docs/hybrid_realtime_matrix_handoff_2026-07-19.md
```

Key result:

```text
FIFO/consumer handoff is healthy.
stride5 reduces producer-only time from about 68.5 s to about 15.7 s for
180 frames.
concurrent live stride5 completes in 17.5 s for 180 frames.
incremental prefix output moves the first solved row from 15.799 s to 1.036 s
on Jetson while preserving byte-identical 180-row matrices and FIFO H264.
```

Claim:

```text
Producer work is a latency-quality and scheduling trade-off story. It is not a
full real-time EIS claim.
Incremental output reduces extra compute blocking before the first matrix, but
does not remove the full motion prepass, 90-frame lookahead, or total LP work.
```

## I Want Failure Boundaries

Read:

```text
docs/challenge_boundary_report_2026-07-18.md
docs/presentation/challenge_boundary.md
docs/presentation/claim_boundary.md
```

Common failures and meanings:

| Failure | Meaning |
|---|---|
| Running failures | high-frequency motion and FOV pressure |
| QuickRotation failures | fast rotation exceeds crop/FOV budget |
| Parallax failures | one global transform cannot represent depth variation |
| Crowd failures | foreground motion contaminates global estimation |
| VPI backend swap slower | placement/dataflow issue, not proof VPI is useless |
| Python appsink/appsrc expensive | Python-in-loop dataflow is not the next acceleration path |
| EGLImage image-wrapper reuse tears | stream reuse is safe, image-wrapper reuse is not |

## I Want Resume / Interview Wording

Read:

```text
docs/presentation/project_story.md
docs/presentation/interview_qna.md
docs/presentation/resume_bullets.md
```

Use wording that includes:

```text
Jetson Orin NX
EIS as representative real-time workload
Regular/Challenge gate split
VPI CUDA module acceleration
MMAPI/VPI/NVENC device-stage profiling
wrapper/sync/transform lifecycle bottleneck
stream-only reuse small lifecycle gain
```

Avoid wording that implies:

```text
full product
zero-copy
all-scene solved
unmeasured real-time claim
```
