# Device-Stage Lifecycle Budget - 2026-07-23

## Decision

The next device-stage optimization should remain narrow. Existing Nsight/NVTX
and lifecycle repeat evidence does not justify a broad queue-depth,
double-buffering, or multi-in-flight rewrite.

Best current route:

```text
1. Treat stream-only reuse as the only safe lifecycle candidate worth a bounded
   follow-up, because it showed small repeat gains without changing output
   semantics.
2. Keep NvBuffer pair as a quality-preserving dataflow alternative with small
   and variable gains.
3. Do not revive EGLImage image-wrapper reuse, pitch-linear main encode,
   block-linear VPI scratch, or direct mismatched NvBuffer input.
```

## Frozen Scope

```text
source: Regular05 same-source boundary
matrix: resid_r15_s07
matrix convention: source_to_dest
quality semantics: no crop/postprocess or stabilization change
output health: rc=0, fallback=0, readable output
```

This document uses existing evidence only:

```text
results/nsight_device_stage_profile_20260723/
results/device_stage_profile_probe_20260723/repeat/
results/device_stage_lifecycle_probe_20260723/repeat/
```

## Nsight Stage Budget

The absolute wall timings under Nsight capture are slower than normal runs, so
they should be used for attribution rather than throughput claims.

| Stage / Range | EGLImage Avg | NvBuffer Pair Avg | Interpretation |
|---|---:|---:|---|
| `wall_frame_device_stage` | 23.276 ms | 24.175 ms | capture-overhead-inflated frame scope |
| wrap + submit + sync | 10.023 ms | 10.268 ms | dominant profiled region |
| `VPI:vpiImageCreateWrapper` | 1.924 ms | 2.105 ms | wrapper creation remains expensive |
| `vpi_stream_sync` | 2.140 ms | 2.201 ms | sync is larger than submit/warp call |
| `input_transform_main_to_scratch` | 0.870 ms | 0.901 ms | transform sandwich remains visible |
| `output_transform_scratch_to_main` | 0.929 ms | 0.966 ms | transform sandwich remains visible |
| `VPI:Perspective Warp` | 0.763 ms | 0.805 ms | actual warp is not the bottleneck |
| `vpi_submit_perspective_warp` | 0.022 ms | 0.024 ms | submit call is negligible |

Actionability:

| Cost Area | Actionability | Reason |
|---|---|---|
| `vpi_submit_perspective_warp` | none | too small to optimize directly |
| PerspectiveWarp kernel | low | under 1 ms in capture; module already performs well |
| transform sandwich | medium but risky | tied to main-chain block-linear and VPI scratch format boundary |
| wrapper creation/lifecycle | medium | large cost, but image-wrapper reuse is rejected due tearing/failure history |
| stream sync / CUDA sync | medium | material cost; needs overlap/async evidence before broad scheduling work |
| CUDA/EGL register/free/unregister | medium | material lifecycle cost, but route must preserve output semantics |

## CUDA API Budget

| CUDA API | EGLImage Avg | NvBuffer Pair Avg | Meaning |
|---|---:|---:|---|
| `cudaFree` | 1.341 ms | 1.136 ms | lifecycle/free cost is material; large max values indicate initialization/outliers |
| `cudaStreamSynchronize` | 0.568 ms | 0.570 ms | sync cost is material and consistent |
| `cudaGraphicsUnregisterResource` | 0.302 ms | 0.326 ms | EGL/CUDA resource lifecycle cost |
| `cudaGraphicsEGLRegisterImage` | 0.279 ms | 0.300 ms | EGL/CUDA resource lifecycle cost |
| `cudaMalloc` | 0.143 ms | 0.158 ms | smaller but repeated |
| `cudaLaunchKernel` | 0.048 ms | 0.052 ms | not the bottleneck |

Interpretation:

```text
The remaining cost is not a compute-kernel problem. It is resource lifecycle and
synchronization around the VPI/MMAPI boundary.
```

## Existing Lifecycle Repeat Evidence

Five same-source alternating runs compared accepted EGLImage, stream-only reuse,
and format-matched NvBuffer pair.

| Path | Runs | rc=0 | Wall Mean | Wall Median | Stage100 Mean |
|---|---:|---:|---:|---:|---:|
| accepted EGLImage | 5 | 5/5 | 1.928150 s | 1.940980 s | 7.840122 ms |
| stream-only reuse | 5 | 5/5 | 1.882484 s | 1.811826 s | 7.502906 ms |
| NvBuffer pair | 5 | 5/5 | 1.906174 s | 1.911762 s | 7.916916 ms |

Benefit against accepted EGLImage:

| Candidate | Wall Mean | Stage100 | Stage Avg | Wrapper | VPI Warp |
|---|---:|---:|---:|---:|---:|
| stream-only reuse | +2.368% | +4.301% | +1.280% | +6.146% | -14.914% |
| NvBuffer pair | +1.140% | -0.980% | +0.908% | -3.322% | +0.839% |

Interpretation:

```text
stream-only reuse is safe in the repeat evidence and gives the best observed
small lifecycle gain, but the gain is still low-single-digit. NvBuffer pair is
quality-preserving, but this repeat set shows variable timing benefit.
```

## Candidate Selection

| Candidate | Priority | Verifier | Stop Rule |
|---|---|---|---|
| Stream-only reuse repeat or long-run | P1 | same-source wall/stage mean or p50, rc=0, fallback=0 | close as bounded if gain remains below about 3-5% or unstable |
| NvBuffer pair repeat with resid anchor | P2 | same-source timing and output size/readability | keep as quality-preserving alternative if gain remains variable |
| Wrapper/register/free/sync micro-probe | P2 | stage budget reduces lifecycle calls without output change | stop if it revives rejected image-wrapper reuse or changes semantics |
| Device-stage perf/watt | P2 | explicit power source plus wall/FPS/FPS/W | label as unavailable if sampling cannot be done safely |
| Queue-depth / double buffering | deferred | requires clear idle-gap evidence | do not open from current evidence |

## P3 / P4 Execution Boundary

The current evidence is enough to choose candidates, but not enough to justify a
broad implementation. If P3 is executed, the only reasonable repeat is:

```text
accepted EGLImage vs stream-only reuse, same Regular05 source, same resid_r15_s07
matrix, multiple alternating runs, with rc/fallback/output checks.
```

If P4 is executed, the result must be labeled:

```text
device-stage perf/watt evidence
not full EIS pipeline perf/watt
not zero-copy
not product real-time EIS
```

## Current Recommendation

Proceed with a bounded P3/P4 only if Jetson execution is available without
changing system configuration. Otherwise P5 can close this loop as:

```text
Existing profiling already identifies wrapper/sync/transform/lifecycle as the
dominant device-stage cost. The only safe candidate, stream-only reuse, has
low-single-digit gains. That is not enough to justify a large scheduler rewrite.
```
