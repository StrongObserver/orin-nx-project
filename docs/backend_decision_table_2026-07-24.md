# Backend Decision Table - 2026-07-24

## Purpose

This table separates backend capability from project value. A route can be
technically runnable but still not be the right autumn-recruitment result if it
does not fit the Orin NX heterogeneous-video-compute story, changes quality
semantics, or lacks measured same-input evidence.

## Decision Matrix

| Route | Evidence | Current Value | Use Now? | Boundary |
|---|---|---|---|---|
| OpenCV CPU EIS | Regular quality-safe and performance baselines | Quality and comparison anchor | Yes, as baseline | Not hardware acceleration |
| OpenCV estimate downscale | Regular05 `8.568 ms -> 3.022 ms`, wall `8.473 s -> 7.565 s` | Real CPU pipeline cost reduction | Yes | Regular gate only |
| VPI CUDA PerspectiveWarp, Python full pipeline | Same-input Regular05 backend swap slower than OpenCV CPU | Negative placement evidence | No | Conversion/sync/readback dominate small 640x360 Python path |
| VPI CUDA PerspectiveWarp, high-res module | 4K `48.995 ms -> 20.514 ms`, FPS/W `1.682 -> 4.385` | Strong module acceleration | Yes, as module evidence | Not full EIS pipeline acceleration |
| VPI PyrLK | CPU/CUDA run, but OpenCV faster and keeps more valid points | Negative replacement evidence | No | No VPI optical-flow acceleration claim |
| VPI Dense Optical Flow | Current Python probe unavailable | Backend boundary | No | Not a result |
| VPI Python Remap | Native abort on this setup | Python binding negative evidence | No | Does not prove C++ Remap impossible |
| VPI C++ Remap | CPU/CUDA pass; CUDA `2.5x-3.4x` faster than OpenCV CPU on tested maps | Strong operator/module evidence | Yes, as operator evidence | Not EIS quality or full pipeline |
| Remap MMAPI padded diagnostic | 640x368 identity/wave `rc=0`, stage avg about `10.52-10.57 ms` | Device-stage operator insertion evidence | Yes, diagnostic | Not Regular EIS quality |
| Remap native-size pad/crop | 640x360 main, 640x368 scratch, identity/wave_safe `rc=0` | Size/layout boundary closed | Yes, diagnostic | Not mesh/local-warp success |
| Dynamic Remap payload | MMAPI dynamic Remap works, stage avg about `13.14-13.16 ms` | Future mesh cost boundary | Yes, as cost warning | Payload rebuild is expensive |
| CUDA standalone dynamic affine | RGBA `0.194 ms`, Y8 `0.138 ms` | Strong execution candidate | Yes, as standalone evidence | Not MMAPI integration |
| CUDA/MMAPI identity/marker interop | identity/marker/dynamic_marker `rc=0`, p95 black border `0` | Safety/dataflow evidence | Yes, diagnostic | Not warp correctness |
| CUDA affine over current EGL scratch | identity passes; translate/affine tears | Negative integration evidence | No | Current EGL-mapped scratch random sampling is rejected |
| CUDA double-surface debug | full-frame copy passes; integer translate tears | Narrows root cause | Yes, as negative evidence | Copy safety does not imply random sampling safety |
| VPI CUDA-owned bridge | identity passes; standalone RGBA VPI warp exact; bridge return to NV12/NVENC fails | Negative bridge evidence | No | Do not reuse as optimization path |
| Accepted C++ EGLImage path | Five Regular paths and Regular05 device stage evidence | Main device-stage correctness path | Yes | Not zero-copy, not full real-time |
| Stream-only reuse | 10-run mean gain: wall +5.303%, stage avg +6.346%; rc/fallback clean | Small accepted lifecycle optimization | Yes | Tail latency not proven better |
| NvBuffer pair | Preserves `resid_r15_s07`, small and variable stage gains | Quality-preserving dataflow alternative | Yes | Not zero-copy |
| Python GStreamer appsink/appsrc | appsink `7.93 ms/frame`; pass-through encode `15.81 ms/frame` | Negative path-selection evidence | No | Python-in-loop is not the next acceleration path |
| Queue depth / double buffering | Nsight does not show enough idle-gap trigger yet | Deferred | No | Needs new evidence before implementation |
| Static local Remap correction | Parallax10 metrics did not improve | Negative quality evidence | No | Future quality route needs dynamic mesh/depth/RS/gyro model |

## Route Classes

### Use As Main Results

```text
OpenCV CPU baseline and estimate-scale optimization
VPI CUDA high-resolution PerspectiveWarp module and FPS/W evidence
accepted C++ EGLImage MMAPI/VPI/NVENC device-stage path
stream-only reuse as small lifecycle optimization
NvBuffer pair as quality-preserving dataflow alternative
Nsight/NVTX wrapper/sync/transform/lifecycle attribution
```

### Use As Supporting Operator Evidence

```text
VPI C++ Remap
Remap native-size pad/crop
dynamic Remap payload cost boundary
standalone CUDA dynamic affine warp
CUDA/MMAPI identity and small-marker interop safety
```

### Keep As Negative Evidence

```text
VPI full-pipeline Python backend swap
VPI PyrLK replacement
Python Remap native abort
Python appsink/appsrc EIS integration
CUDA affine over current EGL-mapped NV12_ER scratch
CUDA double-surface integer translate
VPI CUDA-owned bridge non-identity return-to-NV12/NVENC path
static single-cell local Remap correction
```

## Interview-Safe Framing

Good:

```text
I separated capability from placement. VPI CUDA is useful for high-resolution
warp modules, but not as a naive small-frame Python backend swap. The accepted
device-stage route is MMAPI/VPI/NVENC with measured wrapper/sync/transform
costs, and the small follow-ups are stream-only reuse and NvBuffer pair. CUDA
standalone warp is promising, but current MMAPI return-to-NV12/NVENC routes have
negative evidence, so I did not package it as acceleration.
```

Bad:

```text
VPI accelerated the EIS pipeline.
CUDA solved the device-stage warp.
NvBuffer pair is zero-copy.
Remap solved local-warp stabilization.
Queue depth or double buffering is proven useful.
```

## Next Route Decision

The only CUDA route worth considering is not the failed bridge itself. It is a
new, identity-first route based on a better-documented CUDA/NvBufSurface/NVENC
ownership model, preferably guided by official samples or internal references.

If that route cannot be made concrete, CUDA remains a strong standalone operator
result plus negative MMAPI integration evidence, which is still valuable for the
project.
