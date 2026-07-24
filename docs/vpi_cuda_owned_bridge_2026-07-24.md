# VPI CUDA-Owned Bridge - Local Preparation - 2026-07-24

## Decision

The next device-stage route is implemented and locally validated at source level:

```text
MMAPI block-linear main surface
-> NvBufSurfTransform to pitch-linear NV12_ER input scratch
-> sequential EGL-to-CUDA copy
-> persistent CUDA-owned pitch-linear NV12 input
-> VPI CUDA PerspectiveWarp
-> persistent CUDA-owned pitch-linear NV12 output
-> sequential CUDA-to-EGL copy
-> NvBufSurfTransform to block-linear encoder surface
-> NVENC
```

This is materially different from the rejected path. The old path let custom
CUDA or VPI random-sample the EGL-mapped scratch directly. The new path uses the
EGL surfaces only for sequential copies; VPI reads and writes CUDA-owned memory.

Current status after Jetson verification:

```text
local source preparation: pass
Jetson build: pass
identity video: pass
translate / non-identity video: fail
resid_r15_s07 replay: not run on this bridge because translate failed
same-input acceleration claim: rejected for this bridge
```

This bridge is not accepted as the device-stage warp path. The usable result is
the diagnostic boundary: full-frame copy and identity are safe, and VPI warp on
standalone CUDA-owned RGBA memory is correct, but the MMAPI bridge cannot yet
return a visually correct non-identity warped frame to NVENC.

## Why This Route

The route composes three measured boundaries:

1. `cuda_double_surface_debug_v1` Test1 proved sequential full-frame CUDA copy
   between EGL-mapped pitch-linear NV12_ER scratch surfaces is readable.
2. `experiments/vpi_cuda_mem_warp` proved VPI CUDA PerspectiveWarp works on
   CUDA-owned pitch-linear memory.
3. The accepted MMAPI/VPI/NVENC path already defines the source-to-destination
   matrix convention, block-linear encoder boundary, and visual review process.

The route does not repeat these rejected ideas:

```text
custom CUDA random sampling over EGL scratch
direct VPI CUDA-pitch wrapper around CUeglFrame pointers
image-wrapper reuse across changing EGLImages
pitch-linear main chain into NVENC
```

## Files

Active contract:

```text
configs/harness/contracts/vpi_cuda_owned_bridge_v1.json
```

Patcher:

```text
removed after negative closeout; do not reuse this failed bridge implementation
```

Spatial verifier:

```text
scripts/measure_spatial_shift_coherence.py
```

## Historical Local Validation

### Patcher validation

Historical status before removal:

```text
self_test_status: pass
```

The self-test proves:

```text
the patch applies to a synthetic multivideo_transcode fixture
the second patch is idempotent
the generated helper has no custom __global__ warp kernel
the generated helper contains VPI_IMAGE_BUFFER_CUDA_PITCH_LINEAR
copy-in, VPI PerspectiveWarp, and copy-out are present
the Makefile receives CUDA and VPI include/link flags exactly once
```

### Generated C++ syntax validation

The generated helper was compiled locally with `g++ -std=c++14 -fsyntax-only`
against minimal CUDA/VPI/MMAPI API stubs.

Result:

```text
cpp_stub_compile_exit=0
```

This catches C++ control-flow and type/syntax defects in the generated helper.
It does not replace compilation against the real Jetson headers and libraries.

### Spatial-verifier regression

The new verifier was tested against the existing frame-100 evidence:

```text
clean candidate:
  results/cuda_double_surface_debug_20260724/frame_inspect_recheck/test1_0100.png

rejected candidate:
  results/cuda_double_surface_debug_20260724/frame_inspect_recheck/test2_0100.png
```

Clean full-frame copy versus source:

| Metric | Result |
|---|---:|
| band shift spread p95 | 0.075069 px |
| expected shift error p95 | 0.073032 px |
| ideal-reference MAE p95 | 3.108052 |
| decision | pass |

Rejected translate versus ideal 8-pixel translation:

| Metric | Result |
|---|---:|
| band shift spread p95 | 0.841730 px |
| expected shift error p95 | 0.860972 px |
| ideal-reference MAE p95 | 42.612007 |
| decision | fail |

The important correction is that phase correlation alone is insufficient: the
old corrupt output still appears close to an 8-pixel global shift. The
ideal-reference MAE gate rejects the severe content corruption.

After Jetson negative closeout, `scripts/patch_mmapi_vpi_cuda_owned_bridge.py`
and `experiments/vpi_cuda_pitch_warp_correctness/` were removed from the active
workspace so future agents do not accidentally reuse a known-bad bridge as an
optimization path. The measured result and evidence paths remain recorded here.

## Jetson Result

Fresh Jetson sample:

```text
/home/nvidia/orin-nx-project/_mmapi_work/jetson_multimedia_api/samples/99_vpi_cuda_owned_bridge_20260724_08
```

Evidence directory:

```text
/home/nvidia/orin-nx-project/results/vpi_cuda_owned_bridge_20260724/
C:\Users\Admin\Desktop\orin nx project\results\vpi_cuda_owned_bridge_20260724\
```

### Identity

`identity_fix02` passed:

| Metric | Result |
|---|---:|
| frames | 180 |
| resolution | 640x360 |
| black-border p95 | 0.000000000 |
| source-vs-identity center MAE | 2.821918 |
| source-vs-identity center p95 | 7.305556 |
| spatial coherence | pass |

### Non-Identity Attempts

| Candidate | Geometry | Black Border | Visual / Metric Result | Decision |
|---|---|---|---|---|
| direct NV12 VPI warp, dx=8 | roughly shifted | p95 0.071960286 | lower half corrupted; ideal-reference MAE p95 35.235669 | reject |
| direct NV12 VPI warp with queried plane sizes | roughly shifted | p95 0.119625651 | still corrupted; ideal-reference MAE p95 31.444161 | reject |
| RGBA intermediate + VPI convert back to NV12 | roughly shifted | p95 0.000004557 | output still has large content/color error; ideal-reference MAE p95 51.682096 | reject |
| RGBA intermediate + custom RGBA-to-NV12 writeback | roughly shifted | p95 0.000008681 | bridge-internal RGBA warp is correct, but final NV12/encoded frame has large color/content error; ideal-reference MAE p95 35.314408 | reject |

Standalone diagnostic, now historical:

```text
experiments/vpi_cuda_pitch_warp_correctness
```

This standalone test proved VPI CUDA PerspectiveWarp over CUDA-owned RGBA pitch
memory is correct by itself:

| Mode | mean_abs | mean_abs_center | max_abs |
|---|---:|---:|---:|
| identity | 0 | 0 | 0 |
| translate dx=8 | 0 | 0 | 0 |
| translate dx=-8 | 0 | 0 | 0 |

Bridge-internal RGBA dump also showed `output_rgba` matched the ideal 8-pixel
translation with `mean_abs=0`. Therefore the remaining failure is after the
correct RGBA warp, when returning to NV12/NVENC inside the current bridge.

## Accepted Path Recheck

Because the CUDA-owned bridge did not pass non-identity visual correctness, the
validated fallback remains the existing VPI-managed MMAPI paths.

Same Regular05 source and `resid_r15_s07` matrix, 5 alternating runs:

| Path | rc=0 | fallback | wall mean |
|---|---:|---:|---:|
| accepted EGLImage | 5/5 | 0 | 1.896964 s |
| stream-only reuse | 5/5 | 0 | 1.842633 s |
| NvBuffer pair | 5/5 | 0 | 1.884400 s |

Wall-time benefit against accepted EGLImage:

| Candidate | Benefit |
|---|---:|
| stream-only reuse | 2.864% |
| NvBuffer pair | 0.662% |

Timing-instrumented EGLImage vs stream-only reuse, 5 alternating runs:

| Path | rc=0 | fallback | wall mean | wrapper mean | stage100 mean | stage avg mean |
|---|---:|---:|---:|---:|---:|---:|
| EGLImage timing | 5/5 | 0 | 1.906795 s | 5.695632 ms | 7.615494 ms | 10.089808 ms |
| stream-only reuse | 5/5 | 0 | 1.884477 s | 5.597740 ms | 7.591920 ms | 9.971878 ms |

Stream-only reuse benefit in this run:

| Metric | Benefit |
|---|---:|
| wall mean | 1.170% |
| wrapper mean | 1.719% |
| stage100 mean | 0.310% |
| stage avg mean | 1.169% |

This is a real low-single-digit lifecycle/dataflow improvement, not a large
acceleration result.

Review copy:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260724_vpi_cuda_owned_bridge_and_accepted_path\20260724_regular05_accepted_paths_source_egl_stream_nvbuf_grid.mp4
```

## Startup Black Fix

Human review of the accepted-path grid found a brief left-edge black exposure in
the first seconds. Source was checked separately and did not contain the issue.
The exposure was synchronized across `egl`, `stream_reuse`, and `nvbuf_pair`,
which points to the startup portion of the `resid_r15_s07` matrix sequence.

Diagnosis, first 90 frames:

| Video | max left80 | mean left80 |
|---|---:|---:|
| source | 0.000000000 | 0.000000000 |
| old stream | 0.044722222 | 0.002102238 |

First fix:

```text
compute inclusion-safe extra scale for resid_r15_s07
safety_px = 4
hold startup FOV scale for 60 frames
fade back to original matrix over 30 frames
use accepted stream-only reuse path for output
```

Result:

| Video | max left80 first 90 | mean left80 first 90 | black-border p95 | black-border max |
|---|---:|---:|---:|---:|
| old stream | 0.044722222 | 0.002102238 | not used for final | not used for final |
| startup FOV v2 | 0.000000000 | 0.000000000 | 0.000000000 | 0.000633681 |

Review copy:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260724_regular05_startup_black_fix\20260724_regular05_startup_black_fix_source_old_fixed_grid_30fps.mp4
```

The 30fps copy is the review target. Earlier MP4 conversions used 25fps and
therefore looked slower than the original 30fps H264 source.

Follow-up human review found that `startup FOV v2` still had slight zooming
because its extra scale changes frame by frame. The second candidate used one
constant inclusion-safe extra scale for the first 90 frames:

```text
constant_extra_scale = 1.035641520
```

Constant-FOV result, first 90 frames:

| Video | max left80 | mean left80 |
|---|---:|---:|
| old stream | 0.044722222 | 0.002102238 |
| startup FOV v2 | 0.000000000 | 0.000000000 |
| constant FOV | 0.000000000 | 0.000000000 |

Constant-FOV full-video black-border summary:

| Metric | Value |
|---|---:|
| black-border p95 | 0.000000000 |
| max black-border ratio | 0.000646701 |
| frames > 0.1% black | 0 |

Current recommended review copy:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260724_regular05_startup_black_fix\20260724_regular05_startup_black_fix_source_old_v2_const_grid_30fps.mp4
```

The user then still saw a 3-4s scale switch. Root cause: the 90-frame constant
candidate returned from scale `1.272814399` to the original `1.229010594` at
frame 90, exactly around 3 seconds at 30fps. The final candidate uses one
constant inclusion-safe scale for all 180 frames:

```text
constant_extra_scale_full = 1.038357587
```

Final constant-FOV result:

| Video | max left80 first 180 | mean left80 first 180 | black-border p95 | max black-border |
|---|---:|---:|---:|---:|
| old stream | 0.044722222 | 0.001074846 | not used for final | not used for final |
| const90 | 0.004270833 | 0.000023727 | not used for final | not used for final |
| constant FOV full | 0.000000000 | 0.000000000 | 0.000000000 | 0.000000000 |

Current recommended review copy:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260724_regular05_startup_black_fix\20260724_regular05_startup_black_fix_source_old_const90_constfull_grid_30fps.mp4
```

## Historical Patcher Behavior

Runtime modes:

```text
identity:
  identity VPI matrix

translate:
  source_to_dest translation from VPI_CUDA_OWNED_DX / DY

matrix:
  source_to_dest matrices from VPI_MATRIX_CSV
```

Persistent objects:

```text
CUDA-owned Y/UV input allocations
CUDA-owned Y/UV output allocations
VPI input/output wrappers
VPI CUDA stream
```

Per-frame operations:

```text
input NvBufSurfTransform
EGL register/map
sequential copy-in
VPI PerspectiveWarp + sync
sequential copy-out
EGL unregister/unmap
output NvBufSurfTransform
```

Logs separate:

```text
matrix fallback and frame-index mismatch
EGL registration
copy-in
VPI warp
copy-out
EGL unregister
input/output NvBufSurfTransform
total device stage
```

## Execution Record

The bridge patcher has been removed after negative closeout. Do not recreate the
failed implementation from this report. The tested Jetson samples were generated
under:

```text
/home/nvidia/orin-nx-project/_mmapi_work/jetson_multimedia_api/samples/99_vpi_cuda_owned_bridge_20260724_*
```

Run order used before closeout:

```text
1. identity, short run and extracted-frame review
2. identity, full 180-frame run
3. translate dx=8, only after identity passes
4. spatial-coherence verification against an ideal translate reference
5. resid_r15_s07 matrix replay, only after translate passes
6. side-by-side review against the accepted EGLImage output
7. interleaved five-run timing against the accepted EGLImage path after bridge rejection
```

Historical runtime environment:

```bash
VPI_CUDA_OWNED_MODE=identity

VPI_CUDA_OWNED_MODE=translate
VPI_CUDA_OWNED_DX=8
VPI_CUDA_OWNED_DY=0

VPI_CUDA_OWNED_MODE=matrix
VPI_MATRIX_CSV=<absolute resid_r15_s07.csv path>
```

The binary still uses the existing positional `multivideo_transcode` command
shape:

```text
multivideo_transcode num_files 1 <input.h264> H264 <output.h264> H264
```

## Acceptance Gates

Correctness:

```text
identity rc=0 and 180 readable frames
no green output, tearing, unrelated content, or color corruption
identity black-border p95 < 1%
identity source-vs-output center MAE <= 6
translate is coherent and passes the ideal-reference gate
matrix fallback_count=0
matrix frame_index_mismatch_count=0
resid output passes manual visual veto
```

Performance:

```text
same Regular05 source
same resid_r15_s07 matrix
same timing scope
interleaved runs
at least five successful runs per path
new total stage running average at least 10% lower than accepted EGLImage path
no visual regression
```

If the route does not meet the 10% total-stage threshold, it remains a
correctness or memory-model diagnostic rather than an accepted optimization.

## Claim Boundary

Allowed now:

```text
A new CUDA-owned VPI bridge was implemented and tested on Jetson.
Identity is safe, but non-identity bridge output is rejected.
The accepted fallback path remains VPI-managed EGLImage / stream-only reuse /
NvBuffer pair, with low-single-digit same-input stage and wall-time gains.
```

Forbidden:

```text
claiming the CUDA-owned bridge solves non-identity device-stage warp
claiming the CUDA-owned bridge preserves resid_r15_s07 quality
claiming large acceleration from this loop
full real-time EIS
zero-copy
full-pipeline acceleration
```
