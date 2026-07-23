# Reproducibility Guide

This guide is layered. Start at L0 and stop when you have enough evidence for
your purpose. Local `results/` folders and review videos are intentionally
ignored by Git.

## L0 - Control Plane

Purpose: verify that the project gates, contracts, and startup routing are
healthy.

```powershell
cd "C:\Users\Admin\Desktop\orin nx project"
py -3.12 scripts\harness_runner.py onboard
py -3.12 scripts\harness_runner.py doctor
py -3.12 scripts\harness_runner.py check-claim --gate-id nus_running_gate_v1 --claim main_gate_success_rate
```

Expected:

```text
onboard points to no active task contract and names remap_native_size_pad_crop_probe_v1 as the latest completed contract
doctor_status: pass
nus_running_gate_v1 main_gate_success_rate: forbidden
```

Claim boundary:

```text
Passing L0 proves the control plane is healthy. It does not prove any new
algorithm or performance result.
```

## L1 - Regular Quality And CPU Baseline

Purpose: locate the accepted Regular-gate quality and CPU performance evidence.

Primary docs:

```text
docs/stage_result_regular_performance_baseline_2026-07-18.md
docs/regular_gate_residual_closed_loop_2026-07-21.md
docs/presentation/baseline_and_metrics.md
```

Primary ignored evidence:

```text
results/evidence/20260718_jetson_regular05_perf/
results/regular_gate_est0p5_grid16_validation_20260718/
```

Review assets live outside the repo:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260718_regular_gate_est0p5_grid16_validation\
C:\Users\Admin\Videos\orin nx\review\performance\20260721_regular_gate_residual_closed_loop_full\
```

Expected result summary:

```text
Regular performance baseline:
  lp_rigid_strength080_dynzoom106
  estimate_scale=0.5
  feature_grid_size=16
  NUS Regular gate: 5/5 objective pass and human accepted

resid_r15_s07:
  accepted Regular-gate stabilization-strength recovery result
```

Claim boundary:

```text
This is Regular-gate EIS quality evidence, not all-scene or product-grade EIS.
```

## L2 - VPI Module And Perf/Watt Evidence

Purpose: verify where hardware acceleration helps and where it does not.

Primary docs:

```text
docs/vpi_warp_module_report_2026-07-18.md
docs/presentation/hardware_acceleration_boundary.md
docs/presentation/final_benchmark_table.md
```

Primary ignored evidence:

```text
results/vpi_warp_module_rerun_20260722/
results/vpi_warp_correctness_20260722/
results/power_probe_20260722_sudo/
results/pyr_lk_opencv_vpi_compare_20260722_v2/
```

Expected result summary:

```text
640x360 Python full-pipeline VPI backend swap is slower.
High-resolution PerspectiveWarp benefits from VPI CUDA.
4K PerspectiveWarp:
  OpenCV CPU: 48.995 ms, 20.410 FPS, 1.682 FPS/W
  VPI CUDA:   20.514 ms, 48.747 FPS, 4.385 FPS/W
```

Claim boundary:

```text
This is module-level acceleration and module-level perf/watt evidence. It is not
full EIS pipeline acceleration.
```

## L3 - MMAPI / VPI / NVENC Device Stage

Purpose: inspect the accepted C++ device-side path and its dataflow boundary.

Primary docs:

```text
docs/regular_gate_eglimage_fix_2026-07-20.md
docs/regular05_eglimage_dataflow_cost_2026-07-20.md
docs/regular05_live_eglimage_path_2026-07-20.md
docs/presentation/dataflow_architecture.md
```

Accepted device path:

```text
H264 input
-> MMAPI/NVDEC block-linear NV12 main chain
-> NvBufSurfTransform to pitch-linear NV12_ER scratch
-> VPI CUDA PerspectiveWarp
-> NvBufSurfTransform back to block-linear NV12
-> NVENC
```

Rejected paths:

```text
old pitch-pointer wrapper: visible block tearing
EGLImage image-wrapper reuse: tearing or failures
pitch-linear main encoder chain: near-solid green output
block-linear VPI scratch pair: rejected by VPI
direct mismatched NvBuffer input: format mismatch
```

Claim boundary:

```text
This proves a measured C++ device-stage path. It does not prove full real-time
EIS or zero-copy.
```

## L4 - NvBuffer Pair And Nsight/NVTX

Purpose: verify the device-stage dataflow follow-up and profiling attribution.

Primary docs:

```text
docs/regular_gate_nvbuffer_pair_resid_2026-07-23.md
docs/nsight_device_stage_profile_result_2026-07-23.md
docs/device_stage_lifecycle_budget_2026-07-23.md
docs/device_stage_lifecycle_perf_result_2026-07-23.md
```

Primary ignored evidence:

```text
results/regular_gate_nvbuffer_pair_resid_20260723/
results/regular05_eglimage_timing_resid_compare_20260723/
results/nsight_device_stage_profile_20260723/
results/device_stage_lifecycle_probe_20260723/repeat/
results/device_stage_lifecycle_perf_20260723/
```

Expected result summary:

```text
NvBuffer pair:
  preserves resid_r15_s07
  stage frame100: 7.535 ms -> 7.230 ms
  stage running avg: 9.589 ms -> 9.401 ms

Nsight/NVTX:
  vpiSubmitPerspectiveWarp: about 0.022-0.024 ms
  VPI Perspective Warp: about 0.763-0.805 ms
  dominant cost: wrapper/sync/transform/lifecycle

Stream-only reuse:
  wall mean: 1.946819 s -> 1.843571 s
  stage avg: 10.336381 ms -> 9.680414 ms
```

Claim boundary:

```text
NvBuffer pair and stream-only reuse are small device-stage improvements. They do
not prove zero-copy, queue-depth benefits, or full-pipeline acceleration.
```

## L5 - Public / Interview Package

Purpose: read the project as a portfolio.

Recommended order:

```text
README.md
docs/presentation/final_benchmark_table.md
docs/presentation/dataflow_architecture.md
docs/presentation/claim_boundary.md
docs/evidence_reader_path.md
docs/presentation/interview_qna.md
docs/presentation/resume_bullets.md
```

Before sharing publicly:

```powershell
git status --short
git diff --check
rg -n "password|token|secret|<local-secret-placeholder>" README.md docs configs src scripts AGENTS.md
```

Expected:

```text
No passwords, tokens, raw videos, review videos, or internal source text should
be committed.
```
