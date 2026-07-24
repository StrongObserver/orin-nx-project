# Regular05 Startup Black Fix Closeout - 2026-07-24

## Scope

This closeout records the startup black-border follow-up discovered after the
accepted VPI-managed paths were rechecked during `vpi_cuda_owned_bridge_v1`.

It does not change the accepted `resid_r15_s07` Regular-gate quality anchor and
does not change the negative decision for the CUDA-owned VPI bridge. The tested
path remains the accepted stream-only reuse consumer.

## Problem

Human review of the accepted-path comparison grid found a brief left-edge black
exposure in the first seconds. The source was checked separately and did not
contain the issue. The exposure was synchronized across accepted EGLImage,
stream-only reuse, and NvBuffer pair outputs, so the cause was traced to the
startup portion of the `resid_r15_s07` matrix sequence rather than to a single
consumer route.

## Candidate History

| Candidate | Intent | Objective result | Decision |
|---|---|---:|---|
| old stream | Existing accepted stream-only reuse output | left80 max first 180 = `0.044722222` | diagnostic baseline |
| startup FOV v2 | Remove first-90-frame left-edge exposure with frame-varying extra scale | left80 max first 90 = `0.000000000`; black-border p95 = `0.000000000` | rejected by human review because slight zooming remained |
| constant FOV first 90 | Use one constant inclusion-safe scale for first 90 frames | left80 max first 90 = `0.000000000`; black-border p95 = `0.000000000` | diagnostic, still returned scale at frame 90 |
| constant FOV full | Use one constant inclusion-safe scale for all 180 frames | left80 max first 180 = `0.000000000`; black-border p95 = `0.000000000`; max black-border = `0.000000000` | objective pass, pending human visual acceptance |

## Evidence

Local evidence:

```text
results/vpi_cuda_owned_bridge_20260724/startup_black_fix_v2/
results/vpi_cuda_owned_bridge_20260724/startup_black_fix_const/
results/vpi_cuda_owned_bridge_20260724/startup_black_fix_const_full/
```

Current recommended review copy:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260724_regular05_startup_black_fix\20260724_regular05_startup_black_fix_source_old_const90_constfull_grid_30fps.mp4
```

Key CSV summaries:

```text
results/vpi_cuda_owned_bridge_20260724/startup_black_fix_const_full/left_edge_summary.csv
results/vpi_cuda_owned_bridge_20260724/startup_black_fix_const_full/black_summary.csv
```

## Current Decision

`constant FOV full` is objectively clean on the measured black-border and
left-edge metrics. It should remain pending human visual review because the
fix buys that cleanliness by applying a constant extra inclusion-safe scale
across the full 180-frame Regular05 clip.

Do not mark it accepted until the user confirms that the FOV/scale trade-off is
visually acceptable. If accepted, the next narrow step is a five-Regular
extension under the same source-to-destination matrix convention and the same
accepted stream-only reuse consumer.

## Claim Boundary

Allowed:

```text
The startup black exposure in Regular05 has a bounded objective fix candidate:
constant full-clip FOV scale removes the measured left-edge black border in the
existing stream-only reuse path.
```

Forbidden:

```text
Do not present this as EIS quality improvement.
Do not present it as CUDA-owned bridge success.
Do not present it as full real-time EIS, zero-copy, or full-pipeline acceleration.
Do not generalize to all five Regular clips until a five-clip extension is run
or the decision is explicitly limited to Regular05.
```
