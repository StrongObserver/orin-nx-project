# Next-Stage Reference Review - 2026-07-18

## Purpose

This note reviews the internal-AI next-stage advice against the current Orin NX
EIS project state. It is a decision aid, not a new implementation plan.

## Current Project State Used For Judgment

Already accepted:

```text
Regular performance baseline:
  lp_rigid_strength080_dynzoom106
  estimate_scale=0.5
  feature_grid_size=16
```

Evidence:

```text
Regular gate: 5/5 pass_all_objective_gates
Human review: all five Regular side-by-side videos accepted
Regular05 estimate time: about 8.568 ms -> 3.022 ms
Regular05 total wall time: about 8.473 s -> 7.565 s
```

Known boundaries:

```text
VPI backend swap is slower in the 640x360 Python full pipeline.
VPI CUDA is faster in high-resolution warp-heavy module tests.
GStreamer/NVMM has readiness evidence only, not EIS acceleration.
Mesh/grid warp is future work, not the current implementation path.
```

## Internal-AI Advice Review

| Advice | Decision | Why |
|---|---|---|
| Make VPI high-resolution warp module demo a main line | Adopt | Matches existing 720p to 4K evidence and is low risk. It strengthens the hardware acceleration story without overclaiming full-pipeline speedup. |
| Make Challenge-set boundary package a main line | Adopt | Strong fit for the current global-warp model boundary. It converts remaining artifacts into an operating-envelope analysis. |
| Keep GStreamer/NVMM as dataflow boundary measurement | Adopt with scope limit | Useful Jetson systems story, but must remain decode/convert/readback/encode measurement until EIS integration is justified. |
| Do not implement mesh/grid warp now | Adopt | Correct tradeoff for this stage. It has high research value but large implementation and proof cost. |
| Add VPI output correctness check | Adopt with threshold calibration | Correct direction, but do not blindly use fixed thresholds such as MAE < 1 or SSIM > 0.99 until border/interpolation differences are verified. |
| Use Challenge sets as failure-boundary package | Adopt | Must not become a headline pass rate. Use class-specific pass/boundary/fail explanations. |

## High-Value Information To Carry Forward

1. VPI needs a crossover story:

```text
640x360 full pipeline: VPI backend swap slower.
High-resolution warp module: VPI CUDA faster.
```

2. Challenge sets should explain assumptions:

```text
Regular passes because global-warp assumptions mostly hold.
Running/Parallax/Crowd/QuickRotation expose where those assumptions break.
```

3. GStreamer/NVMM is useful only after boundary timing:

```text
measure decode -> convert -> CPU readback -> encode before EIS integration.
```

4. Mesh/grid belongs in future work:

```text
valuable for local/parallax/RS-like artifacts, but too large for the next loop.
```

## Items That Still Need Verification

| Item | Needed verification |
|---|---|
| VPI output correctness | Compare OpenCV CPU and VPI CUDA warp output on same transforms, with border/interpolation differences stated. |
| VPI crossover point | Repackage existing 640x360 negative result and 720p-4K positive result into one curve/table. |
| Challenge-set boundaries | Run or summarize fixed-baseline outputs on Running/Parallax/Crowd/QuickRotation and label each as pass/boundary/fail by role. |
| GStreamer/NVMM dataflow | Repeat the minimum pipeline and add CPU boundary measurement before any EIS integration. |

## Working Decision

Proceed with two main next-stage evidence chains:

```text
P0 main line A: VPI high-resolution module demo/report
P0 main line B: Challenge-set boundary package
```

Keep one scoped support line:

```text
P1 support line: GStreamer/NVMM latency boundary
```

Defer:

```text
Mesh/grid warp implementation
```
