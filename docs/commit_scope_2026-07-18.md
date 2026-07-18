# Commit Scope - 2026-07-18

## Recommended Commit Theme

```text
docs(results): record Regular performance baseline and presentation package
```

or, if including the Harness contracts and runner changes:

```text
docs(harness): add Regular performance baseline contracts
```

## Include

Project source/config/docs that describe reproducible work:

```text
README.md
AGENTS.md
.gitignore
src/cpu_stabilize.py
scripts/harness_runner.py
scripts/download_nus_category.ps1
scripts/diagnose_local_artifacts.py
configs/harness/
docs/
```

New high-value docs/contracts in this stage:

```text
configs/harness/contracts/regular_performance_baseline_est0p5_grid16.json
configs/harness/contracts/regular_gate_est0p5_grid16_validation_v1.json
configs/harness/contracts/gst_nvmm_decode_convert_latency_v1.json
docs/stage_result_regular_performance_baseline_2026-07-18.md
docs/vpi_warp_module_report_2026-07-18.md
docs/gstreamer_nvmm_latency_plan_2026-07-18.md
docs/presentation/
```

## Do Not Include

Large or local evidence outputs:

```text
results/
data/raw/
data/sources/
C:\Users\Admin\Videos\orin nx\
*.mp4
```

These files are local evidence and review assets. Keep them out of Git unless a
small representative artifact is explicitly selected later.

## Current Evidence To Mention In Commit/PR Text

```text
CPU quality-safe baseline:
  lp_rigid_strength080_dynzoom106, estimate_scale=1.0, feature_grid_size=12

Regular performance baseline:
  lp_rigid_strength080_dynzoom106, estimate_scale=0.5, feature_grid_size=16

Regular validation:
  5/5 pass_all_objective_gates under current evaluator and accepted by user review

VPI boundary:
  VPI backend swap is slower in 640x360 full Python pipeline;
  VPI CUDA accelerates high-resolution warp-heavy module benchmark.

GStreamer/NVMM:
  minimum decode/NVMM/nvvidconv/fakesink probe reaches EOS.
```

## Pre-Commit Checks

```powershell
py -3.12 scripts\harness_runner.py doctor
py -3.12 scripts\harness_runner.py validate-evidence results\evidence\20260718_jetson_regular05_perf --date 20260718
git status --short
git diff --stat
```
