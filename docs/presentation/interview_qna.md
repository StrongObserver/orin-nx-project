# Interview Q&A

## Q: What is the project?

A Jetson Orin NX EIS project. I built a controllable CPU video stabilization
pipeline, added quality gates and review assets, measured Jetson runtime, then
tested where performance optimization and hardware acceleration actually help.

## Q: What is your current best result?

For Regular clips, the current performance baseline is:

```text
lp_rigid_strength080_dynzoom106
estimate_scale=0.5
feature_grid_size=16
```

It passes objective gates on all five Regular clips and was accepted by human
review.

## Q: What improved after optimization?

On `regular_gate05_regular_6`:

```text
estimate stage: 8.568 ms -> 3.022 ms
total wall time: 8.473 s -> 7.565 s
```

The speedup came from lower-resolution motion estimation plus a denser feature
grid to recover stability.

## Q: Why keep two baselines?

Because they serve different claims:

```text
quality-safe baseline:
  estimate_scale=1.0, grid12

Regular performance baseline:
  estimate_scale=0.5, grid16
```

The quality-safe baseline is conservative. The performance baseline is accepted
for Regular-gate performance.

## Q: Did VPI accelerate the EIS pipeline?

Not the current full pipeline. A simple VPI backend swap was slower at 640x360.

But VPI CUDA did accelerate high-resolution warp-heavy modules:

```text
720p: 1.35x
1080p: 1.83x
1440p: 2.15x
4K: 2.33x
```

So the lesson is placement and dataflow matter.

## Q: What are the remaining limitations?

- Global warp cannot solve all local/parallax/rolling-shutter-like artifacts.
- Running and other challenge sets are not claimed as solved.
- GStreamer/NVMM dataflow is only probed, not integrated into the EIS pipeline.
- VPI module speedup is not the same as full-pipeline speedup.

## Q: What would you do next?

I would measure the GStreamer/NVMM dataflow boundary:

```text
decode -> NVMM convert -> CPU boundary or encode
```

Only after that would I decide whether it is worth integrating into the EIS
pipeline.

## Evidence To Mention

```text
docs/stage_result_regular_performance_baseline_2026-07-18.md
docs/vpi_warp_module_report_2026-07-18.md
docs/gstreamer_nvmm_latency_plan_2026-07-18.md
results/regular_gate_est0p5_grid16_validation_20260718/regular_gate_validation_summary.md
```
