# Public Source Cards

The cards below are public, commit-safe references for the Orin NX EIS project.
They are chosen for closeness to the current pipeline and Harness boundary, not
for novelty.

## Summary Ranking

| Key | Source | Type | Fit | Main use |
|---|---|---|---|---|
| `public:vidstab_ffmpeg` | `georgmartius/vid.stab`, FFmpeg `vidstabdetect` / `vidstabtransform` | Open-source repo/tool | High | Mature traditional stabilization baseline and two-pass transform smoothing |
| `public:opencv_videostab` | OpenCV `videostab` module | Open-source library | High | Classic global/local motion, smoothing, inpainting, and stabilization abstractions |
| `public:nus_dataset` | NUS Video Stabilization Dataset / SIGGRAPH 2013 assets | Dataset | High | Public, reproducible Regular/Running/Parallax/Zooming/QuickRotation/Crowd gates |
| `public:l1_optimal_camera_paths` | Grundmann, Kwatra, Essa, CVPR 2011 | Paper | High | LP/L1 path smoothing, derivative constraints, crop-aware stabilization |
| `public:bundled_camera_paths` | Liu et al., ACM TOG/SIGGRAPH 2013 | Paper/dataset | High | Spatially varying motion, parallax, rolling shutter, bundled paths |
| `public:meshflow` | MeshFlow, ECCV 2016, plus third-party implementations | Paper/repo | Medium-high | Minimum-latency mesh-based online stabilization ideas |
| `public:nvidia_vpi_samples` | NVIDIA VPI official samples | Official docs/samples | High | Jetson VPI operator backend usage and format constraints |
| `public:jetson_accelerated_gstreamer` | NVIDIA Jetson Accelerated GStreamer docs | Official docs | High | NVMM/NVDEC/NVENC/VIC dataflow and performance path |
| `public:jetson_multimedia_api` | Jetson Multimedia API samples | Official samples | Medium-high | Lower-level camera/CUDA/V4L2/encoder dataflow reference |

## `public:vidstab_ffmpeg`

Source:

- https://github.com/georgmartius/vid.stab
- FFmpeg filters: `vidstabdetect`, `vidstabtransform`

Public metadata checked on 2026-07-17:

- GitHub stars: 946
- Forks: 122
- Last updated: 2026-07-15
- License metadata: `NOASSERTION`

Why it fits:

- Mature traditional stabilizer already aligned with this project as an external
  baseline.
- The two-pass design is useful as a conceptual reference: detect transforms,
  then smooth and transform using full-trajectory knowledge.
- Good fallback when the project needs a stable visual baseline quickly.

Read first:

- README usage and filter parameters.
- Transform file concept and smoothing/crop options.
- Compare with current `results/vidstab_baseline/ostrich_vidstab_compare.mp4`.

Use in this project when:

- A future agent needs a known-good visual reference before changing the custom
  pipeline.
- The question is whether the input video is stabilizable by a traditional
  method at all.

Do not use it to claim:

- Jetson acceleration.
- Custom pipeline quality.
- Same-input performance improvement.

## `public:opencv_videostab`

Source:

- https://github.com/opencv/opencv_contrib/tree/4.x/modules/videostab
- OpenCV docs for `videostab` classes.

Public metadata checked on 2026-07-17:

- Parent repo `opencv/opencv_contrib` stars: 10142
- Forks: 5946
- Last updated: 2026-07-17
- License: Apache-2.0

Why it fits:

- Provides classic building blocks close to this project: global motion
  estimation, RANSAC-like robust fitting, motion filtering, inpainting, and
  wobble/rolling-shutter related abstractions.
- Useful as a design reference without turning the project into a black box.

Read first:

- `global_motion.hpp` / `global_motion.cpp`.
- `motion_stabilizing.hpp` / `motion_stabilizing.cpp`.
- `stabilizer.hpp` / `stabilizer.cpp`.

Use in this project when:

- Motion estimation confidence, smoothing abstraction, or inpainting/crop
  behavior is unclear.
- A future implementation needs a mature pattern for separating estimator,
  smoother, and warper.

Do not use it to claim:

- Product-grade EIS.
- Jetson hardware acceleration.

## `public:nus_dataset`

Source:

- NUS Video Stabilization Dataset related to Liu et al. SIGGRAPH 2013.
- Project page previously used for `Regular.zip` and `Running` assets.

Why it fits:

- Already adopted in this project.
- Provides public, reproducible categories: Regular, Running, QuickRotation,
  Zooming, Parallax, and Crowd.
- Supports the current Harness split: Regular main gate, Running challenge gate.

Read first:

- Local prepared manifests under `results/nus_regular_gate_v1/` and
  `results/nus_running_gate_v1/`.
- `scripts/prepare_nus_gate_set.py`.
- `configs/harness/gates.json`.

Use in this project when:

- Creating or auditing gate/challenge sets.
- Explaining why Running is a model boundary rather than the main success target.

Do not use it to claim:

- Full dataset success unless all selected roles and evidence are explicitly
  evaluated.

## `public:l1_optimal_camera_paths`

Source:

- Grundmann, Kwatra, Essa, \"Auto-Directed Video Stabilization with Robust L1
  Optimal Camera Paths\", CVPR 2011.
- DOI: https://doi.org/10.1109/CVPR.2011.5995525

Public metadata checked on 2026-07-17:

- OpenAlex cited_by_count: 343
- OpenAlex work: https://openalex.org/W2113018061

Why it fits:

- Directly relevant to the current LP-affine branch and its first/second/third
  derivative constraints.
- Good reference for why path smoothing is not just moving average filtering:
  the desired path can contain constant, linear, and parabolic camera segments.

Read first:

- L1 optimal camera path formulation.
- Crop/window constraints.
- Treatment of first, second, and third derivatives.

Use in this project when:

- LP smoothing produces rollback or excessive second-difference artifacts.
- A future agent wants to add an intent-preservation soft constraint inside the
  LP objective instead of post-blending final matrices.

Do not use it to claim:

- The current LP implementation is equivalent to the paper.
- Running gate should pass under a global affine model.

## `public:bundled_camera_paths`

Source:

- Liu, Yuan, Tan, Sun, \"Bundled Camera Paths for Video Stabilization\", ACM TOG
  32(4), SIGGRAPH 2013.
- DOI: https://doi.org/10.1145/2461912.2461995
- PDF search result: http://www.liushuaicheng.org/SIGGRAPH2013/BundledPaths.pdf

Public metadata checked on 2026-07-17:

- OpenAlex cited_by_count: 353
- OpenAlex work: https://openalex.org/W2057412674
- Third-party repo `SuTanTank/BundledCameraPathVideoStabilization`: 49 stars,
  12 forks, BSD-2-Clause, updated 2026-04-10

Why it fits:

- The paper targets exactly the failure modes that global 2D affine struggles
  with: parallax, rolling shutter, and spatially variant motion.
- It also anchors the public NUS dataset already used by this project.

Read first:

- Spatially varying mesh motion representation.
- As-similar-as-possible motion estimation idea.
- Space-time path smoothing and failure examples.

Use in this project when:

- Visual review shows corner pull, local distortion, parallax, or jello.
- A future agent is tempted to keep forcing global affine on high-risk scenes.

Do not use it as the immediate next implementation:

- Mesh/RS support is a future upper-bound direction. The current next project
  step remains Jetson same-input performance evidence.

## `public:meshflow`

Source:

- Liu et al., \"MeshFlow: Minimum Latency Online Video Stabilization\", ECCV
  2016.
- Poster search result: http://www.eccv2016.org/files/posters/P-4A-28.pdf
- Example third-party repo search result: `how4rd/meshflow`.

Public metadata checked on 2026-07-17:

- OpenAlex cited_by_count: 154
- OpenAlex work: https://openalex.org/W2519006193
- Third-party repo `how4rd/meshflow`: 48 stars, 11 forks, license not declared,
  updated 2026-07-15

Why it fits:

- Offers a bridge between full offline bundled paths and lower-latency
  stabilization.
- Relevant if the project later needs to explain why mesh-based motion can
  handle local motion better than a single affine transform.

Read first:

- Meshflow motion representation.
- Adaptive path smoothing.
- Online/minimum latency assumptions.

Use in this project when:

- Regular or challenge clips fail because one global transform cannot represent
  foreground/background motion.
- A future phase explicitly moves beyond global affine.

Do not use it now to:

- Expand scope before Jetson performance evidence exists.
- Add a large black-box implementation that cannot be explained in interviews.

Open question:

- The implementation quality, license, and maintenance status of third-party
  repos must be checked before cloning or adapting.

## `public:nvidia_vpi_samples`

Source:

- https://docs.nvidia.com/vpi/samples.html
- VPI Pyramidal LK Optical Flow sample.
- VPI Dense Optical Flow sample.
- VPI Perspective Warp sample.

Why it fits:

- Official operator-level reference for the exact Jetson acceleration direction.
- Provides backend boundaries such as CPU/CUDA/VIC/PVA/OFA availability and
  image format constraints.

Read first:

- Pyramidal LK Optical Flow sample and algorithm docs.
- Perspective Warp sample, especially backend list and input/output format.
- Remap and image conversion samples if the bottleneck is crop/warp.

Use in this project when:

- Replacing a measured hot module with a VPI backend.
- Investigating whether readback/synchronization costs erase operator speedup.

Do not use it to claim:

- Full-pipeline acceleration without same-input Jetson end-to-end timing.

## `public:jetson_accelerated_gstreamer`

Source:

- NVIDIA Jetson Linux Developer Guide, Accelerated GStreamer.

Why it fits:

- Official reference for hardware decode/convert/encode paths and Jetson-specific
  GStreamer elements.
- Important if the project moves from offline MP4 processing to camera/stream
  input or avoids CPU readback.

Read first:

- Hardware encoder/decoder examples.
- `nvvidconv`, `nvv4l2decoder`, `nvv4l2h264enc`/`nvv4l2h265enc`, and memory type
  notes.
- CUDA memory / NVMM interoperability limits for the JetPack version on the
  device.

Use in this project when:

- The bottleneck is not the warp operator but video I/O, colorspace conversion,
  or CPU-GPU copies.

Do not use it to:

- Rewrite the pipeline before the current same-input performance contract is
  measured.

## `public:jetson_multimedia_api`

Source:

- Jetson Multimedia API sample applications, usually under
  `/usr/src/jetson_multimedia_api/samples/` on the device.

Why it fits:

- Lower-level reference for V4L2 camera capture, CUDA processing, format
  conversion, and encoder paths.
- Useful when GStreamer examples are too high-level or when debugging buffer
  ownership and device memory.

Read first:

- `12_v4l2_camera_cuda` or similarly named camera/CUDA sample for the installed
  JetPack version.
- Video convert and video encode samples.

Use in this project when:

- A future phase needs camera-to-CUDA-to-encoder dataflow.
- GStreamer/NVMM behavior is ambiguous and a minimal native sample is easier to
  reason about.

Do not use it to:

- Add broad C++ infrastructure before a measured performance bottleneck demands
  it.
