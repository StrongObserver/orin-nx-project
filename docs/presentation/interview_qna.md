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

## Q: What are the remaining limitations?

- Global warp cannot solve all local/parallax/rolling-shutter-like artifacts.
- Running and other challenge sets are not claimed as solved.
- GStreamer/NVMM dataflow is only probed, not integrated into the EIS pipeline.
- VPI module speedup is not the same as full-pipeline speedup.
- VPI PyrLK and Remap are not current replacement wins: PyrLK can run but is not
  better than OpenCV in the current same-keypoint probe, and Python Remap hits a
  native binding abort.

## Q: What would you do next?

The next implementation direction is not another baseline tuning loop. The
current frontier is explaining and reducing the device-side dataflow cost:

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
```

I would not claim zero-copy until a format-stable path removes or reduces those
costs without reintroducing tearing, green output, or format mismatch failures.
The highest-value next evidence is an NVTX/Nsight Systems timeline for this
accepted C++ stage.

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

## Q: Why not use VPI PyrLK for motion estimation?

I tested it because it matches the original project design. It can run on CPU
and CUDA in the Python binding, but in the current same-keypoint probe it is not
a good replacement:

```text
OpenCV PyrLK: 1.378 ms, avg valid points 111
VPI CUDA:     1.672 ms, avg valid points 37
```

That means the first useful VPI replacement is PerspectiveWarp, not PyrLK.

## Q: Why not use VPI Remap?

The Python Remap path is not stable on this setup. The minimal WarpMap/Image.remap
probe aborts in the native binding with `double free or corruption`.

That does not prove C++ Remap is impossible. It means the future route should be
a C++/official-sample probe, using `Remap.h` or the VPI fisheye sample as a
reference, instead of continuing to force the Python binding.

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
```
