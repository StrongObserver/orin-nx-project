# Device-Stage Profiling Methodology - 2026-07-23

## Decision

This project uses EIS/video stabilization as the workload. Device-stage
optimization must therefore start from the accepted stabilization source,
matrix, crop/postprocess, and review boundary.

The useful methodology is:

```text
separate hardware execution time from wall-clock time
separate VPI submit, VPI sync, wrapper lifecycle, transforms, encode, and wall time
check whether host-side dataflow is starving hardware before writing a scheduler
prefer small same-source A/B probes over broad pipeline rewrites
fix Jetson performance mode and record the profiling environment before claims
```

The corresponding Orin NX route is C++ MMAPI/VPI/NVENC device-stage profiling
under frozen EIS workload semantics. A new dataflow A/B is justified only if the
timeline shows a real idle bubble, avoidable sync, or resource-lifecycle cost
that can be reduced without changing stabilization output semantics.

## Mapping

| Profiling question | Orin NX evidence target | Verifier |
|---|---|---|
| Is hardware time much smaller than wall-clock time? | Separate VPI submit/sync, wrapper lifecycle, transforms, encode, and wall time | NVTX/Nsight timeline plus existing timing CSV |
| Is Python or host scheduling the bottleneck? | Keep Python appsink/appsrc out of the final device-stage path; inspect live-producer timing only as boundary evidence | Existing appsink/appsrc timing and producer scheduling evidence |
| Is overlap or queueing plausibly useful? | Look for VPI/CUDA/NVENC idle gaps between device-stage ranges | Nsight shows an idle gap that a scoped A/B could remove |
| Is the cost a memory-format boundary? | Compare block-linear main chain, pitch-linear NV12_ER scratch, NvBuffer pair, and transform sandwich cost | Same-source output sanity plus stage timing |
| Are hidden conversions corrupting quality or color? | Keep explicit BGR8/NV12/NV12_ER handling and reject green/tearing outputs | Format probe, color correctness, readable output |
| Are perf numbers stable enough to claim? | Fix Jetson power/perf mode where possible and preserve repeat-run summaries | nvpmodel/tegrastats/INA evidence where available |

## Current Device Path

The accepted device-stage path is:

```text
MMAPI/NVDEC block-linear NV12 main chain
-> NvBufSurfTransform to pitch-linear NV12_ER scratch
-> VPI CUDA PerspectiveWarp
-> NvBufSurfTransform back to block-linear NV12
-> NVENC
```

Existing evidence points to:

```text
wrapper lifecycle
VPI sync
NvBufSurfTransform sandwich
producer scheduling in earlier live runs
format/layout mismatch between main chain and VPI scratch
```

Therefore, the correct next action after a profiling gap is not a generic
scheduler. It is a narrow same-source dataflow or lifecycle A/B that preserves
the accepted EIS workload boundary.

## Minimum Experiment

Do not implement a scheduler first. The minimum experiment is:

```text
1. Add or identify stage markers for decode, input transform, wrapper/NvBuffer
   wrap, VPI submit, VPI sync, output transform, encode, and wall time.
2. Capture an Nsight Systems report or equivalent exported timing summary.
3. Look for hardware idle gaps and host-side wait gaps.
4. Only if gaps exist, open a new dataflow A/B contract for queue depth,
   double buffering, async staging, or buffer lifecycle changes.
```

Frozen boundaries:

```text
same source
same matrix, preferably resid_r15_s07 for quality-preserving comparison
same crop/postprocess boundary
same frame-count/FPS boundary
no EGLImage image-wrapper reuse revival
no pitch-linear main encoder chain
no block-linear VPI scratch pair
no zero-copy claim unless measured
```

## Actual Probe Result

The first same-source A/B was executed on Jetson with the same source and same
`resid_r15_s07` matrix:

```text
results/device_stage_profile_probe_20260723/repeat/
```

Five alternating runs compared:

```text
accepted EGLImage path
format-matched NvBuffer pair path
```

Summary:

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

Interpretation:

```text
The useful result is a dataflow/profiling result. NvBuffer pair improves the
device stage modestly, mainly around wrapper/dataflow cost. VPI warp itself is
nearly unchanged, so the benefit is not a PerspectiveWarp kernel speedup.
```

Decision:

```text
Continue only as profiling-first device-stage work. Do not build a new
multi-threaded scheduler until Nsight/NVTX or equivalent evidence shows hardware
idle gaps or host-side wait that queue depth / double buffering can actually
remove.
```

## Interview Use

Good wording:

```text
I treated the stabilization workload as fixed first, then profiled where time
goes in the device stage: wrapper lifecycle, synchronization, transform
sandwich, VPI warp, and encode. The key lesson was that kernel timing alone is
misleading; the bottleneck is around MMAPI/VPI/NVENC dataflow and lifecycle
cost, not the PerspectiveWarp submit call.
```

Bad wording:

```text
I implemented zero-copy on Orin.
I proved queue-depth or double-buffering is beneficial.
I changed the workload from stabilization to an unrelated accelerator demo.
```
