# Regular05 Block-Linear Pair Probe - 2026-07-20

## Decision

VPI PerspectiveWarp does not accept the tested block-linear NV12 matched pairs
on this Jetson/VPI version. This makes the current pitch-linear scratch path a
real compatibility requirement, not just an implementation habit.

## Probe

Two block-linear input/output scratch variants were tested with the identity
matrix:

```text
1. NVBUF_LAYOUT_BLOCK_LINEAR + NVBUF_COLOR_FORMAT_NV12
2. NVBUF_LAYOUT_BLOCK_LINEAR + NVBUF_COLOR_FORMAT_NV12_ER
```

Both used the Regular05 source and the accepted C++ EGLImage wrapper flow, with
only the scratch allocation format/layout changed.

## Results

Limited-range block-linear NV12:

```text
rc: 139
VPI error:
Only image formats with full range are accepted,
not VPIImageFormat(... BT601 ... VPI_MEM_LAYOUT_BLOCK16_LINEAR ...)
```

Full-range block-linear NV12_ER:

```text
rc: 139
VPI error:
Unsupported image format
VPIImageFormat(... BT601_ER ... VPI_MEM_LAYOUT_BLOCK16_LINEAR ...)
```

## Interpretation

The first error says limited-range block-linear NV12 is not accepted because VPI
PerspectiveWarp wants full range. The second error says full-range block-linear
NV12_ER is still unsupported. Therefore changing only range is not enough.

The accepted pitch-linear NV12_ER scratch pair remains the compatible VPI format
for this path.

## Claim Boundary

Allowed:

```text
VPI does not accept the tested block-linear scratch pairs for PerspectiveWarp.
The accepted pitch-linear scratch path is required for VPI compatibility.
```

Forbidden:

```text
VPI can directly process the main block-linear encoder format.
The transform sandwich is unnecessary.
Zero-copy full chain is available in the current path.
```

## Next Step

The remaining layout question is on the encoder side: test whether NVENC can
accept pitch-linear output. If NVENC also requires block-linear, then the
block-linear main chain plus pitch-linear VPI scratch transform sandwich is a
hard boundary.
