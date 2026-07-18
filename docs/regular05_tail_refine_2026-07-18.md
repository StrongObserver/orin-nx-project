# Regular05 Tail Refinement - 2026-07-18

Status update: this is now an intermediate tuning note. The accepted CPU
baseline was later updated to `lp_rigid_strength080_dynzoom106`; use
`docs/regular05_artifact_root_cause_2026-07-18.md` as the authoritative final
record for the current Regular05 baseline.

## Purpose

The user reviewed the previous `crop90_lanczos_sharp025` side-by-side video and
reported that the first part is acceptable, but the last seconds still shake too
much. This note records the constrained refinement for `regular_gate05_regular_6`.

This is a quality-loop note, not a new final claim. Human visual review remains
required before promoting any candidate to the CPU baseline.

## Diagnosis

The previous Jetson evidence package used:

```text
crop_ratio=0.90
crop_interpolation=lanczos
sharpen_strength=0.25
smoothing_method=lp_affine
lp_trim_ratio=0.10
mask_safety_max_invalid=0.01
```

Summary symptoms:

```text
mask_safety_rollback_frames=149 / 180
mask_safety_avg_beta=0.794
avg_invalid_mask_ratio=0.00872
p95_invalid_mask_ratio=0.009996
```

The tail frames show large correction changes while the invalid-mask ratio sits
near the 0.01 safety limit. The likely cause is not a single tracking failure,
but the crop90 clarity setting leaving little FOV margin. The LP affine
correction and mask-safety rollback fight each other near the end of the clip.

## Candidates

The test stayed intentionally small. It compared:

- slightly smaller fixed crop: `crop89`, `crop88`;
- lower stabilization strength: `strength085`;
- crop90 with bounded dynamic zoom: `dynzoom104`, `dynzoom106`, `dynzoom108`;
- one combined `crop89_dynzoom104`.

Summary table:

```text
results/quality_tail_refine_20260718/tail_refine_summary_table.csv
```

Key rows:

| Candidate | Layered Acceptance | SR | Residual Improve | Second Top5 Improve | Fixed Crop Loss | Rollback Frames | Max Dynamic Zoom |
|---|---|---:|---:|---:|---:|---:|---:|
| baseline_crop90 | stability_pass_smoothness_fail | 3.958 | 0.552 | -0.054 | 0.10 | 149 | 1.00 |
| crop88 | pass_all_objective_gates | 4.537 | 0.585 | 0.014 | 0.12 | 127 | 1.00 |
| strength085 | pass_all_objective_gates | 4.022 | 0.531 | 0.040 | 0.10 | 125 | 1.00 |
| dynzoom104 | pass_all_objective_gates | 5.105 | 0.620 | 0.014 | 0.10 | 90 | 1.04 |
| dynzoom106 | pass_all_objective_gates | 5.644 | 0.653 | 0.011 | 0.10 | 65 | 1.06 |
| dynzoom108 | pass_all_objective_gates | 6.233 | 0.651 | 0.001 | 0.10 | 29 | 1.08 |

## Recommendation

Use `dynzoom106` as the current recommended CPU-baseline candidate, subject to
manual visual review.

Recommended command delta:

```text
--dynamic-zoom
--min-zoom 1.0
--max-zoom 1.06
--zoom-rate-limit 0.003
--zoom-hysteresis 0.02
```

Why not `dynzoom108`:

- it reduces rollback more aggressively;
- but it spends the whole clip at a higher dynamic zoom and has almost zero
  margin on the second-diff improvement metric;
- it risks overpaying in FOV/clarity for a small extra stability gain.

Why not fixed `crop88`:

- it passes objective gates;
- but it permanently increases fixed crop loss from 10% to 12%;
- dynamic zoom is a more targeted fix for a tail-margin problem.

## Evidence

Jetson-run recommended candidate:

```text
results/quality_tail_refine_20260718/crop90_dynzoom106_lanczos_sharp025/
```

Review copies:

```text
C:\Users\Admin\Videos\orin nx\review\quality\20260718_regular05_tail_refine\20260718_nus_regular_gate_v1_regular_gate05_regular_6_jetson_crop90_dynzoom106_lanczos_sharp0p25_compare.mp4
C:\Users\Admin\Videos\orin nx\review\quality\20260718_regular05_tail_refine\20260718_nus_regular_gate_v1_regular_gate05_regular_6_jetson_old_crop90_vs_dynzoom106_compare.mp4
```

Jetson summary for `dynzoom106`:

```text
avg_estimate_ms=8.3274
avg_warp_ms=7.8805
total_wall_time_s=8.343
mask_safety_rollback_frames=65
mask_safety_avg_beta=0.9684
max_dynamic_zoom=1.06
avg_dynamic_zoom=1.06
avg_invalid_mask_ratio=0.00454
p95_invalid_mask_ratio=0.009987
max_black_pixel_ratio=0.000078
```

## Boundary

Do not promote this as the final CPU baseline until the user visually checks the
tail segment and confirms that the extra dynamic zoom does not create an
unacceptable FOV or clarity loss.
