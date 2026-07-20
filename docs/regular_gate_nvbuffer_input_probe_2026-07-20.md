# Regular Gate NvBuffer Input Probe - 2026-07-20

## Decision

Directly wrapping the decoder/encoder DMABUF as `VPI_IMAGE_BUFFER_NVBUFFER` did
not work as a drop-in replacement for the input scratch transform.

This is useful negative evidence: the next performance work should not simply
remove the input `NvBufSurfTransform` and feed the main-chain DMABUF into VPI
while keeping a pitch-linear NV12_ER EGLImage output scratch.

## Test

New probe patch:

```text
scripts/patch_mmapi_vpi_transcode_nvbuffer_input_warp.py
```

Jetson sample:

```text
/home/nvidia/orin-nx-project/_mmapi_work/jetson_multimedia_api/samples/99_vpi_transcode_matrix_nvbuffer_input
```

Input:

```text
regular_gate05_regular_6 source.h264
regular_gate05_regular_6 inclusion_source_to_dest.csv
```

## Result

```text
rc: 139
VPI_MATRIX_LOADED ... count=180
MATRIX_HANDOFF frame=1 matrix_index=0 fallback=0
VPI NvBuffer input warp failed status=2 msg=Input and output images must have the same format
encoder output plane: Broken pipe
process ended with segmentation fault after the failed VPI call
```

Local evidence:

```text
results/regular_gate_nvbuffer_input_probe_20260720
```

## Interpretation

The VPI PerspectiveWarp input and output images must have the same format. The
main-chain DMABUF wrapped as NvBuffer is not compatible with the pitch-linear
NV12_ER output scratch used by the accepted EGLImage-wrapper path. Therefore the
simple "wrap input fd directly and keep output scratch" route is not viable.

The accepted EGLImage-wrapper path remains the frozen C++ path. Performance
optimization should continue from that stable baseline.

## Next Step

Better follow-up options:

```text
1. test a format-matched NvBuffer input and output pair before attempting to
   remove transforms from the accepted path;
2. isolate whether the 10.5 ms EGLImage stage cost comes mostly from repeated
   wrapper creation/synchronization or from the two NvBufSurfTransform calls;
3. reuse VPI wrappers across frames if the surface format and dimensions are
   stable;
4. keep the accepted EGLImage-wrapper path unchanged for quality evidence.
```
