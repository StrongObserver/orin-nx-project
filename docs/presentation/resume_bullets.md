# Resume Bullets

Use these as source wording for a resume or interview profile. Adjust length to
the target format, but keep the claim boundaries.

## Short Version

```text
Built a Jetson Orin NX heterogeneous video-compute pipeline using EIS as a
real-time workload; established Regular/Challenge quality gates, measured VPI
CUDA 4K PerspectiveWarp speed/FPS-W gains, and profiled MMAPI/VPI/NVENC
device-stage bottlenecks with Nsight/NVTX.
```

## Medium Version

```text
Built a Jetson Orin NX heterogeneous video-compute project with EIS as the
representative workload: created Regular/Challenge quality gates, optimized CPU
motion-estimation cost on Regular05 from 8.568 ms to 3.022 ms, and kept the
accepted quality anchor around resid_r15_s07.
```

```text
Measured hardware acceleration boundaries on Jetson Orin NX: showed simple VPI
backend replacement is slower in the 640x360 Python pipeline, while VPI CUDA
accelerates 4K PerspectiveWarp from 48.995 ms to 20.514 ms and improves module
FPS/W from 1.682 to 4.385.
```

```text
Validated and profiled a C++ MMAPI/VPI/NVENC device-stage path; Nsight/NVTX
localized remaining cost to wrapper/sync/transform/lifecycle rather than
vpiSubmitPerspectiveWarp, and stream-only reuse reduced same-source Regular05
stage average from 10.336 ms to 9.680 ms without changing output semantics.
```

```text
Closed a VPI Remap/MMAPI size-layout boundary on Jetson Orin NX: kept the
encoder-facing video chain at native 640x360 while padding only the VPI scratch
stage to 640x368 for Remap, then cropping back before NVENC with rc=0 and no
black-border regression in diagnostic checks.
```

```text
Verified a CUDA/MMAPI scratch-interoperability boundary before making any CUDA
acceleration claim: identity, fixed-shift, and dynamic-shift diagnostics all
returned rc=0 with readable 640x360 output, while identity preserved a
black-border p95 of 0.
```

## Long Version

```text
Jetson Orin NX heterogeneous video compute and device-side dataflow optimization:
used EIS as a real-time workload, built Regular/Challenge quality gates, and
kept quality, performance, and model-boundary claims separate. The accepted
Regular performance baseline passes 5/5 NUS Regular clips, while challenge sets
document global-warp limits such as high-frequency motion, fast rotation,
parallax, and foreground contamination.
```

```text
Profiled CPU and VPI acceleration paths under frozen input semantics. CPU
motion-estimation downscaling plus denser features reduced Regular05 estimate
time from 8.568 ms to 3.022 ms and wall time from 8.473 s to 7.565 s. A direct
VPI backend swap was slower in the small Python pipeline, but VPI CUDA improved
4K PerspectiveWarp from 48.995 ms to 20.514 ms and module FPS/W from 1.682 to
4.385.
```

```text
Advanced the device-side path beyond Python appsink/appsrc into C++
MMAPI/VPI/NVENC: H264 decode, block-linear NV12 main surfaces, pitch-linear
NV12_ER VPI scratch, CUDA PerspectiveWarp, and NVENC output. Nsight/NVTX showed
that the dominant cost is wrapper/sync/transform/lifecycle rather than the VPI
submit call alone. A stream-only reuse follow-up improved same-source Regular05
wall mean by 5.303% while preserving rc=0 and fallback=0 across 10 runs.
```

```text
Extended the VPI operator boundary beyond PerspectiveWarp by validating C++
Remap and closing a native-size MMAPI integration issue: VPI WarpGrid required a
640x368 Remap payload for a 640x360 source, so the device path pads only the VPI
scratch stage and returns to the native 640x360 main chain before encode. This
is a dataflow/operator integration result, not an EIS quality or zero-copy claim.
```

```text
De-risked the next CUDA device-stage route with an identity-first
NvBufSurface/EGLImage/CUDA interop verifier. The verifier proves diagnostic
scratch read/write safety on Jetson Orin NX, but deliberately keeps custom CUDA
warp acceleration, zero-copy, and full real-time EIS claims out of scope until a
separate same-input contract measures them.
```

## Interview One-Liner

```text
This is not just a stabilizer demo. I used EIS to create a measurable video
workload, then traced where CPU, VPI/CUDA, MMAPI/NVENC, memory format, wrapper
lifecycle, and sync costs actually matter on Jetson Orin NX.
```

## Boundary-Safe Phrases

Use:

```text
representative real-time workload
Regular-gate quality
module-level VPI acceleration
device-stage dataflow
native-size VPI Remap scratch-stage pad/crop
CUDA/MMAPI scratch interop safety verifier
quality-preserving NvBuffer pair follow-up
stream-only lifecycle optimization
Nsight-backed bottleneck attribution
```

Avoid:

```text
full real-time EIS
zero-copy full chain
all-scene stabilization
product-grade EIS
VPI optical-flow acceleration
queue-depth/double-buffering speedup
```
