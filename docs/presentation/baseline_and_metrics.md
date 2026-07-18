# Baseline And Metrics

## Main Gate

```text
nus_regular_gate_v1
```

Regular is the current main quality and presentation gate. Running, Parallax,
Crowd, and other sets are challenge or diagnostic sets, not headline pass-rate
targets.

## Quality-Safe Baseline

```text
lp_rigid_strength080_dynzoom106
estimate_scale=1.0
feature_grid_size=12
```

Use when the project needs the most conservative current quality setting.

## Regular Performance Baseline

```text
lp_rigid_strength080_dynzoom106
estimate_scale=0.5
feature_grid_size=16
```

Use when the project claim is Regular-gate CPU performance.

## Regular Gate Result

| Clip | SR_pose | residual_improve | second_top5_improve | grade | layered |
|---|---:|---:|---:|---|---|
| regular_gate01 | 19.516 | 0.758 | 0.527 | A/B | pass |
| regular_gate02 | 5.912 | 0.398 | 0.683 | A/B | pass |
| regular_gate03 | 19.323 | 0.804 | 0.743 | A/B | pass |
| regular_gate04 | 16.304 | 0.760 | 0.757 | C | pass |
| regular_gate05 | 6.031 | 0.610 | 0.000 | A/B | pass |

## Metric Meaning

```text
SR_pose:
  How much residual pose energy is reduced. Higher is better.

residual_improve:
  How much unwanted residual translation is reduced. Higher is better.

second_top5_improve:
  High-frequency smoothness non-regression. Negative values mean worse jitter or
  snapback risk; non-negative values are required for this stage.

black/crop gates:
  Hard degradation checks. A result with better stability but visible black
  border or excessive crop is not promoted.

visual review:
  Final veto for frame jump, rollback, jello, local pull, or unacceptable blur.
```

## Visual Boundary

The user accepted all five Regular review videos. The remaining slight tail
shake is treated as the current global-warp EIS model boundary.

## Evidence

```text
results/regular_gate_est0p5_grid16_validation_20260718/regular_gate_validation_summary.md
C:\Users\Admin\Videos\orin nx\review\performance\20260718_regular_gate_est0p5_grid16_validation\
```
