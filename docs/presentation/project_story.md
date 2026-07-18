# Project Story

## One-Liner

Jetson Orin NX real-time EIS project: build a controllable CPU stabilization
pipeline, validate quality with gates and visual review, then measure where
performance optimization and hardware acceleration actually help.

## Problem

The goal is not just to output a stabilized video. A useful engineering project
must answer:

```text
Does it stabilize selected real clips?
What does it cost in latency?
What artifacts remain?
Which optimizations help, and which do not?
```

## Current Result

The project now has two CPU baselines:

```text
quality-safe baseline:
  lp_rigid_strength080_dynzoom106
  estimate_scale=1.0
  feature_grid_size=12

Regular performance baseline:
  lp_rigid_strength080_dynzoom106
  estimate_scale=0.5
  feature_grid_size=16
```

The Regular performance baseline passes objective gates on all five Regular
clips and was accepted by human review.

## Engineering Value

The strongest project story is measurement discipline:

- quality gates are separated from challenge sets;
- Regular performance baseline is measured on Jetson;
- VPI full-pipeline backend swap was rejected because it was slower;
- VPI CUDA was still shown useful for high-resolution warp-heavy modules;
- challenge sets are used to map model boundaries instead of being hidden;
- GStreamer/NVMM dataflow is scoped as a latency boundary, not overclaimed.

## Three-Minute Version

```text
This is a Jetson Orin NX video stabilization project. I started from a
controllable CPU EIS pipeline instead of treating the stabilizer as a black box:
motion estimation, global motion smoothing, warp, crop, and visual review are
all explicit.

The first goal was not just to output a video, but to make the result measurable.
I split the data into a Regular main gate and challenge/diagnostic sets, added
metrics for residual motion, smoothness, crop, and black border, and preserved
side-by-side review videos.

The current Regular performance baseline is lp_rigid with dynamic zoom,
estimate_scale=0.5, and feature_grid_size=16. It passes all five Regular clips
and was accepted by human review. Compared with the quality-safe baseline on the
Regular05 clip, estimate time dropped from 8.568 ms to 3.022 ms and total wall
time dropped from 8.473 s to 7.565 s.

For hardware acceleration, I measured both success and failure. A simple VPI
backend swap was slower in the small full Python pipeline, but VPI CUDA showed
1.35x to 2.33x speedup on high-resolution warp-heavy modules. I also evaluated
challenge sets to map where the global-warp model fails, and verified a minimum
GStreamer/NVMM decode and conversion path. I do not claim EIS acceleration from
GStreamer yet; I use it as a measured dataflow boundary.

The main engineering value is that every claim has a boundary: Regular baseline,
challenge-set limitations, VPI module acceleration, and future NVMM dataflow
work are kept separate.
```

## Evidence

```text
docs/stage_result_regular_performance_baseline_2026-07-18.md
docs/project_showcase_summary_2026-07-18.md
results/regular_gate_est0p5_grid16_validation_20260718/regular_gate_validation_summary.md
docs/challenge_boundary_report_2026-07-18.md
results/gst_nvmm_decode_convert_latency_20260718/summary.md
```
