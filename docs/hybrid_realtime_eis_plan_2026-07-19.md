# Hybrid Real-Time EIS Plan - 2026-07-19

## Objective

Define the smallest next step from the accepted offline device-side stage demo
toward real-time EIS.

Accepted current stage:

```text
post_geometry_identity_first device-side warp/encode stage demo
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

Suggested contract id:

```text
hybrid_realtime_matrix_handoff_v1
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
source clip
output resolution
accepted device matrix convention: post_geometry_identity_first
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

1. Reuse `source_120f.h264`.
2. Feed the accepted `device_matrices_inverse_post_geometry_identity_first.csv`
   through the existing device path as the control run.
3. Build a mock online handoff that provides the same matrices with frame-index
   timestamps.
4. Verify output matches the CSV replay path within expected encoding variance.
5. Only then replace mock matrices with live CPU-estimated matrices.

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
