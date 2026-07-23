# RK3588 NPU Idea Mapping - 2026-07-23

## Decision

The RK3588 blogger's idea is useful for this project, but not as a direct API or
architecture transplant.

Useful:

```text
hardware time vs wall-clock time separation
Python scheduling and lock-contention diagnosis
multi-in-flight work to keep hardware busy
C++ and shared-buffer dataflow when Python becomes the bottleneck
fixed performance mode before benchmark
```

Not directly transferable:

```text
RKNN core masks
RKNN Lite multi-process runtime layout
rknn_create_mem / pass-through API
RK3588 NPU utilization numbers
```

For Orin NX, the corresponding route is not RKNN-style NPU multi-core
scheduling. It is C++ MMAPI/VPI/NVENC device-stage profiling with frozen EIS
workload semantics, then only opening a dataflow A/B if the timeline shows a
real idle bubble or host-side scheduling bottleneck.

## Mapping

| RK3588 idea | Orin NX equivalent | Usefulness | Verifier |
|---|---|---|---|
| NPU hardware timer is faster than board wall-clock FPS | Separate VPI submit/sync, wrapper lifecycle, transforms, encode, and wall time | High | NVTX/Nsight timeline plus existing timing CSV |
| Python 16 threads lose performance through GIL and RKNN object lock | Python appsink/appsrc and live producer are not the right final dataflow path | High | Existing appsink/appsrc timing and producer scheduling evidence |
| Multi-process creates independent RKNN instances and reduces lock contention | Do not use Python multi-process for current Orin path; use C++ stage and queue/in-flight analysis if needed | Medium | Nsight shows whether CUDA/VPI/NVENC is starved |
| 2:1 workers per NPU core hide command dispatch gaps | Potential Orin analogy is queue depth / double buffering / async submit, not NPU core masks | Conditional | Timeline shows hardware idle gaps between stages |
| rknn_create_mem zero-copy shared memory | NvBufSurface/NvBuffer/DMABUF/EGLImage/VPI wrappers | High conceptually, but current path is not zero-copy | Same-source output sanity plus stage timing |
| pass-through means input already matches model format | Orin equivalent is format-stable NV12_ER scratch, explicit BGR8/NV12 handling, and avoiding hidden conversions | High | Format probe, color correctness, no green/tearing output |
| Fixed CPU/DDR/NPU/GPU frequency before benchmarking | Fixed Jetson power/perf mode and recorded profiling environment | High | nvpmodel/tegrastats/INA evidence where available |

## Why Not Direct Implementation

The RK3588 video solves a YOLO inference-serving problem on an RKNN NPU runtime.
Our current Orin NX path is a video dataflow and VPI warp path:

```text
MMAPI/NVDEC block-linear NV12 main chain
-> NvBufSurfTransform to pitch-linear NV12_ER scratch
-> VPI CUDA PerspectiveWarp
-> NvBufSurfTransform back to block-linear NV12
-> NVENC
```

The already-measured Orin bottleneck is not a missing NPU core mask. Existing
evidence points to:

```text
wrapper lifecycle
VPI sync
NvBufSurfTransform sandwich
producer scheduling in earlier live runs
format/layout mismatch between main chain and VPI scratch
```

Therefore, the first Orin task should be profiling and attribution, not a new
multi-threaded scheduler.

## Expected Benefit If The Idea Transfers

The transferable hypothesis is:

```text
If the Orin device-stage timeline shows VPI/CUDA/NVENC idle gaps caused by
host-side wrapper/sync/transform scheduling, then a future same-source A/B can
test queue depth, double buffering, or format-matched buffer lifecycle changes.
```

This must be compared against existing results:

| Existing result | Meaning |
|---|---|
| VPI submit itself around 0.019 ms | The submit API call is not the bottleneck by itself |
| frame100 EGLImage stage around 7.535 ms under resid timing | Stage cost is around dataflow and sync |
| NvBuffer pair frame100 stage around 7.230 ms | Format-matched NvBuffer pair gives a small gain |
| running avg 9.589 ms -> 9.401 ms | Current measured gain is small but real |

The blogger-inspired route is worth trying only if it can improve this stage
without changing output semantics. It must not reduce quality, change matrix
semantics, or revive rejected routes.

## Minimum Next Experiment

Do not implement a scheduler first. The minimum experiment is:

```text
1. Add or identify stage markers for decode, input transform, wrapper/NvBuffer
   wrap, VPI submit, VPI sync, output transform, encode, and wall time.
2. Capture an Nsight Systems report or equivalent exported timing summary.
3. Look for hardware idle gaps and host-side wait gaps.
4. Only if gaps exist, open a new dataflow A/B contract for queue depth,
   double buffering, or buffer lifecycle changes.
```

Frozen boundaries:

```text
same source
same matrix, preferably resid_r15_s07 for quality-preserving comparison
same crop/postprocess boundary
same frame-count/FPS boundary
no EGLImage image-wrapper reuse revival
no pitch-linear main encoder chain
no block-linear VPI scratch pair
no zero-copy claim unless measured
```

## Interview Use

Good wording:

```text
I used the RK3588 NPU case as a methodology reference: distinguish hardware
time from wall-clock time, identify whether Python or host scheduling starves
the accelerator, and only then move down to C++ shared-buffer dataflow. On
Jetson, the analogous problem is not RKNN core masking; it is MMAPI/VPI/NVENC
stage profiling around NvBufSurface, NvBuffer, wrapper lifecycle, sync, and
transform cost.
```

Bad wording:

```text
I copied the RK3588 NPU zero-copy optimization to Jetson.
I implemented zero-copy on Orin.
I can use multi-core NPU scheduling on VPI the same way RKNN does.
```
