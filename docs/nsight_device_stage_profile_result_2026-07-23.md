# Nsight Device-Stage Profile Result - 2026-07-23

## Decision

The RK3588-inspired route is useful as a profiling method, but the Orin NX
result does not justify building a new queue-depth, double-buffering, or
multi-in-flight scheduler yet.

Why:

```text
vpiSubmitPerspectiveWarp is about 0.02 ms per frame.
The large costs are wrapper/dataflow/sync/transform and CUDA register/free/sync.
The format-matched NvBuffer pair path gives small log-based stage gains, but the
Nsight capture does not show a large hidden hardware-starvation win.
```

Therefore:

```text
P6/P7 queue-depth or double-buffering A/B is not triggered.
The next useful work, if any, is narrower: reduce wrapper/register/free/sync
cost or find a safer buffer lifecycle path without reviving rejected wrapper
reuse.
```

## Evidence

Raw evidence is local and ignored by Git:

```text
results/rk3588_idea_probe_20260723/repeat/
results/nsight_device_stage_profile_20260723/
```

Tracked context:

```text
docs/rk3588_npu_idea_mapping_2026-07-23.md
docs/nsight_device_stage_profile_plan_2026-07-23.md
configs/harness/contracts/nsight_device_stage_profile_v1.json
```

## Log-Based Repeat A/B

Five alternating runs, same source and same `resid_r15_s07` matrix:

| Metric | EGLImage mean | NvBuffer pair mean | Improvement |
|---|---:|---:|---:|
| Wall time | 1.913690 s | 1.864678 s | 2.56% |
| Wall time median | 1.905795 s | 1.843885 s | 3.25% |
| Stage frame100 | 7.823870 ms | 7.204884 ms | 7.91% |
| Stage running avg | 10.240050 ms | 9.898324 ms | 3.34% |
| VPI warp avg | 1.537340 ms | 1.526802 ms | 0.69% |
| Wrapper call | 5.896924 ms | 5.442238 ms | 7.71% |
| First stage | 282.794 ms | 267.135 ms | 5.54% |
| Fallback | 0 / 5 runs | 0 / 5 runs | no regression |
| Output success | 5 / 5 runs | 5 / 5 runs | no regression |
| Output size | 3415439 bytes | 3415439 bytes | identical |

This confirms a small but real device-stage dataflow benefit for NvBuffer pair
under the log-based measurement.

## Nsight / NVTX Capture

Two NVTX-instrumented samples were built and captured on Jetson:

```text
99_vpi_transcode_matrix_eglimage_timing_nvtx
99_vpi_transcode_matrix_nvbuffer_pair_nvtx
```

Both generated `.nsys-rep` and exported CSV stats successfully.

Key NVTX ranges:

| Range | EGLImage avg | NvBuffer pair avg | Interpretation |
|---|---:|---:|---|
| `wall_frame_device_stage` | 23.2764 ms | 24.1754 ms | Nsight capture overhead makes absolute wall timing slower; do not use this as normal-run throughput |
| `eglimage_wrap_submit_sync` / `nvbuffer_wrap_submit_sync` | 10.0225 ms | 10.2681 ms | wrap + submit + sync remains the dominant stage |
| `VPI:vpiImageCreateWrapper` | 1.9237 ms | 2.1050 ms | wrapper creation remains expensive |
| `vpi_stream_sync` | 2.1403 ms | 2.2007 ms | sync is much larger than submit |
| `input_transform_main_to_scratch` | 0.8702 ms | 0.9008 ms | transform sandwich remains nontrivial |
| `output_transform_scratch_to_main` | 0.9286 ms | 0.9664 ms | transform sandwich remains nontrivial |
| `VPI:Perspective Warp` | 0.7630 ms | 0.8051 ms | actual warp is not the bottleneck |
| `vpi_submit_perspective_warp` | 0.0220 ms | 0.0241 ms | submit call is effectively negligible |

Key CUDA API summaries:

| CUDA API | EGLImage avg | NvBuffer pair avg | Meaning |
|---|---:|---:|---|
| `cudaStreamSynchronize` | 0.5682 ms | 0.5700 ms | sync overhead dominates much more than submit |
| `cudaFree` | 1.3408 ms | 1.1361 ms | lifecycle/free cost is material |
| `cudaGraphicsUnregisterResource` | 0.3023 ms | 0.3257 ms | EGL/CUDA resource lifecycle is material |
| `cudaGraphicsEGLRegisterImage` | 0.2788 ms | 0.3005 ms | register cost is material |
| `cudaLaunchKernel` | 0.0485 ms | 0.0522 ms | launch/kernel API cost is small |

## What This Says About The Blogger's Idea

The RK3588 case had a large scheduler/runtime problem:

```text
Python / locks / RKNN runtime could not feed the NPU well enough.
Moving to C++ shared-memory dataflow gave a very large throughput win.
```

The Orin result is different:

```text
We are already in C++ MMAPI/VPI/NVENC.
The problem is not Python GIL or RKNN-style multi-core scheduling.
The remaining cost is wrapper/register/free/sync/transform lifecycle.
```

So the transferable lesson is real:

```text
Do not trust hardware kernel timing alone.
Measure wall-clock and host-side dataflow.
```

But the implementation idea does not transfer directly:

```text
No RKNN core mask equivalent.
No direct rknn_create_mem equivalent.
No evidence yet that queue depth or double buffering will produce a large win.
```

## P6/P7 Decision

Do not open a queue-depth or double-buffering implementation loop yet.

Minimum bar to open that loop later:

```text
Nsight must show a clear idle gap that can plausibly be removed by overlap.
The proposed path must preserve source, matrix, crop/postprocess, and output
readability.
It must not revive EGLImage image-wrapper reuse, pitch-linear main encode,
block-linear VPI scratch, or any known rejected route.
```

## Stream-Only Reuse Follow-Up

To avoid stopping too early, a same-source lifecycle follow-up was also run after
the Nsight capture.

Evidence:

```text
results/rk3588_lifecycle_probe_20260723/repeat/
```

Compared paths:

```text
accepted EGLImage path
EGLImage stream-only reuse path
format-matched NvBuffer pair path
```

All paths used the same Regular05 source and the same `resid_r15_s07` matrix.
Each path ran five alternating runs.

Summary:

| Metric | EGLImage | Stream-only reuse | NvBuffer pair |
|---|---:|---:|---:|
| Runs | 5 | 5 | 5 |
| rc=0 | 5/5 | 5/5 | 5/5 |
| Fallback total | 0 | 0 | 0 |
| Wall mean | 1.928150 s | 1.882484 s | 1.906174 s |
| Wall median | 1.940980 s | 1.811826 s | 1.911762 s |
| Stage frame100 mean | 7.840122 ms | 7.502906 ms | 7.916916 ms |
| Stage running avg mean | 10.176194 ms | 10.045934 ms | 10.083822 ms |
| Wrapper mean | 5.864166 ms | 5.503740 ms | 6.058994 ms |
| VPI warp mean | 1.520012 ms | 1.746708 ms | 1.507266 ms |

Benefit vs accepted EGLImage:

| Candidate | Wall mean | Stage frame100 | Stage avg | Wrapper | VPI warp |
|---|---:|---:|---:|---:|---:|
| Stream-only reuse | +2.368% | +4.301% | +1.280% | +6.146% | -14.914% |
| NvBuffer pair | +1.140% | -0.980% | +0.908% | -3.322% | +0.839% |

Interpretation:

```text
Stream-only reuse is safe in this repeat test and gives small wall/stage gains,
but the gain is still below the threshold for a larger scheduling rewrite.
NvBuffer pair remains a small and variable dataflow alternative rather than a
clear next optimization route.
```

Updated decision:

```text
P6/P7 remains not triggered. The safe lifecycle experiments show low-single-digit
wall/stage gains, not a strong queue-depth or double-buffering opportunity.
```

## Current Best Claim

Allowed:

```text
The RK3588 idea was tested as an Orin profiling/dataflow methodology.
On Orin, format-matched NvBuffer pair gives a small device-stage benefit in
log-based repeat runs.
Nsight shows the bottleneck is wrapper/sync/transform/lifecycle cost rather than
the VPI PerspectiveWarp submit call.
```

Forbidden:

```text
The RK3588 zero-copy optimization was copied to Orin.
Orin now has zero-copy.
Queue depth / double buffering has been proven beneficial.
Full EIS pipeline acceleration has been achieved.
```
