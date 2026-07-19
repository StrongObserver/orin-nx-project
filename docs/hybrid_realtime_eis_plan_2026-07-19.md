# Hybrid Real-Time EIS Plan - 2026-07-19

## Objective

Define the smallest next step from the accepted offline device-side stage demo
toward real-time EIS.

Historical outdoor-car stage:

```text
post_geometry_identity_first device-side warp/encode stage demo
```

Current EIS-quality device replay stage:

```text
regular_gate05_regular_6 with source_to_dest device matrix convention
```

Target next stage:

```text
CPU online motion estimation
-> per-frame matrix handoff
-> MMAPI/VPI/NVENC device-side warp + encode
```

This is a hybrid design. It intentionally does not move optical flow or motion
estimation to VPI yet.

## Why This Route

This route stays closest to the original project design:

```text
controllable EIS pipeline
-> measured CPU baseline
-> measured device-side warp/encode path
-> one scoped step toward online operation
```

It avoids two bad moves:

```text
1. returning to Python appsink/appsrc, already measured as too expensive;
2. jumping to VPI optical flow, mesh warp, gyro, or full zero-copy before the
   warp/encode boundary is stable.
```

## Minimal Architecture

```text
Input H264 or camera stream
-> MMAPI decode
-> CPU-readable frame view or low-rate preview for motion estimation
-> CPU motion estimation and smoothing
-> per-frame 3x3 matrix
-> MMAPI/VPI scratch-buffer warp
-> NVENC output
```

The first implementation may keep a CPU-readable path for motion estimation.
That is acceptable if the claim is framed honestly as a hybrid prototype, not a
zero-copy production pipeline.

## Interface Options

### Option A - CSV Replay Baseline

Purpose:

```text
Keep the current offline matrix CSV path and measure device warp/encode behavior.
```

Use when:

```text
regression testing device warp/encode only
```

Do not use to claim:

```text
online EIS
```

### Option B - File/Queue Matrix Feed

Purpose:

```text
CPU process estimates matrices while MMAPI process consumes them with a bounded
frame delay.
```

Use when:

```text
testing online handoff without rewriting the MMAPI sample deeply
```

Risks:

```text
file I/O jitter
frame-index mismatch
unclear end-to-end latency
```

### Option C - In-Process CPU Estimator

Purpose:

```text
Add CPU motion estimation inside the C++ MMAPI process.
```

Use when:

```text
the handoff path is proven and the next bottleneck is process boundary overhead
```

Risks:

```text
larger C++ rewrite
more debugging surface
harder to preserve current Python EIS behavior exactly
```

Recommended first route:

```text
Option B, then Option C only if Option B proves the timing and quality shape.
```

## Done Contract Draft

Historical outdoor-car contract:

```text
hybrid_realtime_matrix_handoff_v1
```

Current Regular05 EIS-quality contract:

```text
regular05_hybrid_matrix_handoff_v1
```

Machine-readable drafts:

```text
configs/harness/contracts/hybrid_realtime_matrix_handoff_v1.json
configs/harness/contracts/regular05_hybrid_matrix_handoff_v1.json
```

Allowed claims:

```text
hybrid online matrix handoff prototype
MMAPI/VPI/NVENC device-side warp remains active
latency and frame-index alignment measured
```

Forbidden claims:

```text
zero-copy full chain
VPI optical-flow acceleration
product-grade real-time EIS
all-scene EIS quality
```

Frozen variables:

```text
source clip: regular_gate05_regular_6 for EIS-quality work
output resolution
accepted Regular05 device matrix convention: source_to_dest
VPI interpolation: linear
border mode: VPI_BORDER_ZERO
CPU baseline for quality comparison
```

External observations:

```text
frame-index alignment log
matrix handoff latency log
VPI warp timing log
end-to-end wall time
output video
side-by-side review video
direct video diff against accepted CPU baseline
```

Stop reasons:

```text
matrix/frame mismatch after one fix attempt
output is empty or unreadable
hybrid path is slower than offline path with no useful insight
visual review shows worse artifacts than accepted CPU baseline
implementation requires broad C++ rewrite before a small verifier exists
```

## First Implementation Slice

1. Reuse `regular_gate05_regular_6` as the EIS-quality source.
2. Feed the fixed source_to_dest Regular05 device matrix through the existing
   device path as the control run.
3. Build a handoff provider that preserves the same source_to_dest convention.
4. Verify output matches the fixed Regular05 replay path within expected
   encoding variance.
5. Only then replace replay matrices with live CPU-estimated source_to_dest
   matrices.

Success criteria for slice 1:

```text
120 frames processed
no matrix fallback
output non-empty and readable
frame-index alignment log has no gaps
VPI warp avg remains near the current 1.44 ms/frame order
```

## Why Not VPI Optical Flow Yet

VPI optical flow may become valuable later, but it is not the next best step.
The current missing link is not optical-flow speed; it is the online integration
boundary between motion estimation, per-frame matrices, VPI warp, and NVENC.

Revisit VPI optical flow only after:

```text
hybrid matrix handoff works
end-to-end latency is measured
quality no-regression is defined
the motion-estimation stage is confirmed as the limiting cost
```
