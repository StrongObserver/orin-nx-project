# Producer Boundary And Next Route - 2026-07-24

## Scope

This note summarizes the matrix producer / FIFO / MMAPI consumer boundary for
the Orin NX EIS workload. It separates three questions:

```text
1. Can the C++ MMAPI/VPI/NVENC consumer receive per-frame matrices correctly?
2. Can a producer generate matrices close to the accepted offline quality?
3. Can the combined path be called full real-time EIS?
```

The answer is:

```text
1. Yes, the handoff and consumer shape are healthy.
2. Partially, bounded-delay and stride scheduling improved the producer route.
3. No, full real-time EIS is still not claimed.
```

## Handoff And Consumer Health

The matrix handoff shape has been validated:

```text
Python matrix producer -> FIFO -> MMAPI/VPI/NVENC consumer
```

Evidence:

```text
docs/hybrid_realtime_matrix_handoff_2026-07-19.md
configs/harness/contracts/regular05_live_producer_alignment_v1.json
results/regular05_hybrid_matrix_handoff_20260720/
```

Key conclusions:

| Item | Result | Meaning |
|---|---|---|
| Fixed FIFO control | fixed replay vs fixed FIFO diff = 0 | FIFO/consumer is not the quality blocker |
| FIFO handoff | fallback = 0, frame-index mismatch = 0 | Matrix delivery is reliable |
| Handoff cost | sampled reads are tens of microseconds after startup | Handoff overhead is not dominant |
| Accepted consumer | VPI warp / encode path remains readable | Device consumer is healthy |

## Producer Quality Boundary

The first live CPU producers could feed matrices with correct frame index and no
fallback, but quality was weak:

| Candidate | Fallback | Frame-index mismatch | Producer estimate avg | Decision |
|---|---:|---:|---:|---|
| live cumulative raw | 0 | 0 | about 18.37 ms | live path works, quality weak |
| live window correction | 0 | 0 | about 18.09 ms | no quality improvement |

The live producer gap was not a transport problem. It was a matrix quality /
causal smoothing problem.

The offline LP-rigid upper bound proved what a good matrix sequence can look
like, but it is not zero-latency realtime:

| Comparison | Translation mean | Translation p95 | Decision |
|---|---:|---:|---|
| fixed vs original live producer | 35.890 px | 62.762 px | too weak |
| fixed vs offline LP-rigid upper bound | 0.502 px | 1.341 px | good upper bound, not realtime |

## Bounded-Delay Trade-Off

Bounded-delay producer evidence:

| Candidate | Delay | Translation mean | Translation p95 | Black p95 | Decision |
|---|---:|---:|---:|---:|---|
| delay45 | 45 frames | 7.308 px | 33.184 px | 0.000143447 | intermediate |
| delay90 | 90 frames | 1.099 px | 3.400 px | 0.000670356 | best bounded-delay matrix quality, pending review history |

Interpretation:

```text
More delay improves matrix quality because it gives the producer a wider
trajectory window. This is valuable engineering evidence, but it is a latency /
quality trade-off, not zero-latency realtime EIS.
```

Viewport/FOV follow-ups then tested ways to reduce black edge and zooming:

```text
fade15
safe103
crop98 / reflect8_crop98
safe103_crop98
resid_r15_s07 later superseded these as the accepted stabilization-strength
anchor for Regular quality comparisons.
```

## Producer Scheduling Optimization

The largest producer compute cost was repeated LP prefix solving in
`bounded_delay_lp_rigid`. The stride-5 scheduling probe changed only the solve
cadence:

| Candidate | LP stride | LP calls | LP solve ms | Mask safety ms | Producer total |
|---|---:|---:|---:|---:|---:|
| delay90 baseline | 1 | 89 | 57068.382 | 10729.033 | 68507.848 ms |
| delay90 stride5 | 5 | 19 | 12756.410 | 2308.349 | 15687.400 ms |

Regular05 device verification for stride5:

| Metric | Result |
|---|---:|
| consumer rc | 0 |
| fallback | 0 |
| frame-index mismatch | 0 |
| black-border p95 | 0.000784288 |
| frames_gt_0p01 | 0 |

Concurrent live stride5:

| Metric | Result |
|---|---:|
| producer rc | 0 |
| consumer rc | 0 |
| wall time for 180 frames | 17.533 s |
| diff vs precomputed stride5 | 0 |

Interpretation:

```text
Stride5 reduced producer-only time from about 68.5 s to about 15.7 s and
concurrent live wall time from about 68.7 s to about 17.5 s for 180 frames.
This is a real scheduling improvement, but still not full real-time or
zero-latency EIS.
```

## Current Decision

Producer work is valuable as a boundary story:

```text
handoff/consumer is solved;
offline quality upper bound is known;
bounded delay exposes latency-quality trade-off;
stride scheduling cuts repeated LP solve cost;
remaining gap is first-row/startup latency plus full realtime producer quality.
```

Do not claim:

```text
full real-time EIS
zero-latency producer
offline LP-rigid is realtime
VPI optical-flow acceleration
zero-copy full chain
all-scene quality
```

## Next Route

For autumn recruitment, the current producer evidence is already useful. A new
producer implementation should only open if it targets one narrow question:

```text
Can first-row latency be reduced without changing the accepted matrix quality
semantics or making the device output visually worse?
```

Recommended default:

```text
Do not open a broad producer rewrite before finishing presentation/evidence
sync. Keep producer as a latency-quality and scheduling trade-off story unless
the user explicitly wants another implementation loop.
```
