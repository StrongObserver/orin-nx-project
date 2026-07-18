# Challenge Boundary Report - 2026-07-18

## Purpose

This report explains where the current Regular performance baseline applies and
where the global-warp EIS model reaches its boundary.

Baseline under test:

```text
lp_rigid_strength080_dynzoom106
estimate_scale=0.5
feature_grid_size=16
opencv_cpu
```

This is not a new tuning loop. The baseline was frozen before running challenge
clips.

## Summary

| Category | Clips | Objective result | Boundary label | Main attribution |
|---|---:|---|---|---|
| Running | 2 | 1 pass, 1 black-border hard fail | boundary | High-frequency motion creates FOV pressure and black-border risk. |
| QuickRotation | 2 | 2 black-border hard fails | fail / boundary | Fast rotation exceeds crop/FOV budget and exposes global-warp limits. |
| Parallax | 2 | 2 black-border hard fails | fail / boundary | One global transform cannot cover foreground/background depth variation cleanly. |
| Crowd | 2 | 2 black-border hard fails | diagnostic boundary | Foreground/crowd motion and FOV pressure make global estimation less reliable. |

## Per-Clip Result

| Clip | SR_pose | residual_improve | second_top5_improve | black_p95 | grade | layered |
|---|---:|---:|---:|---:|---|---|
| running_01 | 2.883 | 0.329 | 0.392 | 0.009612 | D | hard_fail_black_border |
| running_02 | 3.749 | 0.501 | 0.366 | 0.000004 | A_or_B_candidate | pass_all_objective_gates |
| quickrot_01 | 1.109 | -0.050 | 0.055 | 0.031165 | D | hard_fail_black_border |
| quickrot_02 | 1.152 | 0.051 | 0.071 | 0.009090 | D | hard_fail_black_border |
| parallax_01 | 1.129 | 0.040 | 0.344 | 0.141948 | D | hard_fail_black_border |
| parallax_02 | 1.096 | 0.125 | -0.442 | 0.012967 | D | hard_fail_black_border |
| crowd_01 | 1.256 | 0.093 | 0.646 | 0.253666 | D | hard_fail_black_border |
| crowd_02 | 1.884 | 0.067 | 0.610 | 0.019954 | D | hard_fail_black_border |

## Interpretation

The challenge result is useful because it separates in-domain success from
out-of-domain model limitations:

```text
Regular gate:
  5/5 objective pass and human accepted.

Challenge samples:
  mostly fail by black-border/FOV pressure, weak residual improvement, or
  scene-specific model assumptions.
```

This means the current baseline is suitable as a Regular performance baseline,
not as a product-grade all-scene EIS solution.

## How To Present This

Good wording:

```text
I validated the global-warp EIS baseline on the Regular gate and then used
challenge categories to map the operating envelope. Running, fast rotation,
parallax, and crowd scenes expose FOV pressure, foreground/background motion, and
global-model limits. I do not merge those into the headline pass rate; I use them
to justify future work such as dataflow optimization or mesh/RS-aware models.
```

Avoid:

```text
The algorithm solves Running or Parallax.
The challenge pass rate is the main quality score.
Black-border hard failures are acceptable because stability improved.
```

## Evidence

```text
results/challenge_boundary_package_20260718/eval/challenge_boundary_eval.csv
results/challenge_boundary_package_20260718/stabilized/
results/challenge_boundary_package_20260718/visual/
C:\Users\Admin\Videos\orin nx\review\challenge\20260718_challenge_boundary_package\
```

## Next Step

Use this report as the model-boundary evidence chain. Do not tune the Regular
baseline inside the challenge package. If a future stage wants to improve these
categories, create a new contract for mesh/grid warp, rolling-shutter-aware
models, or scene-specific degradation policy.
