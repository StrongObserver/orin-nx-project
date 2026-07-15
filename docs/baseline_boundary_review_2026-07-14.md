# Baseline Boundary Review - 2026-07-14

## Purpose

Before continuing EIS tuning, this note fixes the current evaluation boundary:
what the gate matrix baseline can prove, what it cannot prove, and which metric
failures should drive the next experiment.

## First-Principles Boundary

A useful video EIS baseline must answer four separate questions:

1. Does it reduce unwanted high-frequency camera shake?
2. Does it preserve intentional camera motion such as panning or walking drift?
3. Does it avoid hard visual regressions: black border, excessive crop, frame
   jumps, rollback, local distortion, or jello-like artifacts?
4. Does it run fast enough on the target device after quality is acceptable?

The current project has no gyro, no ground-truth camera pose, and no standard
benchmark labels. Therefore image-motion metrics are proxy measurements, not
absolute truth. They are useful for same-input regression and failure triage,
but they must be paired with scene vetting and side-by-side visual review before
being used as final quality evidence.

## Current Gate Matrix Meaning

The current gate matrix is built by taking the first 240 frames from 10 local
videos and resizing each clip so the long side is at most 720 px. It is useful as
a compact diagnostic set because it gives repeatable same-input comparisons
across parameter versions.

It is not a final quality benchmark:

- the clips have not been fully labeled as ordinary shake, intentional camera
  motion, scene cut, foreground-dominant motion, low texture, or strong parallax;
- there is no ground-truth stable camera path;
- subjective veto checks are not completed;
- results are Windows-side quality diagnostics, not Jetson performance evidence.

## Current Best Diagnostic Baseline

Current baseline under review:

```text
results/gate_matrix/lp_affine_trim010
results/gate_matrix/gate_matrix_lp_affine_trim010_eval.csv
results/gate_matrix/gate_matrix_lp_affine_trim010_eval.json
```

Core configuration:

```text
smoothing_method=lp_affine
crop_ratio=0.85
lp_trim_ratio=0.10
lp_w1=50, lp_w2=10, lp_w3=20, lp_w4=30
mask_safety_max_invalid=0.01
```

Observed result without warmup:

```text
complete pass: 2/10
SR pass: 3/10
residual improvement pass: 2/10
residual acceptable-or-pass: 3/10
second-diff non-regression: 7/10
black hard fail: 0/10
crop hard fail: 0/10
```

Warmup diagnostic result, skipping the first 5 motion samples:

```text
results/gate_matrix/gate_matrix_lp_affine_trim010_warmup5_eval.csv
results/gate_matrix/gate_matrix_lp_affine_trim010_warmup5_eval.json

complete pass: 2/10
SR pass: 3/10
residual improvement pass: 2/10
residual acceptable-or-pass: 3/10
second-diff non-regression: 9/10
black hard fail: 0/10
crop hard fail: 0/10
```

## Metric Judgment

The current baseline is meaningful, but only as a diagnostic baseline.

The black-border and crop gates are meaningful hard safety gates. The current
configuration is close to the invalid-mask budget: p95 invalid mask is around
1% on every gate clip, so there is little room to loosen FOV constraints without
creating visible border risk.

The second-diff top-5 non-regression gate is directionally meaningful, but the
raw no-warmup result is polluted by initialization/boundary effects. The warmup
diagnostic changes second-diff non-regression from 7/10 to 9/10, while complete
pass remains 2/10. This means second-diff is not the main blocker after warmup.

The SR/residual gates are still meaningful as image-motion proxy metrics, but
they are scene-dependent. They can penalize intended motion, foreground motion,
parallax, weak texture, and errors in re-estimating output video motion. The
current thresholds should not be weakened yet, because the failure pattern is
more likely caused by sample mix and proxy-measurement mismatch than by a clearly
over-strict threshold.

## Next Action

Do not continue blind LP weight or trim-ratio sweeps yet.

The next concrete step should be a gate-set audit:

1. Label each of the 10 clips as ordinary shake, intentional motion, strong
   foreground/parallax, low texture, scene cut, or diagnostic-only.
2. Re-run evaluation with `--warmup-frames 5` as the default diagnostic view,
   while keeping no-warmup results for regression comparison.
3. Split acceptance into:
   - hard gates: black border and crop;
   - quality gates on vetted ordinary-shake clips;
   - diagnostic metrics on challenge clips.
4. Only after the sample roles are clear, decide whether SR/residual thresholds
   should remain as pass/fail gates or become graded diagnostic metrics.
