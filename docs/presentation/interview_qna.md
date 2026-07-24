# Interview Q&A

## Q: What is the project?

A Jetson Orin NX heterogeneous video compute and device-side dataflow project.
I use EIS as a representative real-time vision workload: first keep quality
measurable with CPU baselines and gates, then profile where VPI/CUDA/MMAPI/NVENC
compute, memory format, synchronization, and encode/decode dataflow actually
help.

## Q: What is your current best result?

For Regular clips, the current performance baseline is:

```text
lp_rigid_strength080_dynzoom106
estimate_scale=0.5
feature_grid_size=16
```

It passes objective gates on all five Regular clips and was accepted by human
review.

For the later device-side Regular-gate recovery loop, `resid_r15_s07` is the
accepted result. It was visibly stronger than BQP/spike_mid and did not show hard
pose snaps or visible black borders in review.

## Q: What improved after optimization?

On `regular_gate05_regular_6`:

```text
estimate stage: 8.568 ms -> 3.022 ms
total wall time: 8.473 s -> 7.565 s
```

The speedup came from lower-resolution motion estimation plus a denser feature
grid to recover stability.

## Q: Why is this more than a normal EIS demo?

A normal EIS demo usually stops at before/after video. This project keeps the
video result as the workload and then builds a systems loop around it:

```text
quality gates
CPU timing
VPI module benchmark
GStreamer/NVMM boundary
MMAPI/VPI/NVENC device stage
Nsight/NVTX bottleneck attribution
small lifecycle optimization
```

That is why the main claim is heterogeneous video compute and device-side
dataflow optimization, not "I made the best stabilizer."

## Q: Why not continue improving the stabilization algorithm?

Because the current Regular-gate quality issue is already closed around
`resid_r15_s07`, and more global affine/rigid sweeps would mostly repeat a
closed loop.

The project has more value when it explains:

```text
where quality is accepted
where global-warp EIS breaks
where VPI helps
where VPI does not help
where device-stage lifecycle cost comes from
```

If the objective changes to product-grade stabilization, then the next algorithm
class would likely be mesh, rolling-shutter-aware, or gyro-assisted work. That is
not the current resume-facing claim.

## Q: Why keep two baselines?

Because they serve different claims:

```text
quality-safe baseline:
  estimate_scale=1.0, grid12

Regular performance baseline:
  estimate_scale=0.5, grid16
```

The quality-safe baseline is conservative. The performance baseline is accepted
for Regular-gate performance.

## Q: Did VPI accelerate the EIS pipeline?

Not the current full pipeline. A simple VPI backend swap was slower at 640x360.

But VPI CUDA did accelerate high-resolution warp-heavy modules. Current
checkpoint numbers:

```text
1080p: 36.926 ms -> 18.426 ms, 2.00x
1440p: 29.045 ms -> 15.778 ms, 1.84x
4K:    69.742 ms -> 27.617 ms, 2.53x
```

So the lesson is placement and dataflow matter.

On a 4K 600-frame stable workload with INA3221 board-input power:

```text
OpenCV CPU: 48.995 ms, 20.410 FPS, 12.136 W, 1.682 FPS/W
VPI CUDA:   20.514 ms, 48.747 FPS, 11.118 W, 4.385 FPS/W
```

## Q: Why is it still a hardware project if full-pipeline VPI was slower?

Because a negative full-pipeline result prevented a false claim, and the project
then found the correct level for acceleration:

```text
small 640x360 Python pipeline:
  VPI backend swap is slower

high-resolution PerspectiveWarp module:
  VPI CUDA is faster and better in FPS/W

C++ device stage:
  profiling shows wrapper/sync/transform/lifecycle dominates
```

The engineering value is knowing where to use hardware acceleration and where
not to.

## Q: What are the remaining limitations?

- Global warp cannot solve all local/parallax/rolling-shutter-like artifacts.
- Running and other challenge sets are not claimed as solved.
- GStreamer/NVMM dataflow is only probed, not integrated into the EIS pipeline.
- VPI module speedup is not the same as full-pipeline speedup.
- VPI PyrLK and Remap are not current replacement wins: PyrLK can run but is not
  better than OpenCV in the current same-keypoint probe, and Python Remap hits a
  native binding abort.

## Q: What would you do next?

I would not start another baseline tuning loop by default. The current stage is
sealed for presentation: Regular quality is accepted, NvBuffer pair is measured,
and NVTX/Nsight profiling has already localized the device-stage cost.

If more engineering time is available, I would open one narrow new contract
around wrapper/register/free/sync lifecycle cost, not a broad rewrite:

```text
current accepted path:
  block-linear main chain
  -> pitch-linear NV12_ER scratch
  -> VPI CUDA warp through EGLImage wrappers
  -> block-linear NV12 encode

measured bottlenecks:
  wrapper lifecycle
  vpiStreamSync
  NvBufSurfTransform sandwich
  CUDA/EGL register, unregister, free, and stream synchronize lifecycle cost
```

I would not claim zero-copy until a format-stable path removes or reduces those
costs without reintroducing tearing, green output, or format mismatch failures.
P6/P7 queue-depth or double-buffering work is not currently triggered because
the Nsight result does not show a large hidden scheduler win.

In the follow-up loop, the narrow stream-only reuse candidate was promoted as a
small device-stage lifecycle optimization. It keeps the safe rule: reuse the VPI
stream, but recreate EGLImage image wrappers per frame.

If I had more time, I would choose one scoped route instead of broad exploration:

```text
1. Custom CUDA affine-kernel MMAPI diagnostic, because CUDA scratch interop now
   passes the identity-first safety verifier.
2. Longer fixed-mode perf/watt run, if the goal is stronger power evidence.
3. Very narrow wrapper/register/free/sync probe, if the goal is dataflow cost.
```

I would not restart quality tuning unless the objective changes.

## Q: Why not continue tuning Regular05?

Because the Regular performance baseline already passes the current objective
gate and was accepted by human review. The remaining tail shake is better treated
as a global-warp model boundary than as a reason to keep sweeping parameters.

## Q: Why not claim Running is solved?

Running is a challenge set for this project. It is useful for explaining limits
of pure visual global-warp EIS, not for the headline success metric. Promoting
Running would require a different algorithm class or degradation policy.

## Q: What did the challenge set prove?

It proved the operating envelope. Regular clips are the in-domain success case.
Running, QuickRotation, Parallax, and Crowd expose where the global-warp model
breaks: FOV pressure, fast rotation, foreground/background depth variation, and
dynamic foreground contamination.

## Q: Why is the VPI result still useful if it did not speed up the full pipeline?

It shows engineering judgment. The full pipeline result prevented a false claim.
The high-resolution module benchmark still proves that VPI CUDA is useful when
the warp workload is large enough. The next question is dataflow placement.

The later power probe makes this stronger: on the 4K warp-heavy workload, VPI
CUDA was both faster and better in FPS/W.

## Q: Why stop Python GStreamer integration?

Because the dataflow boundary is already expensive before EIS is added:

```text
appsink readback: about 7.93 ms/frame
appsink -> appsrc -> encode pass-through: about 15.81 ms/frame
```

That is not a good path for accelerating the current CPU EIS pipeline. If this
route continues, it should move toward C++/CUDA or device-side processing.

## Q: What did the MMAPI/VPI/NVENC device-side work prove?

It proved a non-Python device-side warp and encode path:

```text
H264 input
-> MMAPI decode / NvBufSurface
-> pitch-linear NV12_ER scratch
-> VPI CUDA warp
-> block-linear NV12
-> NVENC
```

The current version uses offline CPU-generated matrices. Forward matrices caused
large black borders, while inverse matrices produced normal sampled black-border
sanity on the outdoor-car smoke source. That result is now historical dataflow
evidence, not the Regular05 EIS-quality convention.

I then tested two 120-row matrix candidates. Only composing CPU zoom/crop
geometry into the matrix improved parity:

```text
old inverse mean_abs_center_avg vs CPU: 44.739667
aligned identity-first:                46.884302
post geometry:                         30.688605
post geometry + first-frame identity:  30.241568
Catmull-Rom interpolation:             30.902334
```

Catmull-Rom was slower and worse than linear, so the current best device
candidate for outdoor-car smoke remains linear interpolation plus post-geometry
with first-frame identity.

For Regular05 EIS-quality replay, the convention changed:

```text
inverse convention:
  black_border_p95 = 0.281428602
  CPU-vs-device mean_abs_center_avg = 35.618840

source_to_dest convention:
  black_border_p95 = 0.000972005
  CPU-vs-device mean_abs_center_avg = 4.512432
```

So Regular05 work must use source_to_dest.

## Q: Is the device-side result a real-time EIS pipeline?

No. It is an offline matrix-driven device warp/encode milestone. Motion
estimation is not running online inside the MMAPI path yet, and the device path
does not yet reproduce CPU post-processing such as crop, dynamic zoom, Lanczos
resize, and sharpen.

## Q: Where is the C++ dataflow bottleneck now?

The accepted C++ EGLImage-wrapper path was decomposed with a submit/sync probe.
At frame 100 on Regular05:

```text
total stage:          7.798 ms
wrapper lifecycle:    3.816 ms
VPI submit + sync:    1.532 ms
input/output xforms:  1.857 ms
vpiSubmit alone:      0.019 ms
```

So the bottleneck is not the PerspectiveWarp kernel or the submit call. It is
wrapper lifecycle, sync, and the transform sandwich around the VPI call.

## Q: Did you implement zero-copy?

No. The project has a measured non-zero-copy boundary:

```text
block-linear main chain
pitch-linear NV12_ER VPI scratch
NvBufSurfTransform sandwich
per-frame EGLImage wrappers
```

Several shortcuts were rejected: pitch-linear main encode produced green output,
block-linear VPI scratch pairs were rejected by VPI, direct mismatched NvBuffer
input failed, and EGLImage image-wrapper reuse caused tearing. The honest claim
is that the dataflow cost is measured and localized, not that zero-copy is done.

## Q: What did the NvBuffer pair follow-up improve?

It improved the device-side dataflow path without changing the quality anchor.
The important correction was to compare against `resid_r15_s07`, not the older
inclusion or safe103 matrices.

On all five Regular clips, the format-matched NvBuffer pair path ran with
`rc=0` and `fallback=0`. On same-source Regular05, it aligned with the EGLImage
result in time and geometry, preserved the accepted quality anchor, and reduced
the measured device stage slightly:

```text
stage frame100:   7.535 ms -> 7.230 ms
stage running avg: 9.589 ms -> 9.401 ms
```

So the claim is quality-preserving dataflow improvement. It is not zero-copy,
and it is not full-pipeline acceleration.

## Q: What did stream-only reuse improve?

It improved lifecycle overhead around the accepted EGLImage path without
changing quality semantics.

```text
accepted EGLImage, 10-run same-source repeat:
  wall mean = 1.946819 s
  stage running avg = 10.336381 ms
  wrapper mean = 5.877429 ms

stream-only reuse:
  wall mean = 1.843571 s
  stage running avg = 9.680414 ms
  wrapper mean = 5.365920 ms
```

The measured benefit was:

```text
wall mean: +5.303%
stage avg: +6.346%
wrapper:   +8.703%
```

The important boundary is that stream-only reuse is not image-wrapper reuse.
Image-wrapper reuse was rejected because it caused tearing or failures.
Stream-only reuse is a safe lifecycle improvement because it still recreates the
image wrappers per frame.

## Q: Did stream-only reuse improve tail latency?

Not conclusively.

The 10-run repeat supports a small mean improvement and clean health gates:

```text
rc=0 for all runs
fallback=0 for all runs
wall mean: 1.946819 s -> 1.843571 s
stage avg mean: 10.336381 ms -> 9.680414 ms
```

But the p95/p99 tail is not better in this small repeat:

```text
EGLImage wall p99: 1.981455 s
stream wall p99:   2.040837 s
EGLImage stage p99: 10.599900 ms
stream stage p99:   10.638100 ms
```

So the honest claim is:

```text
small mean lifecycle gain with clean rc/fallback behavior
```

not:

```text
tail latency solved
30-minute endurance proven
```

The later 50-run repeat made the stability boundary stronger:

```text
accepted EGLImage: 50/50 rc=0, fallback=0, wall p99 1.993936 s
stream-only reuse: 50/50 rc=0, fallback=0, wall p99 2.070096 s
NvBuffer pair:     50/50 rc=0, fallback=0, wall p99 1.994439 s
```

So the final wording is still conservative:

```text
all paths are stable in the 50-run repeat; stream-only has a small mean gain,
but no p99 win is proven.
```

## Q: Why not implement queue depth or double buffering now?

Because the current evidence does not show a large removable idle gap. The
largest measured costs are wrapper, sync, transform, and CUDA/EGL lifecycle
costs. Stream-only reuse already captures the safe part of lifecycle reuse and
gives a modest gain:

```text
wall mean: +5.303%
stage avg: +6.346%
```

That is worth recording, but it is not enough to justify a broad scheduler
rewrite under the current project goal.

## Q: Why not use VPI PyrLK for motion estimation?

I tested it because it matches the original project design. It can run on CPU
and CUDA in the Python binding, but in the current same-keypoint probe it is not
a good replacement:

```text
OpenCV PyrLK: 1.378 ms, avg valid points 111
VPI CUDA:     1.672 ms, avg valid points 37
```

That means the first useful VPI replacement is PerspectiveWarp, not PyrLK.

## Q: What happened with VPI Remap?

The Python Remap path is not stable on this setup. The minimal
WarpMap/Image.remap probe aborts in the native binding with
`double free or corruption`.

That did not prove Remap itself was impossible. I then tested the C++ path using
`vpiCreateRemap`, `vpiSubmitRemap`, and `VPIWarpMap`.

Result:

```text
C++ Remap CPU/CUDA: pass
VIC with BGR8: unsupported in this probe
NV12_ER CPU/CUDA: pass
```

CUDA Remap was faster than OpenCV CPU on tested module maps:

```text
identity 640x368:  1.817510 ms -> 0.610031 ms, 2.979x
identity 1920x1088: 8.096360 ms -> 2.410080 ms, 3.359x
identity 3840x2160: 31.127200 ms -> 9.423580 ms, 3.303x
wave 3840x2160:     31.064200 ms -> 9.516820 ms, 3.264x
```

The correct claim is module/operator-level C++ Remap acceleration. It is not
yet MMAPI integration and not full EIS pipeline acceleration.

## Q: What did CUDA/MMAPI interop prove?

After the standalone CUDA dynamic warp probe, I ran a separate MMAPI scratch
interop safety verifier instead of immediately claiming CUDA acceleration.

The verifier keeps the existing device-stage boundary:

```text
block-linear NV12 main chain
-> pitch-linear NV12_ER scratch
-> CUDA driver API EGL interop
-> block-linear NV12 main chain
-> NVENC
```

Result:

```text
identity:       rc=0, readable 640x360, black-border p95=0
marker:         rc=0, readable 640x360, black-border p95=0
dynamic_marker: rc=0, readable 640x360, black-border p95=0
```

The first large-plane `shift_dx8` / `dynamic_shift` attempt returned `rc=0`, but
human review rejected it because the review video showed severe tearing and
distortion. The corrected marker modes copy the full frame first and then write
only a small Y-plane ROI marker, so they verify CUDA write activity without
large-plane tearing. The important safety result is that identity passes without
unreadable output, green output, or black-border regression.

Correct claim:

```text
CUDA can safely read/write the current MMAPI scratch boundary at diagnostic
level. A custom CUDA affine kernel or acceleration result still needs its own
contract and timing comparison.
```

Forbidden claim:

```text
CUDA has accelerated the full MMAPI EIS pipeline.
```

## Q: Did the custom CUDA affine kernel work inside MMAPI?

Not as an accepted warp path.

The identity CUDA kernel path did work:

```text
rc=0
readable 640x360 output
black-border p95 = 0
source-vs-identity mean_abs_center_avg = 2.772184
```

But non-identity random sampling failed visually:

```text
translate / affine kernels over the current EGL-mapped pitch-linear NV12_ER
scratch produced severe tearing or unrelated visual corruption.
```

I tried focused fixes before closing it:

```text
temporary cudaMallocPitch buffers plus copy-back
matrix as kernel arguments instead of constant memory
Y-only and integer translate diagnostics
extra cuCtxSynchronize points
NvBufSurfaceSyncForDevice on the output scratch
```

The sync attempt even segfaulted, which matches the earlier project evidence
that this sync route is not a reliable fix here.

Correct conclusion:

```text
Standalone CUDA is promising, and CUDA marker writes into MMAPI scratch are
safe, but the current EGL-mapped NV12_ER scratch route is not an accepted
full-frame CUDA affine warp path. The next route needs a different surface
ownership model or official/internal guidance.
```

## Q: What did the double-surface debug prove?

It split the CUDA/MMAPI problem into smaller tests:

```text
Test0 VIC round-trip:
  decode/transform/encode path is readable, no tearing

Test1 dual-surface CUDA full-frame copy:
  rc=0, readable, black-border p95=0, source-vs-output mean_abs_center_avg=2.805

Test2 dual-surface CUDA integer translate:
  rc=0 but visual tearing/distortion remains
```

So the blocker is now narrower:

```text
The basic transforms, encoder path, and full-frame CUDA copy are clean.
The failure appears when the CUDA kernel does spatial random sampling / remap
over the current EGL-mapped NV12_ER scratch surface.
```

That means the next route should change the memory/surface ownership model, not
keep patching the same EGL random-write path.

## Q: What happened after the VPI CUDA-owned bridge failed?

I closed it as negative evidence instead of packaging it as an optimization.

What passed:

```text
identity through the bridge
standalone CUDA-owned RGBA VPI PerspectiveWarp
bridge-internal RGBA translate diagnostic
```

What failed:

```text
non-identity bridge output after returning to NV12/NVENC
```

The useful conclusion is:

```text
VPI CUDA-owned warp can be correct in isolation, but the current bridge does not
have a visually correct return path to NV12/NVENC for non-identity output.
```

The next route is not "try the same bridge harder." It is:

```text
start from an official-sample-shaped CUDA-to-encoder verifier
identity / marker first
then integer translate
then affine or matrix replay only if translate is clean
```

If the official samples do not settle the NvBufSurface/EGLImage/CUDA/NVENC
ownership and sync order, I would ask internal AI or an experienced Jetson
engineer for the exact memory-ownership sequence before coding another broad
patch.

The next verifier did use the official sample shape. Starting from
`03_video_cuda_enc`, the project verified CUDA processing before NVENC:

```text
marker mode:
  rc=0, 180 readable frames, black-border p95=0

translate dx=8:
  rc=0, spatial coherence pass
  band shift spread p95 ~= 0.088 px
  expected shift error p95 ~= 0.085 px

affine dx=8:
  rc=0, spatial coherence pass
  band shift spread p95 ~= 0.084 px
  expected shift error p95 ~= 0.082 px
```

This proves CUDA-to-encoder ownership is viable in the official encode sample
shape. It still does not prove the rejected transcode scratch path is fixed, and
it is not a full-pipeline acceleration claim.

## Q: What was the Regular05 startup black fix?

Human review found a brief left-edge black exposure in the first seconds of the
accepted-path comparison. The source did not have that issue, and the exposure
appeared across accepted EGLImage, stream-only reuse, and NvBuffer pair outputs.
That pointed to the startup portion of the matrix sequence.

The final objective candidate is `constant FOV full`:

```text
left80 max first 180: 0
left80 mean first 180: 0
black-border p95: 0
black-border max: 0
```

I still do not mark it accepted automatically because it uses a full-clip
constant extra FOV-safe scale. That is a visual trade-off: no measured black
edge, but potentially more field-of-view loss. It needs human acceptance before
becoming a final quality/display decision.

After review, the user accepted `const_full` for Regular05. `const90` remains
diagnostic because it still has zooming.

The same constant-FOV-full rule was then extended to five Regular clips through
the accepted stream-only reuse consumer:

```text
5/5 rc=0
5/5 fallback=0
5/5 frame-index mismatch=0
```

Regular01 remains visual-conditional because gray-threshold black-border p95 is
below 1%, but max is slightly above 1% for two frames. The other four clips are
clean under the current black-border checks.

## Q: Is the producer path real-time now?

No.

The producer/consumer handoff is healthy:

```text
fallback=0
frame-index mismatch=0
handoff after startup is tens of microseconds
```

The stride5 scheduling optimization is real:

```text
producer-only delay90:
  68.5 s -> 15.7 s for 180 frames

concurrent live stride5:
  17.5 s for 180 frames
```

But this is still not full real-time EIS. The remaining issue is producer
latency and the quality trade-off between offline LP quality and causal or
bounded-delay smoothing. I would present it as a latency-quality/scheduling
boundary, not as a finished live product.

The first-row latency audit confirms that FIFO itself is not the bottleneck:

```text
handoff p95: about 39 us
LP solve total: about 12.76 s
mask safety total: about 2.31 s
producer total: about 15.69 s
```

So the next useful producer question is not a consumer rewrite. It is whether
the producer can emit early rows incrementally while preserving the accepted
bounded-delay quality semantics.

## Q: Why do source, identity_pad_crop, and wave_safe_pad_crop not show stabilization?

Because that review video is not a stabilization-quality candidate. It is a
device-stage dataflow diagnostic.

Panel roles:

```text
source:
  original input, no stabilization expected

identity_pad_crop:
  dataflow sanity check
  640x360 main chain -> 640x368 VPI scratch -> identity Remap
  -> crop/transform back to 640x360 -> NVENC

wave_safe_pad_crop:
  operator diagnostic
  proves the Remap map is active and stays inside a safe FOV envelope
```

Expected result:

```text
No stabilization is expected.
The expected pass condition is readable output without black bands, block
tearing, wrong colors, or size/layout corruption.
```

## Q: What did the native-size Remap pad/crop loop actually buy?

It closed a concrete MMAPI/VPI/NVENC integration risk.

The blocker was:

```text
Regular05 source is 640x360.
VPI Remap WarpGrid aligns the height to 368.
Remap requires output image dimensions to match the warp map.
Direct native 640x360 Remap therefore fails.
```

The fix was:

```text
Keep the main decode/encode chain at 640x360.
Pad only the pitch-linear VPI scratch stage to 640x368.
Run VPI Remap at 640x368.
Crop/transform back to 640x360 before NVENC.
```

Measured result:

```text
identity:  rc=0, readable, black-border p95=0
wave_safe: rc=0, readable, black-border p95=0
```

Engineering value:

```text
This does not improve EIS quality by itself.
It proves that future spatial operators such as dynamic mesh/local warp can be
wired into the current native-size MMAPI/VPI/NVENC device path without changing
the encoder-facing video size.
```

Forbidden wording:

```text
Do not say Remap solved stabilization quality.
Do not call it zero-copy.
Do not present it as full-pipeline acceleration.
```

## Q: Did local Remap improve parallax or local-warp EIS quality?

No. I tested that bridge explicitly and it did not improve the chosen parallax
sample.

The primary sample was:

```text
results/nus_parallax_challenge_v1_curated/raw_clips/parallax10_parallax_13.mp4
```

It was a real boundary case:

```text
scene_gate: challenge_degrade
motion_p95: 19.56 px
local/global_p95: 1.30
row_residual_p95: 2.23 px
```

I built a constrained local Remap correction around high-residual grid cells, but
the metrics did not improve:

```text
baseline global_residual_p95_avg: 2.196
gx0 gy3 strength 1.0:             2.216
gx0 gy3 strength 0.5:             2.199
gx3 gy3 strength 0.5:             2.201
gx3 gy0 strength 0.5:             2.206
```

So the useful conclusion is not "local warp solved parallax." The conclusion is:

```text
The Remap operator is available, but quality improvement needs a dynamic spatial
model such as mesh path optimization, depth/foreground separation, rolling-shutter
awareness, or gyro-assisted constraints. A fixed per-cell offset is not enough.
```


## Q: Is the device output equivalent to the CPU stabilized output?

Not yet. A 120-frame local panel comparison of the review video showed:

```text
CPU stabilized vs device inverse:
  mean_abs_center_avg = 37.033757
  p95_abs_center_avg  = 138.416667
```

That is enough to reject a CPU-equivalence claim. The correct claim is that the
device-side warp/encode path works and has a known parity gap.

## Q: Why keep the quality-safe baseline?

The performance baseline is accepted for Regular-gate speedup. The quality-safe
baseline remains useful when a future comparison needs the most conservative
current setting or when a new clip raises visual concerns.

## Evidence To Mention

```text
docs/stage_result_regular_performance_baseline_2026-07-18.md
docs/vpi_warp_module_report_2026-07-18.md
docs/gstreamer_nvmm_latency_plan_2026-07-18.md
docs/device_matrix_warp_demo_2026-07-19.md
results/vpi_warp_module_rerun_20260722/
results/power_probe_20260722_sudo/
results/pyr_lk_opencv_vpi_compare_20260722_v2/
results/regular05_submit_sync_probe_20260722/
results/regular_gate_est0p5_grid16_validation_20260718/regular_gate_validation_summary.md
docs/presentation/final_benchmark_table.md
docs/presentation/dataflow_architecture.md
docs/presentation/claim_boundary.md
docs/nsight_device_stage_profile_result_2026-07-23.md
results/nsight_device_stage_profile_20260723/
docs/device_stage_lifecycle_budget_2026-07-23.md
docs/device_stage_lifecycle_perf_result_2026-07-23.md
results/device_stage_lifecycle_perf_20260723/
```
