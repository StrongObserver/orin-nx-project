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

The project has a closed Regular-gate quality result and two CPU baselines:

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

The current Regular-gate stabilization-strength recovery result is
`resid_r15_s07`. It was accepted by human review because it is visibly stronger
than BQP/spike_mid, without hard pose snaps or visible black borders.

## Engineering Value

The strongest project story is measurement discipline:

- quality gates are separated from challenge sets;
- Regular performance baseline is measured on Jetson;
- VPI full-pipeline backend swap was rejected because it was slower;
- VPI CUDA was still shown useful for high-resolution warp-heavy modules;
- 4K PerspectiveWarp also has board-level perf/W evidence;
- VPI PyrLK and Remap were tested and rejected as short-term replacement routes;
- MMAPI/EGLImage dataflow was decomposed into wrapper, sync, and transform costs;
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
and was accepted by human review. Later, after BQP and spike_mid were rejected
as too weak, the residual closed-loop candidate resid_r15_s07 was accepted as
the current Regular-gate stabilization-strength recovery result.

For hardware acceleration, I measured both success and failure. A simple VPI
backend swap was slower in the small full Python pipeline, but VPI CUDA showed
clear gains on high-resolution PerspectiveWarp. In the latest 4K stable
workload, OpenCV CPU ran at 48.995 ms per frame and 1.682 FPS/W, while VPI CUDA
ran at 20.514 ms and 4.385 FPS/W. I also tested VPI PyrLK and Remap: PyrLK can
run on CPU/CUDA but is not a good OpenCV replacement under the current probe,
and Python Remap hits a native binding abort, so Remap would need a C++/official
sample path.

On the device-side path, I moved away from Python appsink/appsrc and used the
C++ MMAPI/VPI/NVENC path as the performance frontier. The latest submit/sync
probe shows that vpiSubmit itself is almost free, while wrapper lifecycle,
stream sync, and NvBufSurfTransform dominate the stage cost. This keeps the
claim honest: module acceleration and measured dataflow boundaries, not a
finished zero-copy real-time EIS product.

The main engineering value is that every claim has a boundary: Regular baseline,
challenge-set limitations, VPI module acceleration, perf/W evidence, and
MMAPI/NVMM dataflow boundaries are kept separate.
```

## Evidence

```text
docs/stage_result_regular_performance_baseline_2026-07-18.md
docs/project_showcase_summary_2026-07-18.md
results/regular_gate_est0p5_grid16_validation_20260718/regular_gate_validation_summary.md
docs/challenge_boundary_report_2026-07-18.md
results/gst_nvmm_decode_convert_latency_20260718/summary.md
results/vpi_warp_module_rerun_20260722/
results/power_probe_20260722_sudo/
results/regular05_submit_sync_probe_20260722/
```
