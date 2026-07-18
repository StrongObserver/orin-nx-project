# Orin NX EIS Evaluation System V1 - 2026-07-17

## Purpose

This document defines the lifecycle evaluation system for the Orin NX EIS
project. The goal is to keep future experiments comparable: datasets, metric
layers, claim boundaries, and manual review labels should stay stable across
algorithm and performance work.

This is not an algorithm progress log. It is the evaluation contract that sits
under Harness V1 and Loop Engineering V2.

## Source Basis

The user asked to adapt evaluation ideas from the local Typora reference folder
listed in the current oral-template prompt. The conclusions below are rewritten
as public-project evaluation rules; internal source text, private links, and
local note paths are not copied here.

The useful ideas are:

- split core regression sets from badcase/boundary sets;
- objective metrics must be calibrated against human review before becoming
  hard gates;
- IQA metrics such as PSNR, SSIM, LPIPS, DISTS, VIF, FSIM, CLIP/DINO-like
  features are useful but task-dependent;
- sharpness is not quality by itself: acutance, texture, ringing, noise, and
  subjective detail preservation must be separated;
- every metric needs a role: hard gate, soft gate, diagnostic, or calibration.

The non-useful or deferred parts:

- generic image IQA datasets do not replace EIS video stabilization gates;
- MLLM/IQA scoring is not a current hard gate;
- full camera/OIS chart lab methods are future reference, not current offline
  MP4 EIS evaluation.

## Machine-Readable Files

| File | Role |
|---|---|
| `configs/harness/evaluation_datasets.json` | Lifecycle dataset registry |
| `configs/harness/metric_schema.json` | Metric layers, thresholds, and adoption rules |
| `configs/harness/gates.json` | Active gate/claim boundaries |
| `configs/harness/loop_profiles.json` | Loop profiles that consume these datasets/metrics |

Quick checks:

```powershell
py -3.12 scripts\harness_runner.py list-evaluation-datasets
py -3.12 scripts\harness_runner.py check-evaluation-datasets
py -3.12 scripts\harness_runner.py list-metric-schema
```

## Dataset Layers

### P0 Main And Current Evidence

| Dataset | Role | Status | Use |
|---|---|---|---|
| `nus_regular_gate_v1` | main_gate | active_prepared | Main selected Regular quality evidence |
| `nus_running_gate_v1` | challenge_gate | active_prepared | Running/high-frequency boundary |
| `regular05_perf_gate` | performance_gate | active_prepared | Jetson same-input performance evidence |

These are the only P0 prepared gates for headline project claims.

### P1 Lifecycle Boundary Sets

| Dataset | Role | Status | Use |
|---|---|---|---|
| `nus_quickrotation_challenge_v1` | challenge_gate | active_prepared | Curated fast rotation boundary |
| `nus_zooming_diagnostic_v1` | diagnostic | active_prepared | Curated intentional zoom / intent preservation |
| `nus_parallax_challenge_v1` | challenge_gate | active_prepared | Curated parallax / global-affine model limit |
| `nus_crowd_diagnostic_v1` | diagnostic | active_prepared | Curated foreground/crowd motion contamination |

Current local NUS source status:

- Available and extracted: `Regular`, `Running`, `QuickRotation`, `Zooming`,
  `Parallax`, `Crowd`.
- Prepared lifecycle sets: `Regular`, `Running`, `QuickRotation`, `Zooming`,
  `Parallax`, `Crowd`.
- `Parallax` curated indices: `0,1,5,7-17`; full-category candidates removed
  indices `2,3,6` for short duration and index `4` for weak stable-reference
  improvement under the current proxy validation.
- `Crowd` curated indices: `0-20,22`; full-category candidate index `21` was
  removed for short duration.
- `Parallax.zip` and `Crowd.zip` are both below the 3GB user-download boundary.
  The official source is slow and can stall, so `scripts\download_nus_category.ps1`
  supports Range chunk mode for resumable acquisition.

P1 sets are designed to be redundant and lifecycle-oriented. They should not
all be converted into one headline pass rate.

### P2 Metric Calibration

| Dataset family | Role | Status | Use |
|---|---|---|---|
| LIVE / TID / CSIQ / IVC / Toyama | metric_calibration | planned_reference_only | Image IQA sanity and subjective-correlation background |
| LIVE-VQC / KoNViD-1k / YouTube-UGC | metric_calibration | planned_reference_only | Future video quality metric calibration |

These datasets are not EIS gates. Use them only after a concrete
`evaluation_loop` asks whether a visual-quality diagnostic metric should be
calibrated.

## Metric Layers

### Hard Degradation Gates

These protect output quality even when stability metrics improve.

| Metric | Current rule | Source |
|---|---|---|
| `crop_loss_ratio` | pass < 0.10, hard fail > 0.15 | `evaluate_baseline_v1.py` |
| `black_border_ratio` | mean pass < 0.001, p95 hard fail > 0.01 | `evaluate_baseline_v1.py` |

### EIS Core Motion Metrics

These are soft gates and must be paired with side-by-side review.

| Metric | Current rule | Meaning |
|---|---|---|
| `sr_residual_pose` | pass > 1.2, fail < 1.0 | Residual pose energy reduction |
| `improve_residual_trans_std` | pass >= 0.15, acceptable >= 0.10 | Residual translation STD improvement |
| `improve_second_diff_top5_mean` | non-regression >= 0 | High-frequency pose acceleration non-regression |
| `layered_acceptance` | derived | Separates hard gates, stability, smoothness, and role |

### Scene Gate Diagnostics

These route clips into main/challenge/diagnostic roles:

- `motion_p95`
- `local_global_ratio_p95`
- `row_residual_range_p95`
- `running_band_energy_ratio`
- `scene_gate_class`

Scene diagnostics do not decide quality. They decide where quality should be
judged.

### Visual Quality Diagnostics

Currently supported:

- `laplacian_var_mean`
- `tenengrad_mean`
- `laplacian_ratio_vs_raw`

Planned only after calibration:

- PSNR / SSIM / MS-SSIM / VIF / FSIM / LPIPS / DISTS;
- CLIP/DINO-like features;
- Visual Noise;
- Ringing / acutance-style metrics.

Do not turn these into hard gates until enough Orin EIS side-by-side human
review labels exist.

### Affine Artifact Diagnostics

These help explain shape distortion risk:

- `scale_abs_delta_p95`;
- `anisotropy_abs_delta_p95`;
- `shear_proxy_p95`.

They are diagnostic only.

### Performance Metrics

These support performance claims only with `platform_label=jetson`:

- `avg_estimate_ms`;
- `avg_warp_ms`;
- `total_wall_time_s`;
- FPS derived from the same-input run.

Windows timing is development evidence only.

## Manual Visual Veto

Manual review remains authoritative for:

- `frame_shift`;
- `rollback_or_snapback`;
- `jello_or_rolling_shutter_artifact`;
- `local_distortion_or_corner_pull`;
- `continuous_black_border`;
- `unacceptable_blur_or_detail_loss`;
- `over_sharpen_or_ringing`;
- `foreground_or_parallax_failure`;
- `intent_motion_over_suppressed`.

If manual review vetoes a result, do not argue from proxy metrics.

## How A Future Agent Should Use This

1. Run:

```powershell
py -3.12 scripts\harness_runner.py doctor
py -3.12 scripts\harness_runner.py list-loop-profiles
py -3.12 scripts\harness_runner.py list-evaluation-datasets
py -3.12 scripts\harness_runner.py list-metric-schema
```

2. Pick a loop profile.

3. Pick a dataset role:

- main quality: `nus_regular_gate_v1`;
- challenge/boundary: Running / QuickRotation / Parallax;
- diagnostic: Zooming / Crowd;
- performance: `regular05_perf_gate`;
- metric calibration: IQA/VQA only after explicit evaluation-loop request.

4. Use metrics according to their layer.

5. Produce review assets for any quality claim and copy them to:

```text
C:\Users\Admin\Videos\orin nx
```

## Current Gaps

1. `Parallax` and `Crowd` are now prepared as curated P1 lifecycle sets. If the
   local source archives are lost, reacquire them through chunked resume:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\download_nus_category.ps1 -Category Parallax -ChunkSizeMB 8 -Extract
powershell -ExecutionPolicy Bypass -File scripts\download_nus_category.ps1 -Category Crowd -ChunkSizeMB 8 -Extract
```

2. Visual-quality metrics are diagnostic only. They need human-review
   calibration before becoming gates.
3. The next project action is still Jetson same-input performance evidence for
   `regular_gate05_regular_6.mp4`.

