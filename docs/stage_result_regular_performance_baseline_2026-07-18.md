# Regular Performance Baseline Stage Result - 2026-07-18

## Stage Decision

The current Regular performance baseline is:

```text
lp_rigid_strength080_dynzoom106
estimate_scale=0.50
feature_grid_size=16
```

The quality-safe baseline remains:

```text
lp_rigid_strength080_dynzoom106
estimate_scale=1.00
feature_grid_size=12
```

Use the performance baseline for Regular-gate speedup claims. Use the
quality-safe baseline when the safest single-clip quality setting is more
important than speed.

## Why This Is Accepted

`est0p5_grid16` was first accepted by human review on `regular_gate05`. It was
then validated across all five `nus_regular_gate_v1` clips:

| Clip | SR_pose | residual_improve | second_top5_improve | grade | layered |
|---|---:|---:|---:|---|---|
| regular_gate01 | 19.516 | 0.758 | 0.527 | A/B | pass |
| regular_gate02 | 5.912 | 0.398 | 0.683 | A/B | pass |
| regular_gate03 | 19.323 | 0.804 | 0.743 | A/B | pass |
| regular_gate04 | 16.304 | 0.760 | 0.757 | C | pass |
| regular_gate05 | 6.031 | 0.610 | 0.000 | A/B | pass |

The user reviewed all five Regular side-by-side videos and accepted them. The
remaining tail shake and small residual artifacts are treated as the current
global-warp EIS model boundary.

## Performance Meaning

On `regular_gate05_regular_6`:

| Config | avg_estimate_ms | avg_warp_ms | total_wall_time_s |
|---|---:|---:|---:|
| quality-safe baseline, est1p0 grid12 | 8.568 | 7.936 | 8.473 |
| performance baseline, est0p5 grid16 | 3.022 | 7.897 | 7.565 |

This is about a 65% reduction in motion-estimation time and about an 11%
reduction in total wall time on the selected Regular05 evidence clip.

## Boundaries

Do not overclaim this result:

- It is a Regular-gate performance baseline, not product-grade EIS.
- It does not prove Running, Parallax, Crowd, or rolling-shutter-heavy scenes are
  solved.
- It does not prove VPI full-pipeline acceleration.
- It does not remove the need to explain the global-warp model boundary.

## Related Evidence

```text
results/evidence/20260718_jetson_regular05_perf/
results/estimate_scale_quality_perf_20260718/quality_perf_summary.md
results/regular_gate_est0p5_grid16_validation_20260718/regular_gate_validation_summary.md
C:\Users\Admin\Videos\orin nx\review\performance\20260718_regular_gate_est0p5_grid16_validation\
```

## Next Engineering Direction

The CPU Regular baseline is now good enough to stop local parameter tuning.

Next work should move to one of these controlled directions:

1. GStreamer/NVMM latency contract: quantify decode/convert/CPU-boundary costs.
2. High-resolution VPI module presentation: keep it as a module-level hardware
   acceleration result.
3. Commit hygiene and presentation packaging: prepare the project for review
   without committing local videos or raw data.
