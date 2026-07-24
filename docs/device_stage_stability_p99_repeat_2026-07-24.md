# Device-Stage Stability And P99 Repeat - 2026-07-24

## Scope

This note turns existing Jetson repeat evidence into a stability/P99 summary for
the accepted C++ device-stage boundary.

It does not claim a 30-minute endurance run. The current evidence is a bounded
repeat set:

```text
accepted EGLImage vs stream-only reuse: 10 alternating runs
accepted EGLImage vs stream-only reuse vs NvBuffer pair: 5 alternating runs
tegrastats activity check: one bounded activity run
```

## Frozen Semantics

```text
source: Regular05 same-source boundary
matrix: resid_r15_s07
matrix convention: source_to_dest
consumer: accepted C++ MMAPI/VPI/NVENC path variants
quality: no EIS tuning, crop, postprocess, or matrix-strength change
```

## Ten-Run Stream-Only Repeat

Evidence:

```text
results/device_stage_lifecycle_perf_20260723/repeat_stream_vs_egl_175139/repeat_stream_vs_egl_metrics.csv
results/device_stage_lifecycle_perf_20260723/repeat_stream_vs_egl_175139/repeat_stream_vs_egl_summary.csv
results/device_stage_lifecycle_perf_20260723/repeat_stream_vs_egl_175139/repeat_stream_vs_egl_benefit.csv
```

All runs returned `rc=0`, `output_success=True`, and `fallback_count=0`.

| Path | Runs | Wall p50 | Wall p95 | Wall p99 | Stage avg p50 | Stage avg p95 | Stage avg p99 |
|---|---:|---:|---:|---:|---:|---:|---:|
| accepted EGLImage | 10 | 1.956897 s | 1.981455 s | 1.981455 s | 10.365000 ms | 10.599900 ms | 10.599900 ms |
| stream-only reuse | 10 | 1.789785 s | 2.040837 s | 2.040837 s | 9.378920 ms | 10.638100 ms | 10.638100 ms |

Mean benefit:

| Candidate | Wall mean | Stage100 | Stage avg | Wrapper | Warp avg |
|---|---:|---:|---:|---:|---:|
| stream-only reuse | +5.303% | +6.970% | +6.346% | +8.703% | -10.453% |

Interpretation:

```text
stream-only reuse improves mean wall/stage cost, but its p95/p99 tail is not
strictly better in this small 10-run repeat. The honest claim is a small mean
lifecycle gain with clean rc/fallback behavior, not a proven tail-latency win.
```

## Five-Run Three-Path Repeat

Evidence:

```text
results/device_stage_lifecycle_probe_20260723/repeat/lifecycle_repeat_metrics.csv
results/device_stage_lifecycle_probe_20260723/repeat/lifecycle_repeat_summary.csv
results/device_stage_lifecycle_probe_20260723/repeat/lifecycle_repeat_benefit_vs_egl.csv
```

All runs returned `rc=0`, `output_success=1`, and `fallback_count=0`.

| Path | Runs | Wall p50 | Wall p95 | Wall p99 | Stage avg p50 | Stage avg p95 | Stage avg p99 |
|---|---:|---:|---:|---:|---:|---:|---:|
| accepted EGLImage | 5 | 1.940980 s | 1.981326 s | 1.981326 s | 10.320400 ms | 10.393600 ms | 10.393600 ms |
| stream-only reuse | 5 | 1.811826 s | 2.035205 s | 2.035205 s | 9.731050 ms | 10.770600 ms | 10.770600 ms |
| NvBuffer pair | 5 | 1.911762 s | 1.998689 s | 1.998689 s | 10.183900 ms | 10.551800 ms | 10.551800 ms |

Mean benefit against accepted EGLImage:

| Candidate | Wall mean | Stage100 | Stage avg | Wrapper | Warp avg |
|---|---:|---:|---:|---:|---:|
| stream-only reuse | +2.368% | +4.301% | +1.280% | +6.146% | -14.914% |
| NvBuffer pair | +1.140% | -0.980% | +0.908% | -3.322% | +0.839% |

Interpretation:

```text
NvBuffer pair remains quality-preserving and viable, but timing benefit is
small and variable. Stream-only reuse is the better promoted lifecycle result,
while neither candidate justifies queue-depth or double-buffering work from the
current tail-latency evidence.
```

## Activity Boundary

Evidence:

```text
results/device_stage_lifecycle_perf_20260723/tegrastats_stream_vs_egl_175646/tegrastats_activity_summary.csv
```

| Path | rc | Wall | Stage avg | Wrapper | GR3D avg | GR3D max | CPU temp max | GPU temp max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| accepted EGLImage | 0 | 1.984509 s | 10.675500 ms | 6.233940 ms | 25.000% | 39% | 41.906 C | 39.687 C |
| stream-only reuse | 0 | 1.799962 s | 9.593930 ms | 5.012290 ms | 27.368% | 42% | 41.968 C | 39.718 C |

This is activity evidence only. It is not board-input power, not FPS/W, and not
a thermal endurance run.

## Decision

Current accepted statement:

```text
Under frozen Regular05 semantics, repeated Jetson device-stage runs show
stream-only reuse has a small mean lifecycle gain and clean rc/fallback behavior.
Tail latency is not yet conclusively improved, and no 30-minute endurance claim
has been collected.
```

Useful interview value:

```text
This evidence shows the optimization process: profile first, change one
lifecycle variable, run alternating repeats, preserve fallback/readability
checks, and avoid promoting a broad scheduler rewrite when the tail evidence is
not strong enough.
```

Next optional hardware step:

```text
Run a true 20-30 minute endurance loop only if the project needs an endurance
claim. Required fields: rc/fallback/frame mismatch, output readability,
wall/stage p50/p95/p99, tegrastats temperature/activity, and a clear note that
power is unavailable unless a real rail source is sampled.
```
