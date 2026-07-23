# Claim Boundary

Use this file to keep interview, README, and resume wording honest.

## Safe Headline

```text
Jetson Orin NX heterogeneous video compute and device-side dataflow optimization.
EIS is used as a representative real-time vision workload to measure quality,
latency, VPI/CUDA module acceleration, MMAPI/NVENC memory-format boundaries,
wrapper lifecycle, sync, transform cost, and perf/watt trade-offs.
```

## Allowed Claims

| Claim | Evidence |
|---|---|
| Regular is the in-domain EIS quality gate | `nus_regular_gate_v1`, five-clip objective pass and human review |
| Challenge sets define model boundaries | Running, QuickRotation, Parallax, Crowd reports |
| `resid_r15_s07` is the accepted Regular-gate stabilization-strength recovery result | Residual closed-loop report and review videos |
| CPU performance baseline reduces Regular05 estimate cost | `8.568 ms -> 3.022 ms`, wall `8.473 s -> 7.565 s` |
| VPI CUDA accelerates high-resolution PerspectiveWarp modules | 1080p/1440p/4K module reruns and 4K perf/watt probe |
| Python appsink/appsrc is not the next acceleration path | 7.93 ms/frame readback and 15.81 ms/frame pass-through |
| Accepted C++ MMAPI/VPI/NVENC path works as a device-side stage | EGLImage-wrapper path, Regular gate reviews, timing probes |
| NvBuffer pair preserves `resid_r15_s07` and gives a small stage gain | Five Regular runs and same-source Regular05 timing |
| Nsight shows wrapper/sync/transform/lifecycle cost dominates | `nsight_device_stage_profile_result_2026-07-23.md` |
| Stream-only reuse gives a small lifecycle gain | 10-run same-source Regular05 repeat: wall mean `1.947 -> 1.844 s`, stage avg `10.336 -> 9.680 ms` |

## Forbidden Claims

Do not say:

```text
This is a finished full real-time EIS product.
The whole EIS pipeline is accelerated by VPI.
The project has zero-copy full chain.
NvBuffer pair is zero-copy.
Queue depth or double buffering has been proven beneficial.
Stream-only reuse proves zero-copy.
VPI optical flow accelerates our motion estimation.
Running / Parallax / Crowd are solved.
The result is product-grade or all-scene EIS quality.
Outdoor-car inverse/post-geometry is Regular05 EIS-quality evidence.
safe103_crop98 or inclusion_source_to_dest is the current quality anchor.
```

## Precise Wording

### VPI

Good:

```text
VPI CUDA helps on high-resolution PerspectiveWarp modules and improves 4K
FPS/W, but a simple VPI backend swap is slower in the current 640x360 Python
EIS pipeline.
```

Bad:

```text
VPI accelerated my EIS pipeline.
```

### NvBuffer Pair

Good:

```text
Format-matched NvBuffer pair preserves the accepted `resid_r15_s07` quality
anchor and reduces a small part of the measured device-side stage cost.
```

Bad:

```text
NvBuffer pair makes the pipeline zero-copy.
```

### Nsight

Good:

```text
Nsight/NVTX showed that the bottleneck is wrapper, sync, transform, and lifecycle
cost rather than `vpiSubmitPerspectiveWarp` alone. That is why I did not open a
broad queue-depth or double-buffering rewrite without stronger idle-gap evidence.
```

Bad:

```text
Nsight proved double buffering will speed it up.
```

### EIS Quality

Good:

```text
The Regular gate is the in-domain quality result. Challenge sets expose global
warp limits such as FOV pressure, fast rotation, parallax, and foreground
motion.
```

Bad:

```text
The stabilizer works on all scenes.
```

## Current Stage Status

```text
Quality recovery: sealed around resid_r15_s07.
NvBuffer pair correctness: sealed as quality-preserving small dataflow gain.
Nsight/NVTX profiling: completed first capture and lifecycle follow-up.
Stream-only reuse: promoted as a small accepted lifecycle optimization.
P6/P7 scheduler or double-buffering work: still not triggered.
Current best next action: use the final evidence package plus lifecycle result
for README, interview, and presentation. Start broader engineering only through
a new scoped contract.
```

## Resume-Safe Bullet

```text
Built a Jetson Orin NX heterogeneous video-compute pipeline using EIS as a
real-time workload: established Regular/Challenge quality gates, optimized CPU
motion-estimation cost, measured VPI CUDA 4K PerspectiveWarp speed and FPS/W,
validated a C++ MMAPI/VPI/NVENC device-side warp/encode path, and used
NVTX/Nsight to localize remaining cost to wrapper/sync/transform lifecycle
rather than the warp kernel alone.
```
