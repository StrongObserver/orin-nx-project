# Device-Side Stage Demo Handoff - 2026-07-19

## Historical Outdoor-Car Stage Demo

Historical outdoor-car dataflow stage demo:

```text
post_geometry_identity_first
= post geometry + first-frame identity + VPI linear
```

This proves an offline CPU-matrix-driven MMAPI/VPI/NVENC device-side warp and
encode path on the outdoor-car smoke source. It does not prove real-time full
EIS and it is not the current Regular05 EIS-quality replay convention.

Current EIS-quality device replay convention:

```text
Regular05 source_to_dest
```

See:

```text
docs/layered_artifact_diagnosis_2026-07-19.md
configs/harness/contracts/regular05_hybrid_matrix_handoff_v1.json
```

## Best Evidence Assets

Historical outdoor-car review video:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260719_same_source_matrix_device_warp\20260719_device_matrix_warp_demo_sample_outdoor_car_jetson_post_geometry_identity_first_grid_compare.mp4
```

Use this only for dataflow/history review because it compares:

```text
source / CPU stabilized / post_geometry / post_geometry_identity_first
```

Technical attribution image:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260719_same_source_matrix_device_warp\20260719_device_matrix_warp_demo_sample_outdoor_car_jetson_post_geometry_frame_attribution.jpg
```

Older comparison kept for traceability:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260719_same_source_matrix_device_warp\20260719_same_source_matrix_device_warp_raw_cpu_device_compare.mp4
```

Do not commit these media files.

## Result Table

| Candidate | CPU-vs-device mean_abs_center_avg | p95_abs_center_avg | VPI warp avg at frame 100 | Decision |
|---|---:|---:|---:|---|
| old inverse | 44.739667 | 156.975000 | 1.416640 ms | valid path, poor parity |
| aligned identity first | 46.884302 | 159.958333 | 1.436010 ms | worse |
| post geometry | 30.688605 | 116.958333 | 1.455940 ms | strong improvement |
| post geometry + first-frame identity | 30.241568 | 115.866667 | 1.442760 ms | accepted stage demo |
| post geometry + first-frame identity + Catmull-Rom | 30.902334 | 117.875000 | 2.980040 ms | reject |

Identity transcode baseline:

| Comparison | mean_abs_center_avg | p95_abs_center_avg | Meaning |
|---|---:|---:|---|
| source vs identity transcode | 25.664099 | 97.133333 | codec/colorspace/dataflow pixel-diff floor |

Interpretation:

```text
The accepted device output is not pixel-equivalent to CPU output, but its raw
pixel diff is now close to the measured identity-transcode floor. Future review
should rely on visual evidence plus targeted region checks, not raw pixel diff
alone.
```

## Claim Boundary

Allowed wording:

```text
I validated a non-Python device-side path on Jetson Orin NX:
MMAPI decode / NvBufSurface -> pitch-linear NV12_ER scratch -> VPI CUDA warp
-> block-linear NV12 -> NVENC. The current stage uses offline CPU-generated
matrices and the best accepted candidate is post_geometry_identity_first.
```

Forbidden wording:

```text
real-time full EIS
CPU-output pixel equivalence
full-pipeline VPI acceleration
zero-copy full chain
product-grade EIS
```

## What Not To Reopen

Do not reopen these unless a new input changes the evidence:

```text
old inverse as default
Catmull-Rom interpolation
raw pixel diff chasing
Python appsink/appsrc EIS integration
pitch-linear main path into NVENC
Regular05 global-affine tuning
```

## Current Engineering Entry

The next engineering direction for EIS-quality work starts from Regular05
source_to_dest, not outdoor-car inverse/post_geometry matrices:

```text
regular05_hybrid_matrix_handoff_v1
```

Before implementation, define:

```text
1. how matrices move from CPU estimation to the MMAPI/VPI thread;
2. what timing is measured end-to-end versus VPI-warp-only;
3. what quality no-regression check is used against the accepted CPU baseline;
4. where the loop stops if latency or quality fails.
```
