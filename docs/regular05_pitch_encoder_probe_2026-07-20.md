# Regular05 Pitch Encoder Probe - 2026-07-20

## Decision

NVENC does not produce a valid visual output when the transcode main buffer is
changed to pitch-linear for this Regular05 path. The command returns success,
but the encoded video becomes nearly solid green after the first frames.

This closes the other side of the layout question:

```text
VPI needs pitch-linear NV12_ER scratch.
NVENC/main chain needs the block-linear main buffer path.
```

Therefore the block-linear main chain plus pitch-linear VPI scratch transform
sandwich is a hard boundary for the current MMAPI path.

## Probe

Existing patch script:

```text
scripts/patch_mmapi_transcode_pitch_only.py
```

Remote sample:

```text
/home/nvidia/orin-nx-project/_mmapi_work/jetson_multimedia_api/samples/99_transcode_pitch_only_regular05_probe
```

Input:

```text
regular_gate05_regular_6 source.h264
```

## Results

```text
rc: 0
App run was successful
output mp4 size: about 59 KB
```

Frame sanity:

| Frame | Mean | Std | Interpretation |
|---:|---:|---:|---|
| 0 | 78.361571 | 14.630978 | partially non-flat |
| 1 | 78.438945 | 6.829839 | already nearly flat |
| 30 | 79.059171 | 0.458032 | near-solid output |
| 90 | 79.062973 | 0.472845 | near-solid output |
| 179 | 79.047344 | 0.553334 | near-solid output |

The sampled frame at 90 is visually near-solid green.

Local evidence:

```text
results/regular05_pitch_encoder_probe_20260720
```

## Interpretation

This is not a clean encoder failure because the app returns success. It is a
semantic/data-layout failure: the encoded output is not visually valid. The
result matches earlier pitch-linear main-chain smoke evidence.

The current accepted design remains justified:

```text
decoder/encoder main path: block-linear
VPI scratch path: pitch-linear NV12_ER
bridge: NvBufSurfTransform sandwich
```

## Claim Boundary

Allowed:

```text
Pitch-linear main-chain encoding is not visually valid in this MMAPI path.
The transform sandwich is required by both VPI and NVENC layout constraints.
```

Forbidden:

```text
NVENC cleanly accepts pitch-linear output in this path.
Zero-copy full chain is available.
The transform sandwich is merely accidental implementation overhead.
```

## Next Step

The remaining useful performance work should not try to remove the transform
sandwich outright. Better directions:

```text
1. minimize the number of transforms only if quality remains fixed;
2. investigate whether VIC/NvBufSurfTransform scheduling can be overlapped;
3. move up to live-producer scheduling and end-to-end pipeline timing;
4. treat zero-copy full chain as unsupported in this stage.
```
