# Knowledge Routing Table

Use this table after reading the active Done Contract and current gate evidence.
It is a recovery aid for real blockers, not a mandatory preflight checklist.

| Blocker | First reference to open | What to extract | Stop condition |
|---|---|---|---|
| Regular visual quality still poor after one scoped change | `internal:eis_algorithm_topic`, then `public:l1_optimal_camera_paths` | Whether the failure is path smoothing, intent preservation, crop/FOV, or motion estimation | Stop if the next change is only another unconstrained weight sweep |
| Metrics improve but visual review shows rollback, frame jump, local pull, or jello | `internal:eis_cis_solution`, `public:bundled_camera_paths`, `public:meshflow` | Which failure needs mesh/spatially variant motion, rolling-shutter handling, or foreground rejection | Mark as model boundary if global affine cannot explain the failure |
| Running or high-motion clips look bad | `internal:eis_algorithm_topic`, `public:bundled_camera_paths`, `public:meshflow` | Scene role, degradation policy, and whether the clip belongs to challenge rather than main gate | Do not optimize Running if it hurts Regular |
| Weak texture, sky, wall, water, or repeated texture breaks motion estimation | `internal:orb_eis_application`, `public:opencv_videostab`, `public:nvidia_vpi_samples` | Feature/flow fallback, confidence gating, grid sampling, RANSAC thresholds | Stop after one concrete confidence/fallback fix if evidence remains ambiguous |
| Foreground/parallax dominates the estimated affine motion | `public:bundled_camera_paths`, `public:meshflow`, `internal:eis_algorithm_topic` | Foreground mask, mesh model, local motion rejection, scene gate downgrade | Do not force a single global affine success claim |
| Black border, crop, or FOV trade-off blocks quality | `internal:eis_cis_solution`, `public:l1_optimal_camera_paths`, `public:vidstab_ffmpeg` | Crop budget, dynamic zoom, fixed vs adaptive crop, FOV loss wording | Stop if FOV gain creates hard black-border failures |
| Blur or detail loss becomes the main complaint | `internal:clarity_motion_quality`, then current visual evidence | Whether blur is caused by crop scale, interpolation, sharpen, motion blur, or codec | Do not claim clarity improvement without side-by-side review |
| VPI backend support or operator usage is unclear | `public:nvidia_vpi_samples` | Supported backends, data formats, synchronization/readback costs | Do not claim acceleration until same-input Jetson timing exists |
| GStreamer/NVMM/NVDEC/NVENC dataflow is unclear | `public:jetson_accelerated_gstreamer`, `public:jetson_multimedia_api` | Memory path, hardware decoder/encoder path, format conversion, zero-copy limits | Keep it a performance/dataflow loop, not a quality loop |
| Agent keeps repeating the same failed action | `harness_integration.md` | Stop/recovery rule and next evidence type | Stop and summarize blocker instead of another retry |

## Source Key

Public source cards live in [public_sources.md](public_sources.md).

Internal source keys are defined in `.local_knowledge/internal_reference_index.md`
and point to original local Typora files. Keep that file local-only.
