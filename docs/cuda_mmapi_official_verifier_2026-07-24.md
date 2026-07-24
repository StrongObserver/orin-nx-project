# CUDA-MMAPI Official Verifier - 2026-07-24

## Scope

This verifier starts from NVIDIA Jetson Multimedia API `03_video_cuda_enc`,
which is the official CUDA-processing-then-encode sample shape:

```text
YUV420M input
-> NvVideoEncoder output-plane buffer
-> NvBufSurfaceFromFd
-> NvBufSurfaceSyncForDevice after CPU fill
-> NvBufSurfaceMapEglImage
-> cuGraphicsEGLRegisterImage / CUDA kernel
-> cuGraphicsUnregisterResource
-> NvBufSurfaceUnMapEglImage
-> qBuffer to NVENC
```

This is intentionally different from the rejected MMAPI transcode scratch route.
It verifies CUDA-to-encoder ownership in an official sample shape before any
larger integration claim.

## Build

Copied sample on Jetson:

```text
/home/nvidia/orin-nx-project/_mmapi_work/jetson_multimedia_api/samples/03_video_cuda_enc_verifier
/home/nvidia/orin-nx-project/_mmapi_work/jetson_multimedia_api/samples/03_video_cuda_enc_translate_verifier
```

Tracked patch helper:

```text
scripts/patch_video_cuda_enc_verifier.py
```

The custom verifier copy keeps local `NvAnalysis.cu` inside the copied sample so
the system `/usr/src/jetson_multimedia_api` sources are not modified.

## Input

Regular05 was converted to YUV420P/YUV420M raw input:

```text
/home/nvidia/orin-nx-project/results/cuda_mmapi_official_verifier_20260724/input/regular05_640x360_yuv420p.yuv
```

## Marker / Identity-Style Verifier

Official sample marker mode draws a small black box on the Y plane before NVENC.

| Metric | Result |
|---|---:|
| rc | 0 |
| frames | 180 |
| output readable | yes |
| black-border p95 | 0.000000000 |
| max black-border | 0.000008681 |

Evidence:

```text
results/cuda_mmapi_official_verifier_20260724/marker/
```

## Translate Verifier

The local verifier copy runs a Y-plane `dx=8` translate using a temporary CUDA
input buffer and writes back to the encoder buffer.

| Metric | Result |
|---|---:|
| rc | 0 |
| frames | 180 |
| output readable | yes |
| black-border p95 | 0.012500000 |
| max black-border | 0.012508681 |
| band shift spread p95 | 0.087772 px |
| expected shift error p95 | 0.084687 px |
| coherence status | pass |

The black border is expected for an 8-pixel right shift on a 640-pixel-wide
frame. The spatial-coherence gate is the correctness decision.

Evidence:

```text
results/cuda_mmapi_official_verifier_20260724/translate/
```

## Affine Verifier

The affine verifier uses the same local CUDA path with an affine matrix
equivalent to `dx=8`.

| Metric | Result |
|---|---:|
| rc | 0 |
| frames | 180 |
| output readable | yes |
| black-border p95 | 0.010937500 |
| max black-border | 0.010946181 |
| band shift spread p95 | 0.083640 px |
| expected shift error p95 | 0.082077 px |
| coherence status | pass |

Evidence:

```text
results/cuda_mmapi_official_verifier_20260724/affine/
```

## Decision

This verifier changes the CUDA-MMAPI boundary:

```text
The official CUDA-processing-then-encode sample shape can produce readable
marker, translate, and affine outputs without the tearing seen in the rejected
transcode scratch route.
```

What it proves:

```text
CUDA-to-NVENC ownership is viable in the official encode sample shape.
Y-plane translate/affine writeback can be spatially coherent.
```

What it does not prove:

```text
It does not prove the rejected transcode scratch route is fixed.
It does not prove full NV12 chroma-aware affine warp.
It does not prove full EIS pipeline acceleration.
It does not prove zero-copy.
It does not replace the accepted VPI-managed MMAPI/VPI/NVENC path yet.
```

## Next Boundary

A future implementation should only proceed if it keeps the official ownership
shape or can explain how to bridge that shape back into the current transcode
pipeline without reintroducing tearing.

Reasonable next verifier:

```text
full NV12/YUV420M luma+chroma affine verifier in the official encode sample,
then compare against the accepted VPI-managed path under same-input timing.
```
