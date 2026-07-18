# Future Extensions - 2026-07-18

## Current Baseline Is Closed Enough

The Regular CPU path is now good enough to stop local parameter tuning:

```text
quality-safe baseline:
  estimate_scale=1.0, feature_grid_size=12

Regular performance baseline:
  estimate_scale=0.5, feature_grid_size=16
```

Do not reopen Regular05 or Regular gate tuning unless a new user-visible issue is
found.

## Extension 1: Challenge-Set Boundary Package

Purpose:

```text
Show what the current global-warp EIS can and cannot solve.
```

Scope:

- Running;
- Parallax;
- Crowd;
- QuickRotation.

Expected output:

- one short boundary report;
- selected review videos;
- no headline pass-rate claim.

Stop rule:

```text
Do not optimize challenge clips if it hurts Regular.
```

## Extension 2: Mesh / Grid Warp Research

Purpose:

```text
Investigate the next algorithm class needed for local distortion, parallax, or
rolling-shutter-like artifacts.
```

Scope:

- read one or two strong references first;
- prototype only after a concrete failure case is selected;
- keep the current CPU baseline as comparison.

Stop rule:

```text
Do not start mesh/grid work as a vague refactor. Start only from a selected
badcase and a measurable verifier.
```

## Extension 3: GStreamer / NVMM Appsink Path

Purpose:

```text
Measure whether the hardware decode/NVMM path can reduce data movement before
EIS integration.
```

Start from:

```text
configs/harness/contracts/gst_nvmm_decode_convert_latency_v1.json
docs/gstreamer_nvmm_latency_plan_2026-07-18.md
```

Possible next contracts:

```text
gst_nvmm_fakesink_repeat_latency_v1
gst_nvmm_cpu_boundary_latency_v1
gst_nvmm_decode_encode_latency_v1
```

Stop rule:

```text
Do not integrate into cpu_stabilize.py until decode/convert/readback boundaries
are measured.
```

## Extension 4: VPI High-Resolution Warp Demo

Purpose:

```text
Turn the VPI module benchmark into a small presentation asset.
```

Scope:

- keep it module-level;
- use existing resolution scaling evidence;
- optionally generate a simple chart;
- do not call it full-pipeline EIS acceleration.

Evidence:

```text
docs/vpi_warp_module_report_2026-07-18.md
results/vpi_resolution_scaling_benchmark/vpi_module_summary.md
```

## Extension 5: Commit And Publish Hygiene

Purpose:

```text
Prepare a clean repo stage for GitHub or interview review.
```

Must check:

- no videos or raw data in Git;
- no private notes or internal source text;
- no passwords/tokens;
- README and presentation docs point to ignored local evidence paths only.

Reference:

```text
docs/commit_scope_2026-07-18.md
```
