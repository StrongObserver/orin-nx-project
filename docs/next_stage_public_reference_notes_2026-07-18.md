# Next-Stage Public Reference Notes - 2026-07-18

## Purpose

This note checks the internal-AI next-stage recommendations against public,
commit-safe sources. It only records conclusions that affect this project.

## VPI

Public sources:

```text
NVIDIA VPI Perspective Warp sample:
https://docs.nvidia.com/vpi/1.1.12/sample_perspwarp.html

VPI Python perspwarp API:
https://docs.nvidia.com/vpi/python/build/vpi.Image.perspwarp.html

VPI Perspective Warp C API:
https://docs.nvidia.com/vpi/4.1.3/group__VPI__PerspectiveWarp.html
```

Useful facts:

- VPI Perspective Warp supports CPU/CUDA/VIC style backend selection in the
  sample and API.
- Python `perspwarp` exposes interpolation, border, backend, and stream controls.
- The public API supports submitting perspective warp operations to a stream.

Project implication:

```text
VPI module demo is a valid next-stage line, but it must remain module-level
unless a same-input full-pipeline speedup is measured.
```

Validation needed:

```text
Compare OpenCV CPU and VPI CUDA output under the same transform and state border
or interpolation differences. Do not rely on speed alone.
```

## Jetson GStreamer / NVMM

Public sources:

```text
NVIDIA Jetson Accelerated GStreamer guide:
https://docs.nvidia.com/jetson/archives/r36.2/DeveloperGuide/SD/Multimedia/AcceleratedGstreamer.html

DeepStream Gst-nvvideo4linux2 plugin docs:
https://docs.nvidia.com/metropolis/deepstream/8.0/text/DS_plugin_gst-nvvideo4linux2.html

Jetson Multimedia API sample list:
https://docs.nvidia.com/jetson/archives/r36.4.3/ApiReference/group__l4t__mm__test__group.html
```

Useful facts:

- Jetson has official accelerated GStreamer elements for hardware decode,
  conversion, and encode.
- `nvv4l2decoder` is the NVIDIA V4L2 decode element family for encoded
  bitstreams.
- Jetson Multimedia API includes video encode/decode samples such as
  `01_video_encode` and CUDA/decode examples.

Project implication:

```text
GStreamer/NVMM should stay a dataflow-boundary loop first: decode, convert,
readback, encode. It is not yet EIS acceleration.
```

Validation needed:

```text
Measure pure hardware path, CPU readback boundary, and encode/output boundary
before touching cpu_stabilize.py.
```

## Mesh / Grid Warp

Public sources:

```text
MeshFlow: Minimum Latency Online Video Stabilization:
https://www.microsoft.com/en-us/research/publication/meshflow-minimum-latency-online-video-stabilization/

Bundled Camera Paths for Video Stabilization:
https://www.microsoft.com/en-us/research/publication/bundled-camera-paths-video-stabilization/
https://dl.acm.org/doi/10.1145/2461912.2461995
```

Useful facts:

- MeshFlow models motion at mesh vertices and smooths vertex profiles.
- Bundled Camera Paths uses spatially varying motion and bundled paths to handle
  parallax and rolling-shutter-style cases better than one global model.
- These methods address real global-warp limits, but implementation and proof
  cost are much higher than a boundary package.

Project implication:

```text
Mesh/grid warp is valid future work, but not the next implementation line for
this resume-stage project.
```

Validation needed before implementation:

```text
Pick one concrete parallax or RS-like failure case and define ROI-level metrics,
black-border/crop checks, and visual veto before coding.
```

## Challenge-Set Boundary Package

Public source:

```text
NUS dataset categories already used in this project:
Regular, Running, Parallax, Crowd, QuickRotation, Zooming
```

Project implication:

```text
Challenge sets are the best low-risk route to explain the current global-warp
operating envelope. They should not become a headline pass rate.
```

Suggested framing:

```text
Regular = in-domain success.
Running / Parallax / Crowd / QuickRotation = boundary cases that reveal model
assumptions and future work.
```

## Consolidated Judgment

Adopt the internal-AI ranking with one adjustment:

```text
Main line A: VPI high-resolution warp module demo/report
Main line B: Challenge-set boundary package
Support line: GStreamer/NVMM dataflow latency boundary
Future work: mesh/grid warp
```

Reason:

```text
This ordering maximizes explainable, quantified, resume-friendly evidence while
avoiding large new algorithm branches before they are justified.
```
