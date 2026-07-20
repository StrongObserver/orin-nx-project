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

## Claim Boundary

Allowed:

```text
Accepted C++ EGLImage path consumes fixed, offline-LP, and delay90 Regular05
matrix CSVs.
The consumer path stays healthy: rc=0, fallback=0, mismatch=0.
Delay90 through accepted C++ path keeps black-border p95 below 1%.
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

Run the same accepted EGLImage consumer with a concurrent matrix FIFO/producer,
starting from fixed CSV streaming and then bounded-delay producer streaming.
