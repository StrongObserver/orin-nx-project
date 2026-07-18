# Regular05 Artifact Root Cause - 2026-07-18

## Purpose

The user reported that the tail of the `regular05` output still looks shaky, and
that the perceived issue may be corner stretching / local pull rather than only
global residual shake.

This note separates three possible causes:

- residual global motion is not fully suppressed;
- mask-safety rollback and crop/FOV constraints reintroduce shake;
- global affine warp creates or amplifies local/corner deformation.

## Evidence Inputs

Main clips:

```text
raw:
results/nus_regular_gate_v1/raw_clips/regular_gate05_regular_6.mp4

old crop90 affine:
results/evidence/20260718_jetson_regular05_perf/regular_gate05_regular_6_new_crop90_lanczos_sharp025.mp4

affine dynzoom106:
results/quality_tail_refine_20260718/crop90_dynzoom106_lanczos_sharp025/regular_gate05_crop90_dynzoom106_lanczos_sharp025.mp4

rigid dynzoom106:
results/quality_artifact_root_20260718/lp_rigid_dynzoom106/regular_gate05_lp_rigid_dynzoom106.mp4
```

Diagnostics:

```text
results/quality_artifact_root_20260718/scene_gate_artifact_root.csv
results/quality_artifact_root_20260718/local_regions/local_artifact_summary.csv
results/quality_artifact_root_20260718/artifact_root_eval.csv
results/quality_artifact_root_20260718/artifact_root_summary_table.csv
```

## Key Metrics

| Variant | Layered | SR | Residual Improve | Second Improve | Rollback | Max Zoom | Tail Motion P95 | Tail Corner-Center P95 | Tail Row P95 | Tail Shear P95 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| old_crop90 | stability_pass_smoothness_fail | 3.958 | 0.552 | -0.054 | 149 | 1.00 | 13.441 | 2.235 | 0.960 | 0.02689 |
| affine dynzoom106 | stability_pass_smoothness_fail | 5.754 | 0.704 | -0.027 | 65 | 1.06 | 13.158 | 2.217 | 0.894 | 0.02910 |
| rigid dynzoom106 | pass_all_objective_gates | 6.727 | 0.638 | 0.007 | 55 | 1.06 | 13.254 | 2.287 | 0.890 | 0.02017 |
| affine w4=300 dynzoom106 | pass_all_objective_gates | 7.262 | 0.652 | 0.019 | 49 | 1.06 | 13.243 | 2.403 | 1.060 | 0.02196 |

Scene-gate diagnostics:

```text
raw: challenge_degrade, motion_p95=12.24px, local/global_p95=1.09
old crop90 affine: global_model_risk, local/global_p95=1.85, row_residual_p95=2.15px
affine dynzoom106: normal_candidate by aggregate scene gate
rigid dynzoom106: normal_candidate by aggregate scene gate
```

## Diagnosis

The issue is not only "not enough stabilization".

1. The old crop90 affine output had extreme mask-safety rollback:
   `149/180` frames. This can reintroduce shake, especially near the tail.

2. Dynamic zoom reduces rollback and improves global stability, but it does not
   fully reduce tail corner-center residual. This explains why the user can
   still see tail artifacts after `dynzoom106`.

3. Rigid motion reduces shear proxy substantially:
   `tail_shear_p95` drops from `0.02910` for affine dynzoom106 to `0.02017` for
   rigid dynzoom106. This supports the suspicion that affine degrees of freedom
   contribute to the visible corner-pull feeling.

4. Tail corner-center residual remains high even with rigid dynzoom106:
   `2.287`, still above raw's `1.865`. This means the clip itself contains
   spatially varying motion or local texture/foreground effects that a single
   global model cannot fully explain.

## Current Best Candidate

After the user rejected the full-strength rigid candidate, one more root-cause
driven test was added: reduce stabilization strength instead of changing LP
weights. This targets over-correction from a single global model on the tail
segment.

After user review, the accepted current CPU baseline is:

```text
lp_rigid_strength080_dynzoom106
```

Command delta:

```text
--smoothing-method lp_rigid
--stabilization-strength 0.80
--crop-ratio 0.90
--crop-interpolation lanczos
--sharpen-strength 0.25
--dynamic-zoom
--min-zoom 1.0
--max-zoom 1.06
--zoom-rate-limit 0.003
--zoom-hysteresis 0.02
--lp-trim-ratio 0.10
--lp-w1 50 --lp-w2 10 --lp-w3 20 --lp-w4 30
```

Why this is better than the previous best `lp_rigid_dynzoom106`:

| Variant | Layered | Grade | SR | Residual Improve | Second Improve | Black P95 | Rollback | Tail Motion P95 | Tail Corner-Center P95 | Tail Shear P95 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| lp_rigid_dynzoom106 | pass_all_objective_gates | C_candidate | 6.727 | 0.638 | 0.007 | 0.009961 | 55 | 13.254 | 2.287 | 0.02017 |
| lp_rigid_strength080_dynzoom106 | pass_all_objective_gates | A_or_B_candidate | 6.252 | 0.629 | 0.013 | 0.001497 | 0 | 11.799 | 2.157 | 0.01963 |

The new candidate slightly reduces SR/residual strength, but it improves the
artifact-related dimensions that matter for the user's complaint: no rollback,
lower black-border pressure, lower tail motion, lower corner-center residual,
and lower shear proxy. This is a better tradeoff for the observed tail problem.

Why this is not a complete solution:

- tail corner-center residual remains high;
- the remaining artifact is likely a model boundary of one global warp;
- fully addressing it likely requires mesh/grid warp, rolling-shutter-aware
  correction, gyro/IMU, or scene-gated weakening rather than more LP weight
  sweeping.

## Review Assets

Review copies:

```text
C:\Users\Admin\Videos\orin nx\review\quality\20260718_regular05_artifact_root\20260718_nus_regular_gate_v1_regular_gate05_regular_6_windows_lp_rigid_dynzoom106_lanczos_sharp0p25_compare.mp4
C:\Users\Admin\Videos\orin nx\review\quality\20260718_regular05_artifact_root\20260718_nus_regular_gate_v1_regular_gate05_regular_6_windows_affine_dynzoom106_vs_rigid_dynzoom106_compare.mp4
C:\Users\Admin\Videos\orin nx\review\quality\20260718_regular05_artifact_root\20260718_nus_regular_gate_v1_regular_gate05_regular_6_windows_old_crop90_vs_rigid_dynzoom106_compare.mp4
C:\Users\Admin\Videos\orin nx\review\quality\20260718_regular05_new_method\20260718_nus_regular_gate_v1_regular_gate05_regular_6_windows_lp_rigid_strength080_dynzoom106_compare.mp4
C:\Users\Admin\Videos\orin nx\review\quality\20260718_regular05_new_method\20260718_nus_regular_gate_v1_regular_gate05_regular_6_windows_lprigid100_vs_lprigid080_compare.mp4
C:\Users\Admin\Videos\orin nx\review\quality\20260718_regular05_new_method\20260718_nus_regular_gate_v1_regular_gate05_regular_6_jetson_lp_rigid_strength080_dynzoom106_compare.mp4
```

Jetson verification for `lp_rigid_strength080_dynzoom106`:

```text
avg_estimate_ms=8.5679
avg_warp_ms=7.9362
total_wall_time_s=8.473
mask_safety_rollback_frames=0
p95_invalid_mask_ratio=0.001196
max_invalid_mask_ratio=0.007452
max_black_pixel_ratio=0.000095
max_dynamic_zoom=1.06
```

Human review outcome:

- The user judged this version still imperfect but better than the previous best.
- It is now the CPU baseline for the current stage.
- Keep the model-boundary note: if future review again rejects the tail, do not
  continue global affine/rigid parameter tuning. Move to mesh/grid, RS/gyro-like,
  or scene-gated weakening instead.
