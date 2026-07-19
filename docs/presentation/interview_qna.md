# Interview Q&A

## Q: What is the project?

A Jetson Orin NX EIS project. I built a controllable CPU video stabilization
pipeline, added quality gates and review assets, measured Jetson runtime, then
tested where performance optimization and hardware acceleration actually help.

## Q: What is your current best result?

For Regular clips, the current performance baseline is:

```text
lp_rigid_strength080_dynzoom106
estimate_scale=0.5
feature_grid_size=16
```

It passes objective gates on all five Regular clips and was accepted by human
review.

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

But VPI CUDA did accelerate high-resolution warp-heavy modules:

```text
720p: 1.35x
1080p: 1.83x
1440p: 2.15x
4K: 2.33x
```

So the lesson is placement and dataflow matter.

## Q: What are the remaining limitations?

- Global warp cannot solve all local/parallax/rolling-shutter-like artifacts.
- Running and other challenge sets are not claimed as solved.
- GStreamer/NVMM dataflow is only probed, not integrated into the EIS pipeline.
- VPI module speedup is not the same as full-pipeline speedup.

## Q: What would you do next?

The next implementation direction is not another baseline tuning loop. The
current frontier is the device-side MMAPI/VPI/NVENC path:

```text
Step 1:
  keep post-geometry with first-frame identity as the current best device-side
  matrix candidate.

Step 2:
  treat raw pixel diff carefully because identity transcode already creates a
  large codec/colorspace baseline.

Step 3:
  only continue parity work if the next change has a clear target, such as a
  border workaround or colorspace/encoding baseline.
```

I would not move to real-time online motion estimation until that decision is
closed.

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
sanity, so inverse matrix is the current device-side direction.

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
candidate remains linear interpolation plus post-geometry with first-frame
identity.

## Q: Is the device-side result a real-time EIS pipeline?

No. It is an offline matrix-driven device warp/encode milestone. Motion
estimation is not running online inside the MMAPI path yet, and the device path
does not yet reproduce CPU post-processing such as crop, dynamic zoom, Lanczos
resize, and sharpen.

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
results/regular_gate_est0p5_grid16_validation_20260718/regular_gate_validation_summary.md
```
