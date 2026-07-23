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
onboard prints oral_template_full_text_begin/end, oral_template_full_read: True, rules_first: True, required_sections: pass, execution_mode, active_task_contract: none, and the latest completed contract
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

## L5 - Remap Operator And Native-Size Pad/Crop

Purpose: reproduce the current Remap operator/dataflow boundary without opening
a new quality loop.

Primary docs:

```text
docs/vpi_remap_cpp_probe_2026-07-23.md
docs/remap_mmapi_integration_probe_2026-07-23.md
docs/remap_native_size_pad_crop_probe_2026-07-23.md
```

Tracked implementation:

```text
experiments/vpi_cpp_remap_probe/remap_probe.cpp
scripts/patch_mmapi_vpi_transcode_eglimage_remap_probe.py
scripts/patch_mmapi_vpi_transcode_eglimage_remap_pad_crop_probe.py
```

Primary ignored evidence:

```text
results/vpi_remap_cpp_probe_20260723/
results/remap_mmapi_integration_probe_20260723/
results/remap_native_size_pad_crop_probe_20260723/
```

Review assets live outside the repo:

```text
C:\Users\Admin\Videos\orin nx\review\diagnostic\20260723_vpi_remap_cpp_probe\
C:\Users\Admin\Videos\orin nx\review\diagnostic\20260723_remap_mmapi_integration_probe\
C:\Users\Admin\Videos\orin nx\review\diagnostic\20260723_remap_native_size_pad_crop_probe\
```

Native-size pad/crop reproduction outline:

```powershell
# Windows side: upload the tracked patch script if needed.
scp scripts\patch_mmapi_vpi_transcode_eglimage_remap_pad_crop_probe.py nvidia@192.168.55.1:/home/nvidia/orin-nx-project/scripts/
```

```bash
# Jetson side: copy a fresh MMAPI sample, patch, and build.
cd /home/nvidia/orin-nx-project/_mmapi_work/jetson_multimedia_api/samples
cp -a 16_multivideo_transcode 99_vpi_transcode_matrix_eglimage_remap_pad_crop_probe
cd /home/nvidia/orin-nx-project
python3 scripts/patch_mmapi_vpi_transcode_eglimage_remap_pad_crop_probe.py \
  --sample-dir /home/nvidia/orin-nx-project/_mmapi_work/jetson_multimedia_api/samples/99_vpi_transcode_matrix_eglimage_remap_pad_crop_probe
cd /home/nvidia/orin-nx-project/_mmapi_work/jetson_multimedia_api/samples/99_vpi_transcode_matrix_eglimage_remap_pad_crop_probe
make -j2
```

```bash
# Jetson side: run identity and wave_safe diagnostics.
ROOT=/home/nvidia/orin-nx-project
OUT=$ROOT/results/remap_native_size_pad_crop_probe_20260723
INPUT=$ROOT/results/regular_gate_safe103_crop98_validation_20260720/regular_gate05_regular_6/source.h264
mkdir -p "$OUT"

VPI_REMAP_MODE=identity ./multivideo_transcode num_files 1 \
  "$INPUT" H264 "$OUT/remap_identity_native_pad_crop.h264" H264 \
  > "$OUT/remap_identity_native_pad_crop.log" 2>&1

VPI_REMAP_MODE=wave_safe ./multivideo_transcode num_files 1 \
  "$INPUT" H264 "$OUT/remap_wave_safe_native_pad_crop.h264" H264 \
  > "$OUT/remap_wave_safe_native_pad_crop.log" 2>&1
```

Expected result summary:

```text
main chain remains 640x360
VPI scratch and Remap payload are 640x368
identity and wave_safe return rc=0
both outputs are readable
black-border p95 is 0 in the recorded validation
```

Optional local log summary:

```powershell
py -3.12 scripts\summarize_remap_pad_crop_log.py `
  --log results\remap_native_size_pad_crop_probe_20260723\remap_identity_native_pad_crop.log `
  --out-dir results\remap_native_size_pad_crop_probe_20260723\summary_identity

py -3.12 scripts\summarize_remap_pad_crop_log.py `
  --log results\remap_native_size_pad_crop_probe_20260723\remap_wave_safe_native_pad_crop.log `
  --out-dir results\remap_native_size_pad_crop_probe_20260723\summary_wave_safe
```

Claim boundary:

```text
This reproduces a Remap operator/dataflow size-layout boundary. It does not
prove EIS quality improvement, zero-copy, or full-pipeline acceleration.
```

## L5.5 - CUDA / MMAPI Interop Safety Verifier

Purpose: verify that CUDA can safely read/write the current MMAPI pitch-linear
NV12_ER scratch boundary through EGLImage interop before any CUDA warp
integration or acceleration claim.

Primary docs:

```text
docs/cuda_mmapi_interop_safety_verifier_2026-07-24.md
configs/harness/contracts/cuda_mmapi_interop_safety_verifier_v1.json
```

Tracked implementation:

```text
scripts/patch_mmapi_cuda_interop_safety_verifier.py
```

Primary ignored evidence:

```text
results/cuda_mmapi_interop_safety_verifier_20260724/
```

Review asset:

```text
C:\Users\Admin\Videos\orin nx\review\diagnostic\20260724_cuda_mmapi_interop_safety_verifier\20260724_cuda_mmapi_interop_regular05_jetson_identity_marker_dynamicmarker_grid_fix01.mp4
```

Reproduction outline:

```powershell
scp scripts\patch_mmapi_cuda_interop_safety_verifier.py nvidia@192.168.55.1:/home/nvidia/orin-nx-project/scripts/
```

```bash
ROOT=/home/nvidia/orin-nx-project
SAMPLES=$ROOT/_mmapi_work/jetson_multimedia_api/samples
SAMPLE=$SAMPLES/99_vpi_transcode_cuda_interop_safety_verifier
cp -a "$SAMPLES/16_multivideo_transcode" "$SAMPLE"
python3 "$ROOT/scripts/patch_mmapi_cuda_interop_safety_verifier.py" --sample-dir "$SAMPLE"
cd "$SAMPLE"
make -j2
```

```bash
ROOT=/home/nvidia/orin-nx-project
OUT=$ROOT/results/cuda_mmapi_interop_safety_verifier_20260724
INPUT=$ROOT/results/regular_gate_safe103_crop98_validation_20260720/regular_gate05_regular_6/source.h264
mkdir -p "$OUT"

CUDA_INTEROP_MODE=identity ./multivideo_transcode num_files 1 \
  "$INPUT" H264 "$OUT/cuda_interop_identity.h264" H264 \
  > "$OUT/cuda_interop_identity.log" 2>&1

CUDA_INTEROP_MODE=marker CUDA_INTEROP_MARKER_X=16 CUDA_INTEROP_MARKER_Y=16 ./multivideo_transcode num_files 1 \
  "$INPUT" H264 "$OUT/cuda_interop_marker.h264" H264 \
  > "$OUT/cuda_interop_marker.log" 2>&1

CUDA_INTEROP_MODE=dynamic_marker ./multivideo_transcode num_files 1 \
  "$INPUT" H264 "$OUT/cuda_interop_dynamic_marker.h264" H264 \
  > "$OUT/cuda_interop_dynamic_marker.log" 2>&1
```

Expected result summary:

```text
identity, marker, and dynamic_marker return rc=0
all outputs are readable 640x360 H264
black-border p95 is 0 for all three corrected modes
large-plane shift/dynamic_shift modes are not accepted; visual review found tearing
```

Claim boundary:

```text
This verifies CUDA/MMAPI scratch interop safety at diagnostic level. It does not
prove EIS quality improvement, zero-copy, full real-time EIS, or accepted MMAPI
CUDA acceleration.
```

## L5.6 - CUDA Affine MMAPI Diagnostic

Purpose: inspect the negative boundary found when moving from safe CUDA marker
writes to custom CUDA affine/random-sampling kernels inside the same MMAPI
scratch path.

Primary docs:

```text
docs/cuda_affine_mmapi_diagnostic_2026-07-24.md
configs/harness/contracts/cuda_affine_mmapi_diagnostic_v1.json
```

Tracked implementation:

```text
scripts/patch_mmapi_cuda_affine_diagnostic.py
```

Primary ignored evidence:

```text
results/cuda_affine_mmapi_diagnostic_20260724/
results/cuda_affine_mmapi_diagnostic_20260724_fix05/
results/cuda_affine_mmapi_diagnostic_20260724_sync11/
results/cuda_affine_mmapi_diagnostic_20260724_direct10/
```

Expected result summary:

```text
identity CUDA kernel path is readable
translate / affine random-sampling over EGL-mapped pitch-linear NV12_ER scratch
is rejected because visual review showed severe tearing or unrelated corruption
NvBufSurfaceSyncForDevice on the CUDA output scratch segfaulted in this path
```

Claim boundary:

```text
This is negative integration evidence. Do not claim an accepted MMAPI CUDA affine
warp path, zero-copy, full-pipeline acceleration, or EIS quality improvement.
```

## L5.7 - CUDA Double-Surface Debug

Purpose: follow the internal-AI Test0-Test2 path to isolate whether the CUDA
failure is in the base VIC/encode path, full-frame CUDA copy, or spatial
random-sampling translate.

Primary docs:

```text
docs/cuda_double_surface_debug_2026-07-24.md
configs/harness/contracts/cuda_double_surface_debug_v1.json
```

Tracked implementation:

```text
scripts/patch_mmapi_cuda_double_surface_debug.py
```

Primary ignored evidence:

```text
results/cuda_double_surface_debug_20260724/
```

Expected result summary:

```text
Test0 VIC round-trip: rc=0, readable, no tearing
Test1 dual-surface CUDA full-frame copy: rc=0, readable, no tearing
Test2 dual-surface CUDA integer translate: rc=0 but visual tearing/distortion
```

Claim boundary:

```text
This narrows the blocker to spatial random sampling/remap over the current
EGL-mapped NV12_ER scratch route. It is not an accepted CUDA warp or acceleration
result.
```

## L6 - Public / Interview Package

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
