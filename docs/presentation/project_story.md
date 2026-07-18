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
- GStreamer/NVMM dataflow is scoped as the next latency loop, not overclaimed.

## Evidence

```text
docs/stage_result_regular_performance_baseline_2026-07-18.md
docs/project_showcase_summary_2026-07-18.md
results/regular_gate_est0p5_grid16_validation_20260718/regular_gate_validation_summary.md
```
