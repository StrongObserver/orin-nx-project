# Performance Optimization

## Optimization Target

The main CPU cost before optimization was motion estimation.

Quality-safe baseline on `regular_gate05_regular_6`:

| Config | avg_estimate_ms | avg_warp_ms | total_wall_time_s |
|---|---:|---:|---:|
| estimate_scale=1.0, grid12 | 8.568 | 7.936 | 8.473 |

## Tested Speed Knob

`estimate_scale` reduces motion-estimation resolution.

Initial simple downscale results:

| Candidate | avg_estimate_ms | total_wall_time_s | second_top5_improve | Result |
|---|---:|---:|---:|---|
| est0p75 | 6.350 | 8.091 | -0.018 | rejected |
| est0p5 | 3.020 | 7.647 | -0.003 | rejected |

Both were faster but failed smoothness.

## Accepted Performance Baseline

Adding denser grid features made the low-resolution estimate path acceptable:

| Config | avg_estimate_ms | avg_warp_ms | total_wall_time_s |
|---|---:|---:|---:|
| estimate_scale=0.5, grid16 | 3.022 | 7.897 | 7.565 |

Result:

```text
motion-estimation time: about 65% lower
Regular05 total wall time: about 11% lower
Regular gate: 5/5 pass_all_objective_gates
```

## Why This Is A Good Story

This is not a random parameter sweep. It follows a clear pattern:

```text
find hot stage -> change one variable -> reject speed-only regressions -> add
robustness -> validate across Regular gate -> preserve quality-safe fallback
```

## Evidence

```text
results/estimate_scale_quality_perf_20260718/quality_perf_summary.md
results/regular_gate_est0p5_grid16_validation_20260718/regular_gate_validation_summary.md
```
