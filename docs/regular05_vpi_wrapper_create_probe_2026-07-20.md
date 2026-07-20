# Regular05 VPI Wrapper Create Probe - 2026-07-20

## Decision

VPI EGLImage wrapper creation is a major component of the accepted EGLImage
stage cost. Together with the transform-only and EGL map probes, this explains
most of the previously opaque 10.5 ms stage.

The result also explains why unsafe image-wrapper reuse looked attractive for
performance: it tried to remove a real cost. However, wrapper reuse caused block
tearing, so correctness still requires per-frame wrapper creation unless a safe
alternative is found.

## Probe

New patch script:

```text
scripts/patch_mmapi_transcode_vpi_wrapper_create_probe.py
```

Remote sample:

```text
/home/nvidia/orin-nx-project/_mmapi_work/jetson_multimedia_api/samples/99_transcode_vpi_wrapper_create_probe
```

The probe does:

```text
main DMABUF -> input scratch
NvBufSurfaceFromFd(input/output scratch)
map input/output EGLImage
vpiImageCreateWrapper(input/output)
vpiImageDestroy(input/output)
unmap input/output EGLImage
input scratch -> output scratch
output scratch -> main DMABUF
```

It does not submit VPI warp.

## Results

```text
rc: 0
black_border_p95: 0.000000000
black_border_max: 0.000008681
frames_gt_0p01: 0
```

Frame 100 timing:

| Component | Time |
|---|---:|
| input transform | 0.892873 ms |
| NvBufSurfaceFromFd pair | 0.001152 ms |
| EGL map pair | 0.073156 ms |
| VPI wrapper create pair | 3.406330 ms |
| VPI wrapper destroy pair | 0.285869 ms |
| EGL unmap pair | 0.038722 ms |
| scratch-copy transform | 0.929067 ms |
| output transform | 0.907466 ms |
| total | 6.534640 ms |

The first frame has a large wrapper initialization cost:

```text
frame 1 wrapper_create_ms: 265.077 ms
```

## Interpretation

Transform-only and EGL map probes showed:

```text
three transforms at frame 100: about 2.735 ms
EGL map/unmap pair at frame 100: about 0.136 ms
```

This wrapper-create probe shows:

```text
VPI wrapper create/destroy pair at frame 100: about 3.692 ms
```

Therefore the accepted stage cost is dominated by a combination of transforms
and VPI wrapper lifecycle cost. EGL map/unmap itself is not the main bottleneck.

## Claim Boundary

Allowed:

```text
VPI wrapper creation is a significant cost in the accepted per-frame wrapper
path.
The first frame has a large VPI wrapper initialization spike.
Per-frame wrapper creation is kept for correctness because wrapper reuse caused
tearing in this MMAPI/EGLImage path.
```

Forbidden:

```text
Wrapper reuse is safe.
Map/unmap is the main bottleneck.
Full real-time EIS.
Zero-copy full chain.
```

## Next Step

The next useful optimization path is not image-wrapper reuse. Better options:

```text
1. check whether wrapper creation can be moved to a format-stable path without
   vpiImageSetWrapper over changing EGLImages;
2. test format-matched NvBuffer input/output pairs;
3. measure whether VPI submit/sync adds more cost beyond wrapper creation;
4. keep the accepted per-frame wrapper path as the correctness baseline.
```
