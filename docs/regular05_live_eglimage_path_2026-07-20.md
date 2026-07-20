# Regular05 Live EGLImage Path - 2026-07-20

## Decision

Fixed and producer-generated Regular05 matrices can run through the accepted C++
MMAPI/VPI/NVENC EGLImage path. This confirms that the accepted device path is
usable beyond static review assets and can consume existing producer matrix CSVs.

This is not full real-time EIS yet. The runs use precomputed CSV files, not a
concurrent live FIFO producer.

## Inputs

```text
clip: regular_gate05_regular_6 source.h264
consumer: accepted C++ EGLImage-wrapper sample
matrix convention: source_to_dest
```

Tested matrices:

```text
fixed_replay_source_to_dest.csv
offline_lp_rigid_source_to_dest.csv
delay90_source_to_dest.csv
```

## Summary

| Candidate | rc | wall ms | fallback | mismatch | handoff avg us | VPI avg ms | black p95 | black max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| fixed_replay | 0 | 1855 | 0 | 0 | 0.989091 | 1.499790 | 0.000951823 | 0.006184896 |
| offline_lp | 0 | 1847 | 0 | 0 | 0.864000 | 1.544480 | 0.001459201 | 0.005894097 |
| delay90 | 0 | 1975 | 0 | 0 | 0.986182 | 1.549070 | 0.000639106 | 0.003632813 |

All three outputs are readable and stay below the 1% black-border p95 hard
gate. No fallback or frame-index mismatch was observed in sampled handoff logs.

## FIFO / Live Streaming

The accepted EGLImage sample was patched to read matrices from `VPI_MATRIX_FIFO`
and tested with both precomputed CSV streaming and a concurrent live producer.

| Candidate | rc | wall ms | fallback | mismatch | handoff avg us | handoff p95 us | VPI avg ms | black p95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| fixed_fifo | 0 | 1916 | 0 | 0 | 69.360818 | 256.488000 | 1.515650 | 0.000951823 |
| delay90_fifo | 0 | 1994 | 0 | 0 | 59.839000 | 175.861500 | 1.577790 | 0.000639106 |
| live_delay90 | 0 | 68696 | 0 | 0 | 31.440898 | 53.506000 | 1.554950 | 0.000583333 |

Interpretation:

```text
The accepted EGLImage consumer works with FIFO streaming.
The concurrent live_delay90 producer also works with fallback=0 and mismatch=0.
The live run wall time is dominated by producer computation, not by FIFO handoff
or VPI warp.
```

## Evidence

Remote evidence:

```text
/home/nvidia/orin-nx-project/results/regular05_live_eglimage_path_20260720
```

Local evidence:

```text
results/regular05_live_eglimage_path_20260720
```

Review copy:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular05_live_eglimage_path\20260720_regular05_live_eglimage_path_regular_gate05_source_fixed_offlinelp_delay90_grid.mp4
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular05_live_eglimage_path\20260720_regular05_live_eglimage_path_regular_gate05_source_fixedfifo_delay90fifo_livedelay90_grid.mp4
```

The review grid shows:

```text
source / fixed / offline_lp / delay90
```

## Interpretation

This closes the immediate integration gap between the producer-matrix side and
the accepted C++ EGLImage consumer. The remaining live-EIS question is no longer
"can the accepted C++ path consume producer matrices?" It can.

The next question is whether a concurrent producer/FIFO version can preserve the
same quality and timing while matrices are generated online.

The concurrent producer version preserves the consumer correctness gates, but it
is much slower than precomputed CSV replay. The next bottleneck is producer
compute and scheduling, not the accepted C++ EGLImage consumer.

## Claim Boundary

Allowed:

```text
Accepted C++ EGLImage path consumes fixed, offline-LP, and delay90 Regular05
matrix CSVs.
The consumer path stays healthy: rc=0, fallback=0, mismatch=0.
Delay90 through accepted C++ path keeps black-border p95 below 1%.
Concurrent live_delay90 FIFO also keeps rc=0, fallback=0, mismatch=0, and
black-border p95 below 1%.
```

Forbidden:

```text
Full real-time EIS.
Zero-latency producer.
Zero-copy full chain.
VPI optical-flow acceleration.
All-scene EIS quality.
```

## Next Step

Optimize or restructure producer computation before making stronger live EIS
claims. The accepted C++ consumer is healthy; the current live bottleneck is the
producer.
