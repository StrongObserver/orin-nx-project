# Next-Stage Execution Plan - 2026-07-18

## Objective

Build two mature engineering evidence chains after the Regular CPU baseline:

```text
1. VPI high-resolution warp module demo: acceleration boundary.
2. Challenge-set boundary package: model boundary.
```

Keep GStreamer/NVMM as a support dataflow measurement line. Defer mesh/grid warp
implementation.

## P0 - VPI High-Resolution Warp Module Demo

Contract:

```text
configs/harness/contracts/vpi_highres_warp_module_demo_v1.json
```

Tasks:

1. Reuse existing `results/vpi_resolution_scaling_benchmark/summary.csv`.
2. Add or verify one small correctness check for OpenCV CPU vs VPI CUDA output.
3. Produce a clear crossover/speedup statement.
4. Update `docs/vpi_warp_module_report_2026-07-18.md` and presentation docs.

Expected outputs:

```text
speedup table
crossover statement
correctness check summary
presentation chart
```

Success criteria:

```text
VPI CUDA speedup is stated only for high-resolution module work.
640x360 full-pipeline negative result remains visible.
No full-pipeline acceleration claim is made.
```

Stop rules:

```text
Stop if output correctness mismatch cannot be explained by border/interpolation.
Stop if the task starts requiring full EIS pipeline rewrite.
```

## P1 - Challenge-Set Boundary Package

Contract:

```text
configs/harness/contracts/challenge_boundary_package_v1.json
```

Tasks:

1. Select 2-3 representative clips from each challenge role:
   - Running;
   - QuickRotation;
   - Parallax;
   - Crowd.
2. Run the frozen Regular performance baseline.
3. Generate side-by-side review assets.
4. Evaluate metrics.
5. Label each category as pass / boundary / fail.
6. Write one-sentence failure attribution per category.

Expected outputs:

```text
results/challenge_boundary_package_<YYYYMMDD>/
C:\Users\Admin\Videos\orin nx\review\challenge\<YYYYMMDD>_challenge_boundary_package\
docs/challenge_boundary_report_<YYYYMMDD>.md
```

Success criteria:

```text
Regular remains the main success gate.
Challenge sets are presented as operating envelope, not headline pass rate.
Each category has a clear model-boundary explanation.
```

Stop rules:

```text
Do not tune the baseline inside this loop.
Stop if boundary labels are unclear and request human review.
```

## P2 - GStreamer / NVMM Latency Boundary

Contract:

```text
configs/harness/contracts/gst_nvmm_decode_convert_latency_v1.json
```

Tasks:

1. Repeat the minimum decode/NVMM/convert/fakesink probe 3 times.
2. Add pure hardware decode/convert/encode boundary.
3. Add CPU-readable boundary.
4. Record wall time and EOS status.
5. Write a latency summary.

Expected outputs:

```text
results/gst_nvmm_decode_convert_latency_<YYYYMMDD>/summary.md
commands.txt
run_log_*.txt
```

Success criteria:

```text
Dataflow stages have measured wall-time evidence.
CPU/NVMM boundary is explicitly stated.
No EIS acceleration claim is made.
```

Stop rules:

```text
Stop if caps negotiation fails after one mechanical fix.
Stop before changing system packages or rewriting cpu_stabilize.py.
```

## P3 - Presentation Update

Tasks:

1. Add VPI module demo result to `docs/presentation/hardware_acceleration_boundary.md`.
2. Add Challenge boundary summary to presentation docs.
3. Keep the dual-baseline story unchanged.

Success criteria:

```text
5-minute project explanation remains clear.
Every number has an evidence path.
No challenge result is overclaimed.
```

## P4 - Route Recheck

After P0-P2:

```text
If VPI module demo is clean:
  keep it as hardware acceleration evidence.

If Challenge package is clear:
  use it as model-boundary evidence.

If GStreamer latency shows readback dominates:
  do not integrate EIS into GStreamer yet.

If GStreamer latency is promising:
  create a new integration contract before coding.
```

## Deferred

Mesh/grid warp remains future work until:

```text
one specific badcase is selected;
ROI-level metrics are defined;
crop/black-border risk is controlled;
implementation cost is acceptable.
```
