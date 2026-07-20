# Regular05 Transform Cost Probe - 2026-07-20

## Decision

`NvBufSurfTransform` is a measurable cost, but it is not the whole EGLImage stage
cost. A transform-only probe on Regular05 shows the steady transform dataflow is
about 2.7 ms per frame for three transforms, while the accepted EGLImage stage
was about 10.5 ms and stream-only / wrapper variants remained around 9-10 ms.

The next performance work should separate VPI wrapper/submit/sync overhead from
the transform cost. Optimizing transforms alone cannot explain or remove the
whole gap.

## Probe

New patch script:

```text
scripts/patch_mmapi_transcode_transform_only_probe.py
```

Remote sample:

```text
/home/nvidia/orin-nx-project/_mmapi_work/jetson_multimedia_api/samples/99_transcode_transform_only_probe
```

Input:

```text
regular_gate05_regular_6 source.h264
```

The sample does:

```text
main DMABUF -> input scratch
input scratch -> output scratch
output scratch -> main DMABUF
```

It does not run VPI warp.

## Results

```text
rc: 0
black_border_p95: 0.000000000
black_border_max: 0.000021701
frames_gt_0p01: 0
```

Timing samples:

| Frame | input ms | scratch-copy ms | output ms | total ms | running avg ms |
|---:|---:|---:|---:|---:|---:|
| 1 | 0.961385 | 0.850016 | 0.854977 | 2.666380 | 2.666380 |
| 2 | 0.844992 | 0.850113 | 0.851809 | 2.546910 | 2.606650 |
| 3 | 0.835071 | 0.849025 | 0.856449 | 2.540540 | 2.584610 |
| 4 | 0.855490 | 0.872034 | 0.860033 | 2.587560 | 2.585350 |
| 5 | 0.864001 | 17.657200 | 0.943431 | 19.464600 | 5.961200 |
| 100 | 0.920774 | 0.902885 | 0.911653 | 2.735310 | 2.888830 |

Frame 5 has a one-off spike in scratch-copy. The steady-state transform cost is
closer to 2.5-2.8 ms for the three-transform chain.

## Interpretation

The accepted EGLImage stage includes:

```text
input NvBufSurfTransform
VPI wrapper creation / VPI submit / VPI sync
output NvBufSurfTransform
surface map/unmap and surrounding synchronization
```

The transform-only probe shows that the three-transform path alone is much
smaller than the full EGLImage stage. Therefore the remaining performance gap is
likely in VPI wrapper creation, EGLImage map/unmap, VPI submit/sync, or
interaction among those operations.

## Claim Boundary

Allowed:

```text
Regular05 transform-only dataflow was measured.
Three NvBufSurfTransform calls cost about 2.7 ms steady-state.
The full EGLImage stage cost cannot be attributed to transforms alone.
```

Forbidden:

```text
Transform cost is fully optimized.
Full real-time EIS.
Zero-copy full chain.
VPI optical-flow acceleration.
```

## Next Step

The next useful probe is wrapper/submit/sync isolation:

```text
1. one transform into scratch;
2. VPI identity or no-op operation if available;
3. output transform back;
4. compare against transform-only baseline.
```
