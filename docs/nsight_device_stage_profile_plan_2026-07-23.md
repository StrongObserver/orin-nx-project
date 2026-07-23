# Nsight Device-Stage Profile Plan - 2026-07-23

## Purpose

This is the minimum experiment plan and first probe result for the current
`nsight_device_stage_profile_v1` contract. It turns the device-stage profiling
method into an Orin NX stabilization-pipeline question:

```text
Is the accelerator path limited by hardware execution, or by host-side
dataflow/scheduling around wrapper, sync, transform, and encode?
```

Do not implement a new scheduler before this profile exists.

## Current Instrumentation Already Available

Existing patchers and reports already expose timing anchors:

| Existing tool/report | Relevant signal |
|---|---|
| `scripts/patch_mmapi_vpi_transcode_eglimage_warp.py` | `EGL_STAGE_TIMING`, `VPI_EGLIMAGE_WARP`, `MATRIX_HANDOFF` |
| `scripts/patch_mmapi_vpi_transcode_nvbuffer_pair_warp.py` | `NVBUFFER_PAIR_STAGE_TIMING`, `VPI_NVBUFFER_PAIR_WARP`, `MATRIX_HANDOFF` |
| `scripts/patch_mmapi_transcode_vpi_wrapper_create_probe.py` | `VPI_WRAPPER_CREATE_PROBE_STAGE` |
| `docs/presentation/hardware_acceleration_boundary.md` | current stage table and NvBuffer pair comparison |
| `docs/regular_gate_nvbuffer_pair_resid_2026-07-23.md` | current quality-preserving NvBuffer pair closeout |

These logs are enough for a first instrumentation audit. NVTX should be added
only if a timeline view is needed beyond current CSV/log evidence.

## Proposed Stage Ranges

If NVTX is added, use stable stage names:

```text
decode_dequeue
matrix_handoff
input_transform_main_to_scratch
egl_or_nvbuffer_wrap
vpi_submit_perspective_warp
vpi_stream_sync
wrapper_destroy_or_unwrap
output_transform_scratch_to_main
encode_queue
wall_frame
```

The goal is not fine-grained code beauty. The goal is to make Nsight show where
time is spent and whether hardware is idle.

## Minimum A/B

Run only after instrumentation is confirmed:

| Path | Matrix | Purpose |
|---|---|---|
| Accepted EGLImage path | `resid_r15_s07` when available | baseline quality-preserving stage |
| Format-matched NvBuffer pair | `resid_r15_s07` | compare wrapper/dataflow cost without changing quality anchor |

Frozen boundaries:

```text
same source
same matrix
same crop/postprocess
same frame-count and FPS boundary
same output readability checks
no quality tuning
no pitch-linear main encoder path
no EGLImage image-wrapper reuse revival
```

## What To Look For

The profiling method is useful only if the timeline exposes a concrete system
pattern:

| Observation | Meaning | Next action |
|---|---|---|
| VPI/CUDA/NVENC idle while CPU side is busy | host dataflow/scheduling bottleneck | consider queue depth / double buffering contract |
| VPI sync dominates with no visible overlap | synchronous stage boundary | test async or staged pipeline only under new contract |
| transform sandwich dominates | memory layout boundary | only compare format-stable alternatives, not zero-copy claims |
| NvBuffer pair reduces wrapper but not sync/transform | small dataflow improvement already bounded | record as current best, do not overbuild |
| no idle bubble and no large host wait | scheduler rewrite is not justified | close as methodology reference |

## Stop Rules

Stop before implementation if:

```text
Nsight capture requires a GUI/manual step not available in the current session.
The accepted C++ sample is not present on Jetson.
Adding NVTX would require broad MMAPI sample rewrite.
The proposed change would alter matrix quality, crop/postprocess, or output semantics.
```

In that case, report the blocker in chat and keep the current evidence as:

```text
stage log timing + device-stage profiling method + planned Nsight contract
```

## Expected Output

If executed later, the evidence package should contain:

```text
Nsight .nsys-rep or exported summary
stage timing table
short interpretation of hardware idle vs host wait
one claim-boundary paragraph for presentation docs
```

## First Probe Completed

A log-based A/B has already been run before adding NVTX:

```text
results/device_stage_profile_probe_20260723/repeat/
```

Inputs were frozen:

```text
same Regular05 source
same resid_r15_s07 matrix
same accepted EGLImage path vs format-matched NvBuffer pair path
5 alternating runs
```

Result:

| Metric | EGLImage mean | NvBuffer pair mean | Improvement |
|---|---:|---:|---:|
| Wall time | 1.913690 s | 1.864678 s | 2.56% |
| Stage frame100 | 7.823870 ms | 7.204884 ms | 7.91% |
| Stage running avg | 10.240050 ms | 9.898324 ms | 3.34% |
| VPI warp avg | 1.537340 ms | 1.526802 ms | 0.69% |
| Wrapper call | 5.896924 ms | 5.442238 ms | 7.71% |

The first probe answers part of the device-stage profiling question:

```text
The measurable gain is in wrapper/dataflow stage cost, not in the VPI warp
kernel. At the time of this plan, that supported continuing to Nsight/NVTX
profiling, but did not justify building a new scheduler or claiming zero-copy.
That profiling has since been completed; see
`docs/nsight_device_stage_profile_result_2026-07-23.md`.
```
