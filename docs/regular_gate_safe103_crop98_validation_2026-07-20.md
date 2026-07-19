# Regular Gate Safe103 Crop98 Validation - 2026-07-20

## Stage Decision

The user-accepted Regular05 `safe103_crop98` candidate does not generalize to
the full five-clip Regular gate without per-clip tuning.

The candidate remains valid as a Regular05 visual result, but it must not be
claimed as a Regular gate producer.

## What Was Frozen

```text
producer: bounded_delay_lp_rigid
producer_delay_frames: 90
matrix convention: source_to_dest
viewport policy: safe103 constant scale
postprocess: crop98
no per-clip tuning
```

## Regular Gate Result

| Clip | Frames | crop98 black p95 | max black | frames_gt_0p01 | Hard gate |
|---|---:|---:|---:|---:|---|
| regular_gate01_regular_10 | 180 | 0.024714410 | 0.028485243 | 22 | fail |
| regular_gate02_regular_19 | 300 | 0.339244141 | 0.383984375 | 172 | fail |
| regular_gate03_regular_13 | 180 | 0.000837674 | 0.001297743 | 0 | pass |
| regular_gate04_regular_8 | 180 | 0.008358072 | 0.010998264 | 5 | pass by p95, borderline max |
| regular_gate05_regular_6 | 180 | 0.000421441 | 0.000755208 | 0 | pass |

Summary:

```text
pass: 3/5 by p95 hard gate
fail: regular_gate01, regular_gate02
borderline: regular_gate04 has max > 0.01 on 5 frames, p95 still under 0.01
```

## Failure Attribution

The failure is not a simple postprocess crop strength problem.

For the failed clips, stronger local postprocess crop did not fix the hard gate:

| Clip | crop98 p95 | crop95 p95 | crop92 p95 | Interpretation |
|---|---:|---:|---:|---|
| regular_gate01 | 0.024714410 | 0.024848091 | 0.023677083 | crop strength does not remove the dark/border region |
| regular_gate02 | 0.339244141 | 0.328370443 | 0.312072265 | severe border/dark region remains |

This means the same safe103/crop98 strategy is not a general Regular producer.
Continuing with per-clip crop/scale tuning would violate the contract.

## Review Assets

Review directory:

```text
C:\Users\Admin\Videos\orin nx\review\performance\20260720_regular_gate_safe103_crop98_validation\
```

Each clip has:

```text
source / safe103 / safe103_crop98
```

## Claim Boundary

Allowed:

```text
safe103_crop98 is user-accepted on Regular05.
The same frozen strategy passes 3/5 Regular clips by black-border p95.
Regular01 and Regular02 fail hard black-border gates under the same strategy.
```

Forbidden:

```text
safe103_crop98 passes the Regular gate.
safe103_crop98 is a general Regular producer.
per-clip crop or scale tuning as one frozen strategy.
all-scene EIS quality.
```

## Next Step

Stop local patching of the same global-matrix + crop strategy.

Use knowledge recovery / internal AI to ask for industry guidance on:

```text
FOV-safe crop policy
border fill / inpainting vs crop trade-off
causal smoothing with bounded delay
handling dark borders that do not disappear with simple center crop
when to switch from global matrix to mesh/grid or scene-specific strategy
```
