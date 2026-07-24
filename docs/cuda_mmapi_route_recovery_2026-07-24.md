# CUDA-MMAPI Route Recovery - 2026-07-24

## Blocker

The project has strong standalone CUDA operator evidence, but the current MMAPI
integration route is not accepted:

```text
identity and full-frame copy over current scratch paths can be clean;
non-identity random sampling over the current EGL-mapped pitch-linear NV12_ER
scratch path tears or fails when returning to NV12/NVENC.
```

The failed route must not be repackaged as acceleration.

## Local Evidence

Rejected or diagnostic-only local evidence:

| Route | Result | Decision |
|---|---|---|
| CUDA affine over current EGL scratch | identity passes; translate/affine tears | reject |
| CUDA double-surface debug | VIC round-trip and full-frame copy pass; integer translate tears | negative boundary |
| VPI CUDA-owned bridge | identity passes and standalone RGBA VPI warp is exact; final return to NV12/NVENC is visually wrong | reject |
| standalone CUDA dynamic warp | RGBA/Y8 affine kernel is fast and identity exact | keep as operator evidence only |

Accepted fallback paths:

```text
VPI-managed EGLImage path
stream-only reuse
format-matched NvBuffer pair
```

## Public Reference Recovery

The local knowledge routing points this blocker to:

```text
public:nvidia_vpi_samples
public:jetson_multimedia_api
public:jetson_accelerated_gstreamer
```

Relevant public directions from NVIDIA references:

| Reference | Useful signal | Project interpretation |
|---|---|---|
| Jetson Multimedia API `03_video_cuda_enc` | CUDA processing followed by encode is an official sample shape | Good reference for CUDA-to-NVENC ownership, but not proof that the current transcode scratch route is safe |
| Jetson Multimedia API `02_video_dec_cuda` | `NvBufSurfaceMapEglImage` / EGLImage path is used for CUDA processing on decoded buffers | Confirms EGLImage/CUDA interop is official, but only simple drawing/copy is not enough for random warp correctness |
| Jetson Multimedia API `12_v4l2_camera_cuda` | Buffers are shared with camera, CUDA, and EGL renderer | Useful ownership reference if a camera/input-side route is opened later |
| Jetson Accelerated GStreamer / `nvivafilter` | NVMM buffer CUDA processing exists as an official plugin-style path | Possible future route, but it would change the current MMAPI sample shape |
| NVIDIA forum discussions around EGL register/unregister cost | `cudaGraphicsEGLRegisterImage` and unregister may be per-frame and expensive | Matches this project's Nsight lifecycle attribution |

## Route Decision

Do not continue the failed VPI CUDA-owned bridge.

The only CUDA route worth opening later is a new official-sample-shaped verifier:

```text
1. Start from an official CUDA-processing-with-encode sample shape, preferably
   `03_video_cuda_enc` or a minimal equivalent on the installed JetPack.
2. Verify encoder-compatible CUDA writeback with identity or small marker first.
3. Verify a bounded integer translate only after identity/marker passes.
4. Only then test affine or source_to_dest matrix replay.
5. Stop immediately on tearing, green output, unreadable output, cache/sync
   ambiguity, or a need for broad MMAPI rewrite.
```

This is a different route from the rejected current scratch random-sampling
path. It tests the ownership model first, not the warp algorithm.

## Minimal Verifier Spec

Frozen variables:

```text
source: Regular05 or official sample input, clearly labeled
format: encoder-compatible NV12 path, no hidden RGB-only success
matrix: identity first, then integer translate, then affine/matrix only if safe
output: H264/H265 encoded output readable by the existing review tools
claim: verifier only, not EIS quality, not zero-copy, not full real-time EIS
```

Required observations:

```text
rc
frame count / output readability
black-border p95
source-vs-identity center diff
spatial shift coherence for translate
manual frame review for tearing, color, unrelated content, and band artifacts
stage timing only after correctness passes
```

Acceptance gate:

```text
identity/marker clean -> translate clean -> affine/matrix allowed
```

Stop gate:

```text
any visible tearing, green output, unrelated content, cache/sync ambiguity,
or return-to-NV12/NVENC color/content corruption
```

## ROI

Why it is worth one narrow verifier:

```text
CUDA standalone dynamic warp is much faster than VPI dynamic Remap payload
rebuild in the current diagnostic. If a correct CUDA-to-encoder ownership route
exists, it is high-value interview evidence even if the gain is small.
```

Why it is not worth a broad rewrite now:

```text
The current project already has accepted VPI-managed device-stage paths, Nsight
attribution, stream-only reuse, and NvBuffer pair. A broad CUDA/MMAPI rewrite
without ownership proof would risk spending time on the same failure mode again.
```

## Current Decision

P4 is not an implementation green light yet. It produces a concrete route:

```text
official-sample-shaped CUDA-to-encoder verifier, identity first
```

If the user wants this route implemented, the next step should start from a new
narrow contract, not from `vpi_cuda_owned_bridge_v1`.

Before implementation, ask the internal AI for company/industrial guidance on
the exact Jetson CUDA/NvBufSurface/NVENC ownership and sync sequence if local
official samples on the device do not settle the API order.
