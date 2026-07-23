# Local Warp Quality Bridge - 2026-07-23

## Decision

The completed Remap operator/device-stage work is valuable, but a static local
Remap correction did not improve the selected real parallax boundary sample.

Classification:

```text
C. No useful quality gain from this simple local correction.
```

This is still useful evidence. It shows that moving from operator-level Remap to
actual EIS quality requires a dynamic model, not a fixed per-cell offset.

## Sample Selection

Primary sample:

```text
results/nus_parallax_challenge_v1_curated/raw_clips/parallax10_parallax_13.mp4
```

Reason:

```text
scene_gate: challenge_degrade
motion_p95: 19.56 px
local/global_p95: 1.30
row_residual_p95: 2.23 px
```

Backup sample:

```text
results/nus_parallax_challenge_v1_curated/raw_clips/parallax09_parallax_12.mp4
```

Reason:

```text
scene_gate: challenge_degrade
motion_p95: 22.36 px
local/global_p95: 1.26
row_residual_p95: 1.86 px
```

## Local Residual Problem

Residual grid diagnosis on `parallax10_parallax_13`:

```text
results/local_warp_quality_bridge_20260723/sample_selection/parallax10_residual_grid/
results/local_warp_quality_bridge_20260723/parallax10_local_problem/
```

Baseline summary:

| Metric | Value |
|---|---:|
| global_residual_p95_avg | 2.196383 |
| global_residual_p95_p95 | 2.783206 |
| cell_mean_max_avg | 1.974301 |
| cell_mean_range_avg | 1.446885 |
| cell_mean_range_p95 | 2.120624 |

Highest residual cells by p95:

| Cell | mean_dx | mean_dy | mean_mag | p95_mag |
|---|---:|---:|---:|---:|
| gx0 gy3 | 0.149994 | 0.067958 | 1.508778 | 3.364291 |
| gx3 gy3 | 0.041478 | -0.064248 | 1.279262 | 3.227309 |
| gx3 gy0 | 0.135763 | 0.085972 | 1.347632 | 3.225410 |

This confirms a real local/global mismatch before any correction.

## Prototype

Tracked script:

```text
scripts/apply_local_remap_correction.py
```

Method:

```text
1. Estimate a cell-level residual direction from existing residual-grid data.
2. Build a spatial Gaussian falloff map around one target cell.
3. Apply a bounded inverse dx/dy correction with OpenCV remap.
4. Re-run residual-grid diagnosis.
```

This is deliberately minimal. It does not implement dynamic mesh paths,
depth-layer segmentation, rolling-shutter correction, or gyro-assisted EIS.

## Results

| Candidate | Target | Strength | global_residual_p95_avg | cell_mean_max_avg | cell_mean_range_avg | Outcome |
|---|---|---:|---:|---:|---:|---|
| baseline | none | 0.0 | 2.196383 | 1.974301 | 1.446885 | reference |
| local correction | gx0 gy3 | 1.0 | 2.216424 | 2.002721 | 1.463025 | worse |
| local correction | gx0 gy3 | 0.5 | 2.198613 | 1.986436 | 1.449056 | neutral/slightly worse |
| local correction | gx3 gy3 | 0.5 | 2.200762 | 1.996831 | 1.459487 | worse |
| local correction | gx3 gy0 | 0.5 | 2.205726 | 1.987898 | 1.448646 | worse/neutral |

Interpretation:

```text
A fixed local correction based on average cell residual does not solve this
parallax sample. The residual is dynamic and scene-dependent, not a static
per-cell bias.
```

## Review Evidence

Review video:

```text
C:\Users\Admin\Videos\orin nx\review\diagnostic\20260723_local_warp_quality_bridge\20260723_local_warp_bridge_parallax10_source_vs_candidates_grid.mp4
```

Panel order:

```text
source / local gx0 gy3 s0.5
local gx3 gy3 s0.5 / local gx3 gy0 s0.5
```

This is diagnostic evidence only. It is not a candidate for Regular-gate quality.

## Why P5/P6 Were Not Triggered

The contract required CPU/OpenCV local correction to show value before moving to
VPI C++ Remap or MMAPI Remap integration.

It did not show value:

```text
local residual metrics did not improve
some global/local residual metrics became slightly worse
```

Therefore:

```text
Do not port this static correction to VPI/MMAPI.
Do not claim local-warp quality improvement.
Do not continue blind static-cell corrections.
```

## Engineering Meaning

Remap remains useful:

```text
VPI C++ Remap works.
Remap-MMAPI scratch diagnostic works under size constraints.
```

But this loop shows the missing part for quality:

```text
The hard part is not the Remap operator.
The hard part is estimating a meaningful per-frame, spatially varying correction
that does not introduce new local distortion.
```

Likely future routes:

```text
dynamic mesh path optimization
foreground/background or depth-layer separation
rolling-shutter-aware model
gyro-assisted camera path
industrial EIS reference for local mesh constraints
```

## Boundary

Allowed claim:

```text
We tested whether the completed Remap operator path could improve a real
parallax/global-warp boundary via a constrained static local correction. It did
not improve metrics, so the next quality step requires a richer dynamic model.
```

Forbidden claim:

```text
local Remap improves EIS quality
mesh/local warp is solved
parallax challenge is solved
Remap-MMAPI should replace the accepted Regular path
```
