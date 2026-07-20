# Regular05 Surface Format Probe - 2026-07-20

## Decision

The accepted C++ path needs the transform sandwich because the encoder main
DMABUF and VPI scratch buffers are not format/layout/pitch compatible.

This explains why the direct `VPI_IMAGE_BUFFER_NVBUFFER` input probe failed with
`Input and output images must have the same format`.

## Probe

New patch script:

```text
scripts/patch_mmapi_transcode_surface_format_probe.py
```

Remote sample:

```text
/home/nvidia/orin-nx-project/_mmapi_work/jetson_multimedia_api/samples/99_transcode_surface_format_probe
```

Input:

```text
regular_gate05_regular_6 source.h264
```

## Results

| Surface | colorFormat | layout | pitch | plane0 pitch | plane1 pitch | plane1 offset |
|---|---:|---:|---:|---:|---:|---:|
| main_dmabuf | 6 | 1 | 640 | 640 | 640 | 262144 |
| input_scratch | 7 | 0 | 768 | 768 | 768 | 393216 |
| output_scratch | 7 | 0 | 768 | 768 | 768 | 393216 |

Raw log excerpt:

```text
main_dmabuf:    colorFormat=6 layout=1 pitch=640 plane1_offset=262144
input_scratch: colorFormat=7 layout=0 pitch=768 plane1_offset=393216
output_scratch: colorFormat=7 layout=0 pitch=768 plane1_offset=393216
```

## Interpretation

The main chain and VPI scratch differ in three important ways:

```text
colorFormat: 6 vs 7
layout:      1 vs 0
pitch:       640 vs 768
```

Therefore the current accepted path cannot simply wrap the main DMABUF and the
existing scratch as a matched VPI input/output pair. A format-matched experiment
must deliberately construct both VPI input and output with the same format and
layout before testing direct NvBuffer wrapping again.

## Claim Boundary

Allowed:

```text
The accepted transform sandwich is required by observed format/layout mismatch.
Direct NvBuffer input failed because input and output were not format-compatible.
```

Forbidden:

```text
The transform sandwich is unnecessary.
Zero-copy is already available.
VPI can directly warp between the observed main DMABUF and scratch formats.
```

## Next Step

Test only format-matched pairs:

```text
1. pitch-linear NV12_ER input/output scratch pair;
2. block-linear main-format input/output pair if VPI accepts it;
3. then decide whether any format-stable wrapper alternative is useful.
```
