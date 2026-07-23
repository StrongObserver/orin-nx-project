# Jetson Orin NX Heterogeneous Video Compute Project

Resume-oriented engineering project for heterogeneous video compute and
device-side dataflow optimization on NVIDIA Jetson Orin NX.

The project is not just a demo. The target is an explainable engineering loop:

```text
EIS representative workload
-> controllable CPU baseline and quality gates
-> VPI/CUDA backend and module benchmarks
-> MMAPI/NVDEC/NVENC device-side dataflow
-> wrapper / sync / transform / memory-format profiling
-> honest boundary and trade-off summary for interviews
```

## Portfolio Overview

This repository is best read as a measured systems project:

```text
Quality boundary -> CPU baseline -> VPI module evidence
-> MMAPI/VPI/NVENC device stage -> Nsight attribution
-> small lifecycle/dataflow optimizations -> honest claim boundary
```

### Key Results

| Layer | Result | Boundary |
|---|---|---|
| Regular quality | `lp_rigid_strength080_dynzoom106 + estimate_scale=0.5 + feature_grid_size=16` passed 5/5 NUS Regular clips and was human accepted | Regular gate only, not all-scene EIS |
| Quality recovery | `resid_r15_s07` is the accepted Regular-gate stabilization-strength anchor | Supersedes BQP/spike_mid/safe103 for current quality comparisons |
| CPU optimization | Regular05 estimate time `8.568 ms -> 3.022 ms`; wall `8.473 s -> 7.565 s` | CPU/OpenCV pipeline optimization |
| VPI module acceleration | 4K PerspectiveWarp `48.995 ms -> 20.514 ms`; `1.682 -> 4.385 FPS/W` | Module-level evidence, not full-pipeline acceleration |
| VPI C++ Remap | CUDA Remap is `2.5x-3.4x` faster than OpenCV CPU on tested BGR8 identity/wave maps | Module/operator evidence; Python Remap still failed |
| Remap-MMAPI diagnostic | 640x368 padded source runs Remap identity/wave through MMAPI/VPI/NVENC scratch stage with `rc=0` | Device-stage operator integration evidence; not Regular EIS quality |
| Remap native-size pad/crop | Native 640x360 main chain can use a 640x368 padded Remap scratch stage and crop back before NVENC with `rc=0` | Size/layout diagnostic; not EIS quality or full-pipeline acceleration |
| Dynamic Remap payload | Dynamic per-frame Remap payload rebuild works but raises MMAPI stage avg to about `13.14-13.16 ms` | Future mesh/local-warp cost boundary, not quality or acceleration |
| CUDA dynamic warp | Standalone 640x368 CUDA affine warp: RGBA dynamic `0.194 ms`, Y8 dynamic `0.138 ms` | Standalone operator evidence; MMAPI integration still needs safety verifier |
| CUDA affine MMAPI diagnostic | Identity CUDA kernel path is readable, but translate/affine random-sampling over current EGL-mapped NV12_ER scratch tears | Negative integration evidence; needs different CUDA surface route |
| Local-warp quality bridge | Static single-cell local Remap correction on `parallax10` did not improve local residual metrics | Negative diagnostic result; richer dynamic mesh/depth/RS model needed |
| Python dataflow boundary | appsink readback about `7.93 ms/frame`; appsink -> appsrc -> encode about `15.81 ms/frame` | Explains why Python-in-loop is not the acceleration path |
| C++ device stage | MMAPI/NVDEC -> block-linear NV12 -> pitch-linear NV12_ER scratch -> VPI CUDA warp -> NVENC | Device-stage evidence, not full real-time EIS |
| NvBuffer pair | Preserves `resid_r15_s07`; stage frame100 `7.535 ms -> 7.230 ms` | Small quality-preserving dataflow gain, not zero-copy |
| Nsight/NVTX | `vpiSubmitPerspectiveWarp` about `0.02 ms`; wrapper/sync/transform/lifecycle dominates | Bottleneck attribution |
| Stream-only reuse | 10-run repeat wall mean `1.946819 s -> 1.843571 s`; stage avg `10.336381 ms -> 9.680414 ms` | Small lifecycle optimization; image wrappers are still recreated |

### Architecture

```text
Regular clips
-> CPU/OpenCV EIS and matrix generation
-> resid_r15_s07 source_to_dest matrices
-> MMAPI/NVDEC block-linear NV12 main chain
-> NvBufSurfTransform to pitch-linear NV12_ER scratch
-> VPI CUDA PerspectiveWarp
-> NvBufSurfTransform back to block-linear NV12
-> NVENC output
```

Diagrams:

```text
docs/presentation/assets/device_dataflow_architecture.svg
docs/presentation/assets/evidence_stack.svg
```

### Reproduce

Start with the control plane:

```powershell
py -3.12 scripts\harness_runner.py onboard
py -3.12 scripts\harness_runner.py doctor
py -3.12 scripts\harness_runner.py check-claim --gate-id nus_running_gate_v1 --claim main_gate_success_rate
```

`onboard` is a required startup gate, not just a manifest printer. It prints and
full-reads the real oral-template TXT, validates the required sections, and
reports the current section-4 execution mode before other control-plane checks.

Then follow the layered guide:

```text
docs/reproducibility_guide.md
```

### Evidence Routes

```text
docs/evidence_reader_path.md
docs/presentation/final_benchmark_table.md
docs/presentation/dataflow_architecture.md
docs/presentation/claim_boundary.md
docs/device_stage_lifecycle_perf_result_2026-07-23.md
docs/nsight_device_stage_profile_result_2026-07-23.md
```

### Claim Boundary

Allowed:

```text
Regular-gate EIS quality
module-level VPI CUDA acceleration and 4K FPS/W
module-level VPI C++ Remap acceleration
measured MMAPI/VPI/NVENC device-stage dataflow
small NvBuffer pair and stream-only lifecycle improvements
Nsight-backed wrapper/sync/transform/lifecycle attribution
```

Forbidden:

```text
full real-time EIS product
zero-copy full chain
full-pipeline acceleration from module-only or stage-only evidence
VPI optical-flow acceleration
all-scene or product-grade EIS quality
queue-depth or double-buffering proven beneficial
```

## Current Highlights

```text
Current sealed stage:
  Final evidence package closeout and lifecycle follow-up are complete.
  Nsight/NVTX profiling has been captured and summarized.
  Stream-only reuse is accepted as a small lifecycle optimization.
  Remap-MMAPI diagnostic insertion and local-warp quality bridge are complete.
  Static single-cell local Remap correction did not improve parallax residuals.
  Queue-depth or double-buffering work is not triggered by current evidence.
  The native-size Remap pad/crop diagnostic is complete.
  Dynamic Remap payload cost and standalone CUDA dynamic warp probes are complete.
  CUDA/MMAPI scratch interop safety verification is complete.
  CUDA affine MMAPI diagnostic is closed as negative evidence at non-identity warp.

Regular performance baseline:
  lp_rigid_strength080_dynzoom106 + estimate_scale=0.5 + feature_grid_size=16
  NUS Regular gate: 5/5 objective pass and human accepted

Device-side MMAPI/VPI/NVENC path:
  The accepted C++ EGLImage-wrapper path now runs decode -> block-linear main
  NvBufSurface -> pitch-linear NV12_ER scratch -> VPI CUDA warp -> block-linear
  NV12 -> NVENC. It is the frozen Regular gate C++ device path, not a full
  real-time or zero-copy EIS claim.

Regular gate viewport-stable extension:
  The user accepted Regular05 `safe103_crop98` as the viewport-stable candidate:
  no zooming and no brief left-bottom black edge. The same stride5 bounded-delay
  producer plus fixed-scale/crop98 viewport rule was extended to all five NUS
  Regular clips through the accepted EGLImage FIFO consumer. All five device
  runs have rc=0, fallback=0, and frame-index mismatch=0. Four clips pass the
  gray-threshold black-border hard gate; Regular01 is conditional because gray
  black-border p95 is 0.026323350 while geometry p95 invalid is 0.000003906.
  Human review of Regular01 is required before claiming 5/5 Regular pass.

Regular gate pose smoothing:
  Human review found that the fixed-scale/crop98 route removed zooming and
  brief black edges but still had abrupt translation/rotation pose jumps. Matrix
  diagnostics traced this to remaining `tx/ty/angle` stair-steps. The
  pose_smooth_r4 candidate smooths translation and angle while keeping fixed
  scale and crop98. It ran 5/5 through the accepted EGLImage FIFO consumer with
  rc=0, fallback=0, and mismatch=0, and reduces translation p95 on every clip.
  Human review found R4 too weak. The next lim8 diagnostic used a local delta
  limiter instead of whole-sequence averaging; it also ran 5/5 through the
  accepted consumer, but the user rejected it because abrupt pose jumps remain.
  This moved the project into camera-path root-cause recovery rather than
  another limiter sweep. Matrix-level probes for published-prefix continuity and
  intent-reference LP costs were added as default-off diagnostics, but they are
  not accepted quality fixes.

Bounded QP camera-path candidate:
  The approved recovery loop replaced post-hoc limiter/smoothing with a
  bounded-delay camera-path QP candidate, `bqp_w90_s15_w2_20_w3_200`. It keeps
  the accepted C++ EGLImage FIFO consumer fixed and changes only matrix/path
  generation. On Regular05, matrix metrics improved from safe103crop98
  `trans_d1_p95=12.267` to `7.934`, with `trans_d2_max=2.173` and
  `trans_d3_max=1.834`, close to the R4 smoothness range without using R4's
  whole-sequence averaging. The candidate ran all five Regular clips through
  the accepted Jetson FIFO consumer with rc=0, fallback=0, and mismatch=0.
  Regular02, Regular03, and Regular05 pass current black/geometry hard gates;
  Regular01 and Regular04 are metric-conditional because gray black-border p95
  is high while geometry p95 remains below 1%. Human review later found the
  BQP output too weak, so this candidate remains diagnostic history.

Stabilization-strength recovery history:
  Human review found `bqp_w90_s15` geometrically healthy but visually too weak.
  MeshFlowPy was extracted and inspected; it is a dense/mesh flow backend, not a
  temporal camera-path optimizer, so it is deferred unless global-path recovery
  fails. The first enhanced candidate, `spike_mid_t6_b70_r2_i2`, was a local D2
  pose-spike repair on top of the stronger `safe103crop98` correction. On
  Regular05 it improved residual translation mean from `bqp_w90_s15=3.915` to
  `spike_mid=2.788`, closer to `safe103crop98=2.103`, while preserving 5/5
  Jetson FIFO rc/fallback/mismatch health, but human review still rejected it as
  insufficient for the current quality target.

Residual closed-loop recovery:
  After `spike_mid` was also rejected, residual-grid diagnostics did not show a
  clear local-motion/parallax-only signature. The next candidate,
  `resid_r15_s07`, estimates residual motion from the safe103crop98 output,
  smooths that residual path, and composes the correction back into the device
  matrices. Full-length matrices ran all five Regular clips through the accepted
  Jetson FIFO consumer with rc=0, fallback=0, and mismatch=0. On Regular05,
  residual translation mean improves to `1.033`, stronger than safe103crop98
  `2.103`, bqp `3.915`, and spike_mid `2.788`. Human review accepted the
  candidate: it is visibly stronger than bqp/spike_mid and shows no hard pose
  snaps or visible black borders in the review videos. The result is accepted
  inside the Regular gate boundary, not as all-scene or product-grade EIS.

Regular gate inclusion viewport validation:
  safe103_crop98 is accepted only for Regular05 and failed as a general
  five-clip producer. The newer inclusion-constrained source_to_dest matrices
  have 5/5 geometry-valid coverage with p95/max invalid ratio 0.

Regular gate distortion fix:
  The first MMAPI EGL pitch-wrapper -> in-place VPI warp -> NVENC output was
  rejected because non-identity matrices caused block-like tearing. Identity,
  pure translation/scale/rotation, safe103, and inclusion matrices confirmed
  this is a device integration issue, not an inclusion algorithm issue. The
  corrected visual candidate uses a VPI Python allocated-image path with
  explicit `vpi.Format.BGR8` input and removes both visible tearing and the
  earlier green/cyan color shift on all five Regular clips. The user accepted
  the five BGR8 review grids, so this is now the frozen visual correctness
  candidate for Regular gate inclusion. This is a
  correctness path, not the final MMAPI/NVENC acceleration claim.

C++ EGLImage-wrapper candidate:
  A new MMAPI/VPI/NVENC sample avoids the rejected CUDA pitch-pointer wrapper
  by using VPI EGLImage wrappers on pitch-linear NvBuffer scratch surfaces.
  It ran all five Regular inclusion matrices with rc=0, fallback=0, and no
  frame-index mismatch in sampled handoff logs. The user accepted the five
  review grids, so this is the frozen C++ device-side path for Regular gate
  inclusion.

EGLImage timing boundary:
  Regular05 timing on the accepted C++ path shows VPI warp-only running avg
  around 1.55 ms, while the larger EGLImage scratch-buffer stage is about
  10.5 ms. The next performance target is the memory/dataflow around VPI, not
  the PerspectiveWarp kernel alone.

Wrapper reuse boundary:
  VPI stream reuse is safe, but EGLImage image-wrapper reuse is closed as a
  dead end for this MMAPI path. Single-wrapper, per-buffer, input-only,
  output-only, persistent mapping, and explicit-sync variants either tore or
  failed. Continue performance work on NvBufSurfTransform/dataflow cost instead.

Transform cost probe:
  A transform-only Regular05 probe measured the three-transform dataflow at
  about 2.7 ms steady-state. That is much smaller than the accepted EGLImage
  stage cost, so remaining performance work should isolate VPI wrapper,
  EGLImage map/unmap, submit, and sync overhead rather than blaming transform
  cost alone.

EGL map probe:
  Regular05 EGLImage map/unmap cost is small: about 0.14 ms combined at the
  frame-100 sample. The remaining gap is therefore more likely VPI wrapper
  creation plus VPI submit/sync behavior.

VPI wrapper lifecycle:
  A wrapper-create probe measured about 3.41 ms to create and 0.29 ms to destroy
  the input/output VPI EGLImage wrappers at frame 100, with a large first-frame
  initialization spike. Wrapper lifecycle is a major cost, but image-wrapper
  reuse is unsafe in this MMAPI path.

Identity warp probe:
  Regular05 identity PerspectiveWarp averaged about 1.49 ms versus about 1.55 ms
  for the inclusion matrix. Matrix complexity is not the current dataflow
  bottleneck.

Surface format probe:
  The encoder main DMABUF and VPI scratch are not format/layout compatible:
  main uses colorFormat=6, layout=1, pitch=640; scratch uses colorFormat=7,
  layout=0, pitch=768. Direct NvBuffer wrapping must start from a deliberately
  format-matched input/output pair.

Block-linear probe:
  VPI PerspectiveWarp rejected both tested block-linear scratch pairs: limited
  range NV12 failed because full range is required, and block-linear NV12_ER was
  unsupported. The pitch-linear NV12_ER scratch pair remains required for VPI.

Pitch encoder probe:
  Changing the transcode main path to pitch-linear returned success but produced
  near-solid green video. NVENC/main-chain output must stay block-linear in this
  path, so the block-linear main chain plus pitch-linear VPI scratch transform
  sandwich is a current hard boundary.

Regular05 producer matrices on C++ path:
  The accepted C++ EGLImage consumer ran fixed replay, offline-LP, and delay90
  Regular05 matrices with rc=0, fallback=0, frame-index mismatch=0, and
  black-border p95 below 1%. This validates the accepted device consumer for
  existing producer CSVs.

Concurrent FIFO/live producer:
  The FIFO-enabled accepted EGLImage consumer also ran fixed CSV, delay90 CSV,
  and concurrent live delay90 producer inputs with rc=0, fallback=0, mismatch=0,
  and black-border p95 below 1%. The concurrent live run took about 68.7 s for
  180 frames, so the live bottleneck is producer compute/scheduling rather than
  the C++ consumer.

Producer scheduling optimization:
  A new optional `--lp-prefix-stride` parameter keeps the original stride-1
  behavior by default. With stride 5 on Regular05 delay90, LP solve calls drop
  from 89 to 19 and Jetson producer-only total time drops from about 68.5s to
  about 15.7s. The stride5 FIFO device output keeps fallback=0, mismatch=0, and
  black-border p95=0.000784288. Concurrent live stride5 completes in 17.5s for
  180 frames with the same output as precomputed stride5.
```

## Current Stage

The accepted custom CPU baseline is frozen as:

```text
smoothing_method=lp_rigid
stabilization_strength=0.80
crop_ratio=0.90
crop_interpolation=lanczos
sharpen_strength=0.25
dynamic_zoom=true, max_zoom=1.06
warp_backend=opencv_cpu
estimate_scale=1.0
```

Main evidence clip:

```text
results/nus_regular_gate_v1/raw_clips/regular_gate05_regular_6.mp4
```

Jetson same-input evidence for the frozen CPU baseline:

| Metric | Value |
|---|---:|
| Resolution | 640x360 |
| Frames | 180 |
| avg_estimate_ms | 8.568 |
| avg_warp_ms | 7.936 |
| total_wall_time_s | 8.473 |
| mask_safety_rollback_frames | 0 |
| p95_invalid_mask_ratio | 0.001196 |

This baseline was selected because it reduces the visible `regular05` tail
pull/rollback risk better than the full-strength affine or rigid variants. It is
a practical stage baseline, not a claim that one global warp solves all
parallax, rolling-shutter, or local non-rigid motion cases.

## Backend Boundary

Same-input Jetson backend comparison kept the quality configuration fixed and
changed only `warp_backend`:

| Backend | avg_estimate_ms | avg_warp_ms | total_wall_time_s | Result |
|---|---:|---:|---:|---|
| opencv_cpu | 8.568 | 7.936 | 8.473 | current best |
| vpi_cuda | 8.777 | 9.621 | 9.382 | slower |
| vpi_cpu | 8.620 | 11.934 | 9.640 | slower |
| vpi_vic | 8.587 | 14.531 | 10.132 | slower |

Conclusion: for the current 640x360 Python/OpenCV/VPI full-pipeline path, VPI
warp backend replacement is not an acceleration result. Prior warp-only
high-resolution benchmarks still show VPI CUDA can help when the warp workload
is large enough, but this project should not claim full-pipeline VPI acceleration
until same-input Jetson timing proves it.

## Optimization Findings

### Motion-Estimation Downscaling

`estimate_scale` is a real speed knob. The first simple downscale attempts were
faster but failed smoothness; a second scoped contract found one objective-gated
candidate that the user accepted after side-by-side review.

| Candidate | avg_estimate_ms | total_wall_time_s | second_top5_improve | Result |
|---|---:|---:|---:|---|
| est1p0 | 8.568 | 8.473 | 0.006 | accepted baseline |
| est0p75 | 6.350 | 8.091 | -0.018 | faster, quality gate fail |
| est0p5 | 3.020 | 7.647 | -0.003 | faster, quality gate fail |
| est0p5_grid16 | 3.022 | 7.565 | 0.0003 | Regular performance baseline |

Conclusion: downscaling motion estimation can reduce total Jetson wall time by
about 11% on Regular05. `est0p5_grid16` is human-accepted on all five Regular
review clips and passed objective gates on all five `nus_regular_gate_v1` clips.

Keep two baselines distinct:

```text
quality-safe baseline:
  estimate_scale=1.0, feature_grid_size=12

Regular performance baseline:
  estimate_scale=0.5, feature_grid_size=16
```

The performance baseline does not erase the quality-safe baseline. Use the
quality-safe baseline when the priority is conservatism; use the Regular
performance baseline when the priority is the measured Regular-gate speedup.

Regular gate validation:

| Clip | SR_pose | residual_improve | second_top5_improve | grade | layered |
|---|---:|---:|---:|---|---|
| regular_gate01 | 19.516 | 0.758 | 0.527 | A/B | pass |
| regular_gate02 | 5.912 | 0.398 | 0.683 | A/B | pass |
| regular_gate03 | 19.323 | 0.804 | 0.743 | A/B | pass |
| regular_gate04 | 16.304 | 0.760 | 0.757 | C | pass |
| regular_gate05 | 6.031 | 0.610 | 0.000 | A/B | pass |

### High-Resolution VPI Module Evidence

VPI CUDA remains useful at module scale when the warp workload is large enough:

| Resolution | OpenCV CPU ms | VPI CUDA ms | Speedup |
|---|---:|---:|---:|
| 1280x720 | 6.118 | 4.523 | 1.35x |
| 1920x1080 | 13.569 | 7.398 | 1.83x |
| 2560x1440 | 22.920 | 10.651 | 2.15x |
| 3840x2160 | 48.452 | 20.836 | 2.33x |

This supports a careful claim: VPI CUDA accelerates high-resolution warp-heavy
modules, but the current small full pipeline does not benefit from a simple
backend swap.

### GStreamer / NVMM Probe

The Jetson has a working minimum hardware decode / NVMM / conversion path:

```text
filesrc -> qtdemux -> h264parse -> nvv4l2decoder -> NVMM -> nvvidconv -> BGRx -> fakesink
```

The 1080p probe reached EOS successfully in about 1.60s. This is only a dataflow
readiness result, not EIS acceleration.

Python-in-the-loop boundary:

| Path | Result |
|---|---:|
| appsink BGRx readback | 7.93 ms/frame |
| appsink -> appsrc -> encode pass-through | 15.81 ms/frame |

Conclusion: direct Python GStreamer integration is not the next best way to
accelerate the current CPU EIS pipeline. If this direction resumes, prefer a
C++/CUDA or device-side dataflow path.

### Device-Side Matrix Warp Boundary

The current non-Python device-side path uses Jetson Multimedia API and VPI CUDA:

```text
H264 input -> decode/NvBufSurface -> pitch-linear NV12_ER scratch
-> VPI CUDA warp -> block-linear NV12 -> NVENC
```

Historical outdoor-car same-source matrix tests showed that the forward CPU
matrix creates excessive black border on that smoke source, while the inverse
matrix gives normal sampled black-border sanity:

| Output | Black ratio | Decision |
|---|---:|---|
| device forward matrix | about 0.303 | reject |
| device inverse matrix | about 0.028 to 0.029 | outdoor-car dataflow smoke default only |

That inverse convention is not the Regular05 EIS-quality convention. Regular05
device replay uses `source_to_dest`.

The device path is still a scoped stage boundary. A local 120-frame panel
comparison between CPU stabilized and device inverse output has
`mean_abs_center_avg=37.033757` and `p95_abs_center_avg=138.416667`, so the
project must not claim CPU-output equivalence. The main known gap is that the
device path currently uses linear VPI warp with zero border and does not
reproduce CPU post-processing such as dynamic zoom, fixed crop/resize, Lanczos
interpolation, and sharpen.

The next device-side A/B test was run with generated 120-row matrix candidates:

```text
device_matrices_inverse_aligned_identity_first.csv
device_matrices_inverse_with_post_geometry.csv
```

Result:

| Candidate | mean_abs_center_avg vs CPU | p95_abs_center_avg vs CPU | Decision |
|---|---:|---:|---|
| old inverse | 44.739667 | 156.975000 | valid path, poor parity |
| aligned identity first | 46.884302 | 159.958333 | worse |
| post geometry | 30.688605 | 116.958333 | strong improvement |
| post geometry, identity first | 30.241568 | 115.866667 | current best device candidate |
| post geometry, identity first, Catmull-Rom | 30.902334 | 117.875000 | slower and worse |

The post-geometry matrix shows that composing CPU dynamic zoom + crop geometry
into the device matrix is the right direction. An identity transcode baseline
already has `mean_abs_center_avg=25.664099` versus source, so raw pixel diff has
a high codec/colorspace floor. The best device output still does not reach
CPU-output equivalence, so real-time motion estimation remains premature.

## Control Plane

Harness and evaluation files:

```text
configs/harness/gates.json
configs/harness/contracts/jetson_regular05_perf.json
configs/harness/contracts/regular_performance_baseline_est0p5_grid16.json
configs/harness/contracts/regular05_estimate_scale_quality_perf.json
configs/harness/contracts/regular_gate_est0p5_grid16_validation_v1.json
configs/harness/contracts/gst_nvmm_decode_convert_latency_v1.json
configs/harness/contracts/device_matrix_warp_demo_v1.json
configs/harness/contracts/hybrid_realtime_matrix_handoff_v1.json
configs/harness/contracts/regular05_hybrid_matrix_handoff_v1.json
configs/harness/contracts/orin_next_engineering_loop_v1.json
configs/harness/contracts/regular_gate_inclusion_validation_v1.json
configs/harness/contracts/regular05_eglimage_wrapper_reuse_root_cause_v1.json
configs/harness/contracts/regular05_live_eglimage_path_v1.json
configs/harness/evaluation_datasets.json
configs/harness/metric_schema.json
docs/harness_engineering_v1.md
docs/loop_engineering_v2.md
docs/evaluation_system_v1.md
```

Useful checks:

```powershell
py -3.12 scripts\harness_runner.py doctor
py -3.12 scripts\harness_runner.py list-gates
py -3.12 scripts\harness_runner.py check-evaluation-datasets
py -3.12 scripts\harness_runner.py validate-evidence results\evidence\20260718_jetson_regular05_perf --date 20260718
```

Important gate roles:

| Gate | Role |
|---|---|
| `nus_regular_gate_v1` | main quality gate |
| `nus_running_gate_v1` | challenge / model-boundary gate |
| `regular05_perf_gate` | same-input Jetson performance gate |

Do not use Running, QuickRotation, Parallax, Zooming, or Crowd as headline pass
rates. They are challenge or diagnostic sets unless a future evaluation contract
promotes a specific claim.

## Evidence

Local evidence and videos are intentionally ignored by Git.

Key local paths:

```text
results/evidence/20260718_jetson_regular05_perf/
results/perf_backend_compare_20260718/backend_compare_summary.md
results/estimate_scale_regular05_20260718/estimate_scale_summary.md
results/estimate_scale_quality_perf_20260718/quality_perf_summary.md
results/regular_gate_est0p5_grid16_validation_20260718/regular_gate_validation_summary.md
results/vpi_resolution_scaling_benchmark/vpi_module_summary.md
results/gst_nvmm_probe_20260718_summary.md
results/gst_appsrc_encode_boundary_20260718/summary.md
results/same_source_matrix_20260719/device_matrix_inverse.log
results/device_matrix_warp_demo_20260719/triptych_cpu_vs_device/summary.md
docs/stage_result_regular_performance_baseline_2026-07-18.md
docs/device_matrix_warp_demo_2026-07-19.md
docs/device_stage_demo_handoff_2026-07-19.md
docs/hybrid_realtime_eis_plan_2026-07-19.md
docs/hybrid_realtime_matrix_handoff_2026-07-19.md
docs/gstreamer_nvmm_latency_plan_2026-07-18.md
docs/regular_gate_inclusion_validation_2026-07-20.md
docs/regular_gate_vpi_distortion_fix_2026-07-20.md
docs/regular_gate_eglimage_fix_2026-07-20.md
docs/regular05_eglimage_wrapper_reuse_root_cause_2026-07-20.md
docs/regular05_live_eglimage_path_2026-07-20.md
C:\Users\Admin\Videos\orin nx\review\quality\20260718_regular05_new_method\
C:\Users\Admin\Videos\orin nx\review\performance\20260718_jetson_regular05_perf\
C:\Users\Admin\Videos\orin nx\review\performance\20260718_backend_compare\
C:\Users\Admin\Videos\orin nx\review\performance\20260718_estimate_scale_regular05\
C:\Users\Admin\Videos\orin nx\review\performance\20260718_estimate_scale_quality_perf\
C:\Users\Admin\Videos\orin nx\review\performance\20260718_regular_gate_est0p5_grid16_validation\
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_vpi_bgr8_color_fix\
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_eglimage_fix\
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular05_live_eglimage_path\
```

## Next Engineering Direction

Do not continue blind global affine/rigid parameter sweeps on `regular05`.

The current project direction follows the 2026-07-23 refined design:

```text
Jetson Orin NX heterogeneous video compute and device-side dataflow optimization
with EIS as the representative real-time vision workload.
```

The current device-side acceleration path should stay scoped:

```text
1. keep CPU quality-safe and Regular performance baselines distinct;
2. keep Challenge sets as model-boundary evidence, not headline pass rates;
3. keep high-resolution VPI warp/remap as module-level acceleration evidence;
4. use the accepted C++ EGLImage-wrapper path for Regular gate device replay;
5. keep the BGR8 VPI Python path as visual correctness reference, not as a
   real-time acceleration result;
6. do not reuse EGLImage image wrappers in this MMAPI path;
7. treat NvBuffer pair as a small quality-preserving dataflow-stage follow-up,
   not a zero-copy or full-pipeline acceleration result;
8. treat stream-only reuse as a small lifecycle optimization only, not
   image-wrapper reuse or zero-copy;
9. do not return to Python appsink/appsrc EIS integration;
10. treat dynamic Remap payload rebuild as a measured future-mesh cost boundary;
11. treat standalone CUDA dynamic warp as an operator candidate only until
    MMAPI scratch interop safety is verified;
12. use the final evidence package, architecture table, Nsight/NVTX result, and
    lifecycle repeat result as the current presentation closeout.
```

Current accepted Regular05 device path:

```text
H264 input
-> MMAPI decode / block-linear main NvBufSurface
-> NvBufSurfTransform to pitch-linear NV12_ER scratch
-> VPI CUDA PerspectiveWarp via per-frame EGLImage wrappers
-> NvBufSurfTransform back to block-linear NV12 main chain
-> NVENC
```

Current active contracts:

```text
configs/harness/contracts/orin_next_engineering_loop_v1.json
none
```

Important completed or supporting contracts:

```text
configs/harness/contracts/cuda_dynamic_warp_probe_v1.json
configs/harness/contracts/vpi_dynamic_remap_payload_probe_v1.json
configs/harness/contracts/device_stage_lifecycle_dataflow_v2.json
configs/harness/contracts/remap_native_size_pad_crop_probe_v1.json
configs/harness/contracts/final_evidence_package_closeout_v1.json
configs/harness/contracts/final_portfolio_and_reproducibility_loop_v1.json
configs/harness/contracts/device_stage_lifecycle_perf_loop_v1.json
configs/harness/contracts/local_warp_quality_bridge_loop_v1.json
configs/harness/contracts/remap_mmapi_integration_probe_loop_v1.json
configs/harness/contracts/vpi_remap_cpp_and_device_warp_extension_loop_v1.json
configs/harness/contracts/presentation_closeout_v1.json
configs/harness/contracts/nsight_device_stage_profile_v1.json
configs/harness/contracts/regular_gate_stabilization_strength_recovery_loop_v1.json
configs/harness/contracts/regular05_live_eglimage_path_v1.json
configs/harness/contracts/regular05_eglimage_wrapper_reuse_root_cause_v1.json
```

Current active verifier:

```text
configs/harness/contracts/cuda_mmapi_interop_safety_verifier_v1.json
```

This verifier is now complete. It started from the standalone CUDA dynamic warp
result and checked only whether CUDA can safely write through the current MMAPI
scratch boundary. The first `shift` / `dynamic_shift` diagnostics returned
rc=0, but visual review rejected those outputs because they had severe
tearing/distortion. The corrected verifier uses identity plus small ROI marker
diagnostics: identity, marker, and dynamic_marker all return rc=0 with readable
640x360 outputs and p95 black-border ratio 0. Marker modes prove CUDA write
activity without large-plane tearing. This remains a safety/dataflow verifier,
not a quality loop, not zero-copy, and not a full-pipeline acceleration claim.

Final evidence package docs:

```text
docs/presentation/final_benchmark_table.md
docs/presentation/dataflow_architecture.md
docs/presentation/claim_boundary.md
docs/nsight_device_stage_profile_result_2026-07-23.md
docs/device_stage_lifecycle_budget_2026-07-23.md
docs/device_stage_lifecycle_perf_result_2026-07-23.md
docs/regular_gate_nvbuffer_pair_resid_2026-07-23.md
docs/cuda_mmapi_interop_safety_verifier_2026-07-24.md
```

Rejected or diagnostic-only routes:

```text
sample_outdoor_car_1080p_10fps:
  dataflow / matrix handoff smoke only, not EIS quality evidence.

old MMAPI pitch-pointer wrapper:
  rejected because non-identity matrices caused block-like tearing.

EGLImage image-wrapper reuse:
  rejected after single-wrapper, per-buffer, input-only, output-only,
  persistent-mapping, and explicit-sync variants tore or failed.

direct mismatched NvBuffer input:
  rejected because VPI required matching input/output formats.

block-linear VPI scratch pair:
  rejected by VPI PerspectiveWarp format support.

pitch-linear main encoder chain:
  rejected because it returned success but produced near-solid green output.
```

Regular05 accepted C++ consumer summary:

| Input | rc | fallback | mismatch | black p95 | Decision |
|---|---:|---:|---:|---:|---|
| fixed replay CSV | 0 | 0 | 0 | 0.000951823 | accepted |
| offline-LP CSV | 0 | 0 | 0 | 0.001459201 | accepted |
| delay90 CSV | 0 | 0 | 0 | 0.000639106 | accepted |
| fixed FIFO | 0 | 0 | 0 | 0.000951823 | accepted |
| delay90 FIFO | 0 | 0 | 0 | 0.000639106 | accepted |
| concurrent live delay90 | 0 | 0 | 0 | 0.000583333 | consumer healthy; producer slow |

Primary current review assets:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_vpi_bgr8_color_fix\
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_eglimage_fix\
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular05_live_eglimage_path\
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular05_producer_scheduling_optimization\
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_stride5_viewport_stable_validation\
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_stride5_pose_smooth_r4_validation\
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_stride5_pose_delta_limiter_validation\
```

Regular05 stride5 producer scheduling reduces producer-only time from about
68.5s to about 15.7s and concurrent live wall time from about 68.7s to 17.5s
for 180 frames while the accepted FIFO consumer remains healthy. The viewport
stable rule has now been extended to five Regular clips. R4 and lim8 are now
rejected/diagnostic: R4 weakens stabilization too much, while lim8 still has
visible abrupt pose jumps. BQP and spike_mid are also rejected for insufficient
stabilization or remaining visual issues. The accepted quality recovery result
for this stage is `resid_r15_s07`.
