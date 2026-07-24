# Device-Stage 50-Run Endurance Repeat - 2026-07-24

## Scope

This run extends prior 10-run lifecycle evidence into a longer bounded repeat.
It is not a 30-minute endurance claim. The measured wall duration was about
282 seconds.

Frozen scope:

```text
source: Regular05 same-source boundary
matrix: resid_r15_s07
matrix convention: source_to_dest
paths: accepted EGLImage, stream-only reuse, NvBuffer pair
runs: 50 per path, alternating order
```

## Result

All paths completed cleanly:

```text
accepted EGLImage: 50/50 rc=0, fallback=0
stream-only reuse: 50/50 rc=0, fallback=0
NvBuffer pair:     50/50 rc=0, fallback=0
```

| Path | Runs | Wall mean | Wall p50 | Wall p95 | Wall p99 | Stage avg mean | Stage avg p99 |
|---|---:|---:|---:|---:|---:|---:|---:|
| accepted EGLImage | 50 | 1.885004 s | 1.887649 s | 1.969715 s | 1.993936 s | n/a | n/a |
| stream-only reuse | 50 | 1.854220 s | 1.814211 s | 2.046889 s | 2.070096 s | 9.786855 ms | 10.928000 ms |
| NvBuffer pair | 50 | 1.896002 s | 1.893488 s | 1.974499 s | 1.994439 s | 10.050546 ms | 10.678700 ms |

Activity boundary from `tegrastats`:

| Metric | Value |
|---|---:|
| samples | 280 |
| GR3D avg | 28.621% |
| GR3D max | 72% |
| CPU temp max | 46.250 C |
| GPU temp max | 43.812 C |

## Interpretation

The useful result is stability and tail evidence, not a new acceleration claim.

```text
All three paths are robust in this 50-run repeat.
stream-only reuse has a small mean wall-time gain versus accepted EGLImage.
stream-only reuse does not improve tail latency in this repeat.
NvBuffer pair is stable but does not beat accepted EGLImage on mean or p99 wall
time in this repeat.
```

Mean wall-time comparison:

```text
stream-only reuse vs accepted EGLImage: about +1.63% mean improvement
NvBuffer pair vs accepted EGLImage: about -0.58% mean regression
```

Tail comparison:

```text
accepted EGLImage p99: 1.993936 s
stream-only reuse p99: 2.070096 s
NvBuffer pair p99:     1.994439 s
```

## Evidence

Local evidence:

```text
results/device_stage_endurance_20260724/regular05_50run/endurance_summary.csv
results/device_stage_endurance_20260724/regular05_50run/endurance_metrics.csv
results/device_stage_endurance_20260724/regular05_50run/tegrastats.log
```

Remote evidence:

```text
/home/nvidia/orin-nx-project/results/device_stage_endurance_20260724/regular05_50run/
```

## Claim Boundary

Allowed:

```text
Under frozen Regular05 semantics, accepted EGLImage, stream-only reuse, and
NvBuffer pair all completed 50 alternating Jetson runs with rc=0 and fallback=0.
```

Forbidden:

```text
Do not call this a 30-minute endurance run.
Do not claim stream-only reuse improves p99.
Do not claim NvBuffer pair is faster from this repeat.
Do not claim zero-copy, full real-time EIS, or full-pipeline acceleration.
```
