# Producer First-Row Latency Audit - 2026-07-24

## Scope

This audit explains the apparent startup latency in the Regular05 stride5
producer/FIFO/consumer path. It uses existing evidence only.

## Evidence

```text
results/regular05_producer_scheduling_optimization_20260720/live_stride5_timing.csv
results/regular05_producer_scheduling_optimization_20260720/live_stride5_wall_time.csv
results/regular05_producer_scheduling_optimization_20260720/handoff_live_stride5_fifo/
results/regular05_producer_scheduling_optimization_20260720/jetson_delay90_stride5_timing.csv
```

## Key Numbers

Producer-only stride5 timing:

| Component | Time |
|---|---:|
| LP solve total | 12756.410 ms |
| mask safety total | 2308.349 ms |
| estimate total | 467.268 ms |
| decode total | 109.374 ms |
| output matrix total | 15080.511 ms |
| total elapsed | 15687.400 ms |

Concurrent live stride5:

| Metric | Value |
|---|---:|
| wall time for 180 frames | 17533 ms |
| fallback | 0 |
| frame-index mismatch | 0 |
| handoff avg excluding startup behavior | 28.504 us |
| handoff p95 | 39.025 us |
| handoff max | 42.241 us |

## Decision

The bottleneck is not FIFO read cost or C++ consumer handoff. The sampled
handoff reads are tens of microseconds. The large wall time comes from the
producer-side matrix generation, especially repeated LP prefix solving and mask
safety work, before the consumer has useful rows to consume in the current
script structure.

## ROI

A useful future follow-up would not be a broad producer rewrite. It would target
one narrow question:

```text
Can the producer emit early rows incrementally while preserving the accepted
bounded-delay quality semantics?
```

Current default decision:

```text
Do not open that implementation before the current device-stage/endurance and
CUDA-MMAPI evidence is sealed. The existing producer evidence is already useful
as a latency-quality and scheduling trade-off story.
```

## Claim Boundary

Allowed:

```text
stride5 reduced producer-only time from about 68.5s to about 15.7s for 180
frames, and the live FIFO/consumer path has microsecond-scale sampled handoff
once rows are available.
```

Forbidden:

```text
full real-time EIS
zero-latency producer
FIFO handoff is the bottleneck
consumer rewrite is required by current evidence
```
