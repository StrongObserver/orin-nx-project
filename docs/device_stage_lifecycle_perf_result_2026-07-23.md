# Device-Stage Lifecycle Perf Result - 2026-07-23

## Decision

The bounded lifecycle A/B found one small but real engineering result:

```text
stream-only reuse is safe for this same-source Regular05 repeat and improves the
accepted EGLImage path by about 5.3% wall mean and about 6.3% stage running avg.
```

This is a lifecycle/dataflow improvement, not a new EIS-quality result, not
zero-copy, and not evidence for a broad scheduler rewrite.

## Frozen Scope

```text
source:
  results/regular_gate_safe103_crop98_validation_20260720/regular_gate05_regular_6/source.h264

matrix:
  results/device_stage_lifecycle_probe_20260723/resid_r15_s07.csv

paths:
  accepted EGLImage timing sample
  EGLImage stream-only reuse sample

frame boundary:
  180 matrices loaded, same Regular05 source, source_to_dest convention
```

## Evidence

Local ignored evidence:

```text
results/device_stage_lifecycle_perf_20260723/repeat_stream_vs_egl_175139/
```

Small tracked summary files in that directory:

```text
repeat_stream_vs_egl_metrics.csv
repeat_stream_vs_egl_summary.csv
repeat_stream_vs_egl_benefit.csv
```

Only logs and summary CSV are needed for the conclusion. H264 outputs remain
ignored local artifacts.

## Repeat Result

Ten alternating runs were executed on Jetson. Each run returned `rc=0`, reported
successful app completion, and had zero fallback.

| Path | Runs | rc=0 | Success | Fallback | Wall Mean | Wall Median | Stage100 Mean | Stage Avg Mean | Wrapper Mean | Warp Avg Mean |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| accepted EGLImage | 10 | 10/10 | 10/10 | 0 | 1.946819 s | 1.956897 s | 7.842519 ms | 10.336381 ms | 5.877429 ms | 1.526472 ms |
| stream-only reuse | 10 | 10/10 | 10/10 | 0 | 1.843571 s | 1.789785 s | 7.295914 ms | 9.680414 ms | 5.365920 ms | 1.686040 ms |

Benefit against accepted EGLImage:

| Candidate | Wall Mean | Stage100 | Stage Avg | Wrapper | Warp Avg |
|---|---:|---:|---:|---:|---:|
| stream-only reuse | +5.303% | +6.970% | +6.346% | +8.703% | -10.453% |

Interpretation:

```text
The gain comes from lifecycle/wrapper-side cost, not warp-kernel speed. Warp
average becomes slower in this repeat, so the allowed claim is stream/lifecycle
overhead reduction around the accepted EGLImage path.
```

## What This Does Not Prove

```text
It does not prove full real-time EIS.
It does not prove zero-copy.
It does not prove queue-depth or double-buffering would help.
It does not reopen EGLImage image-wrapper reuse.
It does not change resid_r15_s07 quality semantics.
```

## Route Decision

This result is strong enough to promote stream-only reuse from diagnostic history
to a small accepted lifecycle optimization candidate inside the current
device-stage boundary.

It is not strong enough to trigger a broad scheduler rewrite:

```text
P6/P7 queue-depth / double-buffering remains closed.
Future work should stay around wrapper/register/free/sync lifecycle unless a new
timeline shows a clear removable idle gap.
```

## Tegrastats Activity Check

A single bounded activity run wrapped the accepted EGLImage and stream-only reuse
paths with `tegrastats --interval 100`.

Evidence:

```text
results/device_stage_lifecycle_perf_20260723/tegrastats_stream_vs_egl_175646/
```

Summary:

| Path | rc | Wall | Stage100 | Stage Avg | Wrapper | GR3D Avg | GR3D Max |
|---|---:|---:|---:|---:|---:|---:|---:|
| accepted EGLImage | 0 | 1.984509 s | 8.292940 ms | 10.675500 ms | 6.233940 ms | recorded | recorded |
| stream-only reuse | 0 | 1.799962 s | 6.892700 ms | 9.593930 ms | 5.012290 ms | recorded | recorded |

Benefit in this bounded activity run:

| Candidate | Wall | Stage100 | Stage Avg | Wrapper |
|---|---:|---:|---:|---:|
| stream-only reuse | +9.299% | +16.885% | +10.131% | +19.597% |

Boundary:

```text
This is activity evidence, not hard FPS/W. `tegrastats` was readable without
sudo, but board-input INA rail power was not collected in this loop. Therefore
the project should not claim a device-stage perf-per-watt number from this run.
```
