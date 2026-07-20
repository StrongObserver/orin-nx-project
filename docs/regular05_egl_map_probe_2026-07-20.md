# Regular05 EGL Map Probe - 2026-07-20

## Decision

EGLImage map/unmap is not the main source of the accepted EGLImage stage cost.
On Regular05, map/unmap overhead is small compared with the full 10.5 ms stage.
The remaining gap is more likely VPI wrapper creation, VPI submit/sync, or
interaction among wrapper creation and VPI scheduling.

## Probe

New patch script:

```text
scripts/patch_mmapi_transcode_egl_map_probe.py
```

Remote sample:

```text
/home/nvidia/orin-nx-project/_mmapi_work/jetson_multimedia_api/samples/99_transcode_egl_map_probe
```

The probe does:

```text
main DMABUF -> input scratch
NvBufSurfaceFromFd(input/output scratch)
input scratch EGLImage map/unmap
output scratch EGLImage map/unmap
input scratch -> output scratch
output scratch -> main DMABUF
```

It does not create VPI wrappers and does not run VPI warp.

## Results

```text
rc: 0
black_border_p95: 0.000000000
black_border_max: 0.000004340
frames_gt_0p01: 0
```

Frame 100 timing:

| Component | Time |
|---|---:|
| input transform | 0.917262 ms |
| NvBufSurfaceFromFd pair | 0.000992 ms |
| input map | 0.067652 ms |
| input unmap | 0.020961 ms |
| output map | 0.035394 ms |
| output unmap | 0.011840 ms |
| scratch copy transform | 0.918671 ms |
| output transform | 0.931407 ms |
| total | 2.904180 ms |

## Interpretation

The map/unmap operations are measurable but small. At frame 100, combined input
and output EGL map/unmap cost is about 0.136 ms. This cannot explain the gap
between transform-only cost and the accepted EGLImage stage cost.

## Claim Boundary

Allowed:

```text
EGLImage map/unmap is not the main bottleneck in the Regular05 probe.
Transform and EGL map/unmap together are still much smaller than the full
accepted EGLImage stage cost.
```

Forbidden:

```text
Map/unmap is free.
Wrapper/submit/sync cost has been solved.
Full real-time EIS.
Zero-copy full chain.
```

## Next Step

The next useful probe is VPI wrapper creation + submit/sync isolation, using an
identity matrix or the same inclusion matrix while keeping transform and map
measurements available for comparison.
