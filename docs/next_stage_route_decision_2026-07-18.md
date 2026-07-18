# Next-Stage Route Decision - 2026-07-18

## Decision

The next stage should use two main evidence chains:

```text
Main line A: VPI high-resolution warp module demo/report
Main line B: Challenge-set boundary package
```

One support line remains useful:

```text
Support line: GStreamer/NVMM dataflow latency boundary
```

Defer:

```text
Mesh/grid warp implementation
```

## Why

The Regular CPU baseline is already closed:

```text
Regular performance baseline:
  lp_rigid_strength080_dynzoom106
  estimate_scale=0.5
  feature_grid_size=16
```

The project does not need another local tuning loop. It needs two stronger
engineering stories:

```text
Where acceleration helps:
  VPI high-resolution warp module scaling.

Where the model applies or breaks:
  Challenge-set operating envelope.
```

## Route A: VPI Module Demo

Value:

- Quantified hardware acceleration boundary.
- Explains why 640x360 full-pipeline VPI was slower.
- Shows mature placement of acceleration instead of blind GPU usage.

Required next evidence:

```text
speedup table / crossover statement
simple output-correctness check
presentation chart
module report
```

Contract:

```text
configs/harness/contracts/vpi_highres_warp_module_demo_v1.json
```

## Route B: Challenge-Set Boundary Package

Value:

- Converts remaining artifacts into model-boundary explanation.
- Shows operating-envelope thinking.
- Separates in-domain Regular success from out-of-domain challenge behavior.

Required next evidence:

```text
Running / Parallax / Crowd / QuickRotation selected clips
side-by-side review assets
metrics table
pass / boundary / fail labels
one-sentence attribution per category
```

Contract:

```text
configs/harness/contracts/challenge_boundary_package_v1.json
```

## Support Route: GStreamer / NVMM

Value:

- Jetson systems depth.
- Dataflow latency boundary before integration.

Keep it scoped:

```text
decode / convert / readback / encode measurement only
```

Do not claim:

```text
EIS acceleration
zero-copy integration
full-pipeline speedup
```

Contract:

```text
configs/harness/contracts/gst_nvmm_decode_convert_latency_v1.json
```

## Deferred Route: Mesh / Grid Warp

Reason:

- It addresses real global-warp limits.
- But implementation and proof cost are high.
- It needs selected badcases and ROI-level metrics before coding.

Current status:

```text
future work, not next implementation loop
```

## Execution Order

```text
1. VPI high-resolution module demo/report
2. Challenge-set boundary package
3. GStreamer/NVMM latency boundary
4. Mesh/grid warp research only after a concrete badcase contract exists
```
