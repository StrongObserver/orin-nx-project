# Final Benchmark Table

This table is the compact evidence package for the current stage. It keeps
quality, module acceleration, device-side dataflow, and profiling claims
separate.

## Summary

| Lane | Frozen Scope | Best Current Evidence | Claim Boundary |
|---|---|---|---|
| Regular quality | `nus_regular_gate_v1`, human-reviewed Regular clips | Regular performance baseline is 5/5 objective pass and accepted by human review | In-domain Regular gate only |
| Stabilization-strength recovery | Regular gate device matrices | `resid_r15_s07` accepted by human review; Regular05 residual translation mean `1.033` | Not all-scene EIS quality |
| CPU performance | Regular05 640x360, 180 frames | estimate time `8.568 ms -> 3.022 ms`; wall time `8.473 s -> 7.565 s` | CPU/OpenCV baseline optimization, not hardware acceleration |
| VPI module acceleration | High-resolution PerspectiveWarp | 4K `48.995 ms -> 20.514 ms`; `1.682 -> 4.385 FPS/W` | Module-level warp-heavy evidence |
| VPI C++ Remap | Standalone BGR8 identity/wave maps | CUDA Remap is `2.5x-3.4x` faster than OpenCV CPU; NV12_ER CPU/CUDA works | Module/operator evidence, not full EIS acceleration |
| Remap-MMAPI diagnostic | 640x368 padded H264 through MMAPI/VPI/NVENC scratch path | Remap identity/wave both `rc=0`; stage avg about `10.52-10.57 ms` | Device-stage operator integration evidence, not Regular EIS quality |
| Remap native-size pad/crop | Native 640x360 main chain with 640x368 VPI scratch | identity and wave_safe both `rc=0`; output remains 640x360 and readable | Size/layout diagnostic; not EIS quality or full-pipeline acceleration |
| Remap NvBuffer wrapper | Native 640x360 main chain, 640x368 pitch-linear NV12_ER scratch | identity/wave_safe `rc=0`, p95 black border `0`, stage avg improves about `3-6%` vs EGLImage baseline in diagnostic timing | Small diagnostic dataflow gain; not zero-copy or quality improvement |
| Dynamic Remap payload | 640x368 standalone and MMAPI pad/crop diagnostics | dynamic payload rebuild works; MMAPI stage avg about `13.14-13.16 ms` | Viability and cost boundary; not quality or acceleration claim |
| CUDA dynamic warp | Standalone 640x368 affine warp kernel | RGBA dynamic `0.194 ms`; Y8 dynamic `0.138 ms` | Standalone execution evidence; not MMAPI integration or quality claim |
| Local-warp quality bridge | Parallax10 static local correction prototype | No residual improvement; baseline `global_residual_p95_avg=2.196`, best attempted local corrections stayed about `2.199-2.216` | Negative diagnostic result; static local offset is not enough |
| Python dataflow boundary | GStreamer appsink/appsrc | appsink readback `7.93 ms/frame`; appsrc encode pass-through `15.81 ms/frame` | Explains why Python-in-loop is not the next acceleration path |
| C++ device path | MMAPI/VPI/NVENC Regular05 stage | Accepted EGLImage wrapper path; stage around `7.5-10.5 ms/frame` depending probe/capture | Device-stage evidence, not full real-time EIS |
| NvBuffer pair follow-up | Same Regular05 source, same `resid_r15_s07` matrix | stage frame100 `7.535 -> 7.230 ms`; running avg `9.589 -> 9.401 ms` | Small quality-preserving dataflow gain, not zero-copy |
| Nsight/NVTX attribution | Accepted EGLImage and NvBuffer pair samples | `VPI:Perspective Warp` about `0.76-0.81 ms`; wrap+submit+sync about `10 ms` under capture | Bottleneck attribution; P6/P7 scheduler work not triggered |
| Stream-only reuse lifecycle | Same Regular05 source, same `resid_r15_s07` matrix | 10-run repeat: wall mean `1.947 -> 1.844 s`, stage avg `10.336 -> 9.680 ms` | Small accepted lifecycle optimization, not image-wrapper reuse |

## Regular Baselines

| Baseline | Config | Evidence | Result |
|---|---|---|---|
| Quality-safe baseline | `lp_rigid_strength080_dynzoom106`, `estimate_scale=1.0`, `feature_grid_size=12` | Jetson Regular05 same-input run | `avg_estimate_ms=8.568`, `avg_warp_ms=7.936`, `wall=8.473 s`, rollback `0` |
| Regular performance baseline | `lp_rigid_strength080_dynzoom106`, `estimate_scale=0.5`, `feature_grid_size=16` | Five NUS Regular clips | 5/5 objective pass and human accepted |

Regular performance gain on `regular_gate05_regular_6`:

| Metric | Quality-Safe | Performance Baseline | Change |
|---|---:|---:|---:|
| `avg_estimate_ms` | 8.568 | 3.022 | about 65% lower |
| `total_wall_time_s` | 8.473 | 7.565 | about 11% lower |

## Quality Recovery

`resid_r15_s07` is the accepted Regular-gate stabilization-strength recovery
result. It supersedes `safe103_crop98`, BQP, and `spike_mid` for current
stabilization-strength comparisons.

| Candidate | Regular05 Residual Translation Mean | Decision |
|---|---:|---|
| `safe103_crop98` | 2.103 | strong prior, superseded |
| `bqp_w90_s15` | 3.915 | rejected as too weak |
| `spike_mid` | 2.788 | rejected as insufficient |
| `resid_r15_s07` | 1.033 | accepted |

## VPI And Power Evidence

4K PerspectiveWarp stable workload, 600 frames, INA3221 `VDD_IN` board-input
power:

| Path | Avg ms | FPS | VDD_IN Avg | FPS/W | Claim |
|---|---:|---:|---:|---:|---|
| OpenCV CPU | 48.995 | 20.410 | 12.136 W | 1.682 | CPU module baseline |
| VPI CUDA | 20.514 | 48.747 | 11.118 W | 4.385 | module acceleration |

This supports a high-resolution module claim only. It does not prove full EIS
pipeline acceleration.

## Device-Side Dataflow

Accepted C++ path:

```text
H264 input
-> MMAPI/NVDEC block-linear NV12 main chain
-> NvBufSurfTransform to pitch-linear NV12_ER scratch
-> VPI CUDA PerspectiveWarp
-> NvBufSurfTransform back to block-linear NV12
-> NVENC
```

Submit/sync probe, Regular05 frame 100:

| Stage | Time |
|---|---:|
| input transform | 0.914 ms |
| wrapper create | 3.289 ms |
| VPI submit | 0.019 ms |
| VPI sync | 1.513 ms |
| output transform | 0.943 ms |
| total stage | 7.798 ms |

Interpretation: the bottleneck is around dataflow, wrapper lifecycle, sync, and
transform cost. The VPI submit call itself is not the bottleneck.

## VPI C++ Remap

The earlier Python `Image.remap` path aborted in the native binding. The C++
probe uses `vpiCreateRemap`, `vpiSubmitRemap`, and `VPIWarpMap`.

| Mode | Resolution | OpenCV CPU ms | VPI CPU ms | VPI CUDA ms | CUDA Speedup |
|---|---:|---:|---:|---:|---:|
| identity | 640x368 | 1.817510 | 0.988688 | 0.610031 | 2.979x |
| identity | 1920x1088 | 8.096360 | 7.988430 | 2.410080 | 3.359x |
| identity | 3840x2160 | 31.127200 | 31.452200 | 9.423580 | 3.303x |
| wave | 640x368 | 1.772240 | 0.975930 | 0.704285 | 2.516x |
| wave | 1920x1088 | 8.105170 | 7.968380 | 2.978840 | 2.721x |
| wave | 3840x2160 | 31.064200 | 32.921700 | 9.516820 | 3.264x |

NV12_ER relevance:

| Mode | VPI CPU ms | VPI CUDA ms | Meaning |
|---|---:|---:|---|
| identity 640x368 | 0.753977 | 0.213389 | Remap works on current scratch-like format |
| wave 640x368 | 0.760223 | 0.135011 | local map works on current scratch-like format |

This is a positive module/operator result. It does not prove full-pipeline EIS
acceleration or MMAPI integration.

## Remap-MMAPI Diagnostic Integration

Remap was inserted into a diagnostic MMAPI/VPI/NVENC sample by replacing
`vpiSubmitPerspectiveWarp` with `vpiSubmitRemap` on the pitch-linear NV12_ER
scratch stage.

640x360 failed first because WarpGrid aligned the height to 368 and Remap
requires output size to match the warp map. A 640x368 padded diagnostic source
then ran successfully.

| Mode | rc | Remap Frame100 | Remap Avg | Stage Frame100 | Stage Avg |
|---|---:|---:|---:|---:|---:|
| identity | 0 | 1.584280 ms | 1.589380 ms | 8.529760 ms | 10.524300 ms |
| wave | 0 | 1.630130 ms | 1.591480 ms | 8.323730 ms | 10.573700 ms |

This proves diagnostic Remap insertion is feasible under WarpGrid-compatible
dimensions. It does not prove Regular EIS quality, mesh/local-warp quality, or
full-pipeline acceleration.

## Remap Native-Size Pad/Crop

The follow-up native-size probe keeps the encoder-facing main chain at 640x360
and pads only the pitch-linear VPI scratch stage to the WarpGrid-compatible
640x368 size.

| Mode | rc | Remap Frame100 | Remap Avg | Stage Frame100 | Stage Avg | Black Border P95 |
|---|---:|---:|---:|---:|---:|---:|
| identity | 0 | 1.594870 ms | 1.614520 ms | 8.196200 ms | 11.039800 ms | 0.000000000 |
| wave_safe | 0 | 1.575290 ms | 1.652440 ms | 7.269890 ms | 10.751300 ms | 0.000000000 |

This closes the Remap size/layout diagnostic boundary: native 640x360 input can
use a padded 640x368 Remap scratch stage and crop/transform back to 640x360
before NVENC. It is still diagnostic operator/dataflow evidence, not EIS quality
or full-pipeline acceleration.

Follow-up lifecycle/dataflow V2:

| Mode | EGLImage Stage Avg | Stream-Only Stage Avg | NvBuffer Stage Avg | Decision |
|---|---:|---:|---:|---|
| identity | 11.039800 ms | 11.704200 ms | 10.433000 ms | NvBuffer small gain; stream-only regressed |
| wave_safe | 10.751300 ms | 11.785700 ms | 10.387900 ms | NvBuffer small gain; stream-only regressed |

The useful result is that Remap pad/crop can also use
`VPI_IMAGE_BUFFER_NVBUFFER` wrappers on a format-matched pitch-linear NV12_ER
scratch pair. This remains a diagnostic dataflow result, not a zero-copy or EIS
quality claim.

## Dynamic Remap Payload

Dynamic per-frame Remap payload rebuild was measured as the next boundary after
static Remap integration.

Standalone 640x368 CUDA probe:

| Format | Static Payload Total | Dynamic Rebuild Total | Main Added Cost |
|---|---:|---:|---|
| BGR8 | 0.839870 ms | 2.250150 ms | payload create 1.544170 ms |
| NV12_ER | 0.181523 ms | 2.913010 ms | payload create 2.155590 ms |

MMAPI native-size pad/crop diagnostic:

| Path | rc | Payload Create Frame100 | Remap Avg | Stage Avg | Black P95 |
|---|---:|---:|---:|---:|---:|
| EGLImage dynamic Remap | 0 | 1.761130 ms | 1.586130 ms | 13.139300 ms | 0.002375217 |
| NvBuffer dynamic Remap | 0 | 1.878210 ms | 1.550540 ms | 13.159600 ms | 0.002375217 |

Dynamic Remap works, but per-frame payload rebuild is material and dominates the
added cost. This is a future mesh/local-warp cost boundary, not a quality win.

## CUDA Dynamic Warp

CUDA dynamic affine warp was measured as an alternative to VPI dynamic Remap
payload rebuild.

| Route | Comparable Mode | Total Avg |
|---|---|---:|
| CUDA RGBA dynamic affine | dynamic matrix update + kernel | 0.194142 ms |
| VPI BGR8 dynamic Remap | per-frame WarpMap/payload rebuild | 2.250150 ms |
| CUDA Y8 dynamic affine | dynamic matrix update + kernel | 0.138282 ms |
| VPI NV12_ER dynamic Remap | per-frame WarpMap/payload rebuild | 2.913010 ms |

CUDA is much faster in this standalone affine diagnostic, but it is not yet an
accepted MMAPI path. Direct MMAPI CUDA scratch writeback needs a separate safety
verifier because earlier low-level CUDA/pitch-wrapper routes caused tearing.

## Local-Warp Quality Bridge

The next diagnostic question was whether a constrained local Remap correction can
improve a real parallax/global-warp boundary sample.

Primary sample:

```text
results/nus_parallax_challenge_v1_curated/raw_clips/parallax10_parallax_13.mp4
```

Result:

| Case | global_residual_p95_avg | cell_mean_max_avg | cell_mean_range_avg | Decision |
|---|---:|---:|---:|---|
| baseline | 2.196383 | 1.974301 | 1.446885 | reference |
| gx0 gy3 strength 1.0 | 2.216424 | 2.002721 | 1.463025 | worse |
| gx0 gy3 strength 0.5 | 2.198613 | 1.986436 | 1.449056 | neutral/slightly worse |
| gx3 gy3 strength 0.5 | 2.200762 | 1.996831 | 1.459487 | worse |
| gx3 gy0 strength 0.5 | 2.205726 | 1.987898 | 1.448646 | worse/neutral |

Conclusion:

```text
The Remap operator is useful, but a static single-cell correction is not enough
to solve a real parallax/local residual. A dynamic mesh/depth/RS-aware model
would be needed for a serious quality route.
```

## NvBuffer Pair

Same Regular05 source, same `resid_r15_s07` matrix, same crop/postprocess
boundary:

| Metric | EGLImage | NvBuffer Pair | Improvement |
|---|---:|---:|---:|
| VPI warp avg | 1.518510 ms | 1.491370 ms | 1.79% |
| stage frame100 | 7.535330 ms | 7.230350 ms | 4.05% |
| stage running avg | 9.588980 ms | 9.401090 ms | 1.96% |

Five Regular NvBuffer pair runs with `resid_r15_s07` all returned `rc=0` and
`fallback=0`. Regular01 remains visual-conditional because the gray-threshold
black-border metric is sensitive to dark edges.

## Nsight/NVTX

Key exported result:

| Range / API | EGLImage Avg | NvBuffer Pair Avg | Meaning |
|---|---:|---:|---|
| `vpi_submit_perspective_warp` | 0.0220 ms | 0.0241 ms | submit call is negligible |
| `VPI:Perspective Warp` | 0.7630 ms | 0.8051 ms | warp is not the dominant stage |
| `vpi_stream_sync` | 2.1403 ms | 2.2007 ms | sync is material |
| wrap + submit + sync range | 10.0225 ms | 10.2681 ms | dominant profiled stage |
| input transform | 0.8702 ms | 0.9008 ms | transform sandwich remains visible |
| output transform | 0.9286 ms | 0.9664 ms | transform sandwich remains visible |
| `cudaFree` | 1.3408 ms | 1.1361 ms | lifecycle/free cost is material |

Decision: P6/P7 queue-depth or double-buffering work is not triggered. The
timeline supports attribution, not a broad scheduler rewrite.

## Stream-Only Reuse Lifecycle Follow-Up

Same Regular05 source, same `resid_r15_s07` matrix, ten alternating runs:

| Path | Runs | rc=0 | Fallback | Wall Mean | Stage100 Mean | Stage Avg Mean | Wrapper Mean |
|---|---:|---:|---:|---:|---:|---:|---:|
| accepted EGLImage | 10 | 10/10 | 0 | 1.946819 s | 7.842519 ms | 10.336381 ms | 5.877429 ms |
| stream-only reuse | 10 | 10/10 | 0 | 1.843571 s | 7.295914 ms | 9.680414 ms | 5.365920 ms |

Benefit:

| Candidate | Wall Mean | Stage100 | Stage Avg | Wrapper | Warp Avg |
|---|---:|---:|---:|---:|---:|
| stream-only reuse | +5.303% | +6.970% | +6.346% | +8.703% | -10.453% |

This promotes stream-only reuse as a small accepted lifecycle optimization
inside the current device-stage boundary. It does not revive EGLImage
image-wrapper reuse and does not justify queue-depth or double-buffering work.

## Evidence Pointers

```text
docs/stage_result_regular_performance_baseline_2026-07-18.md
docs/regular_gate_residual_closed_loop_2026-07-21.md
docs/regular_gate_nvbuffer_pair_resid_2026-07-23.md
docs/nsight_device_stage_profile_result_2026-07-23.md
docs/device_stage_lifecycle_budget_2026-07-23.md
docs/device_stage_lifecycle_perf_result_2026-07-23.md
docs/vpi_remap_cpp_probe_2026-07-23.md
docs/remap_mmapi_integration_probe_2026-07-23.md
docs/remap_native_size_pad_crop_probe_2026-07-23.md
docs/device_stage_lifecycle_dataflow_v2_2026-07-23.md
docs/vpi_dynamic_remap_payload_probe_2026-07-23.md
docs/cuda_dynamic_warp_probe_2026-07-23.md
docs/local_warp_quality_bridge_2026-07-23.md
docs/presentation/hardware_acceleration_boundary.md
results/regular_gate_est0p5_grid16_validation_20260718/
results/vpi_warp_module_rerun_20260722/
results/power_probe_20260722_sudo/
results/regular_gate_nvbuffer_pair_resid_20260723/
results/regular05_eglimage_timing_resid_compare_20260723/
results/nsight_device_stage_profile_20260723/
results/device_stage_lifecycle_perf_20260723/
results/vpi_remap_cpp_probe_20260723/
results/remap_mmapi_integration_probe_20260723/
results/remap_native_size_pad_crop_probe_20260723/
results/device_stage_lifecycle_dataflow_v2_20260723/
results/vpi_dynamic_remap_payload_probe_20260723/
results/cuda_dynamic_warp_probe_20260723/
results/local_warp_quality_bridge_20260723/
```
