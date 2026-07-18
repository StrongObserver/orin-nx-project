# Evidence Map - 2026-07-18

This map points to local evidence. Most evidence files are ignored by Git.

| Evidence | Path | Purpose | Git status |
|---|---|---|---|
| Regular quality-safe baseline package | `results/evidence/20260718_jetson_regular05_perf/` | Jetson evidence for `estimate_scale=1.0`, grid12 quality-safe baseline | ignored |
| Regular performance baseline validation | `results/regular_gate_est0p5_grid16_validation_20260718/regular_gate_validation_summary.md` | Regular 5/5 objective pass for `estimate_scale=0.5`, grid16 | ignored |
| Regular review videos | `C:\Users\Admin\Videos\orin nx\review\performance\20260718_regular_gate_est0p5_grid16_validation\` | Human review evidence for Regular performance baseline | outside repo |
| Challenge boundary report | `docs/challenge_boundary_report_2026-07-18.md` | Model boundary summary for Running, QuickRotation, Parallax, Crowd | tracked |
| Challenge boundary metrics | `results/challenge_boundary_package_20260718/eval/challenge_boundary_eval.csv` | Per-clip challenge metrics | ignored |
| Challenge review videos | `C:\Users\Admin\Videos\orin nx\review\challenge\20260718_challenge_boundary_package\` | Side-by-side challenge boundary review | outside repo |
| VPI module report | `docs/vpi_warp_module_report_2026-07-18.md` | High-resolution VPI warp module speedup and correctness sanity check | tracked |
| VPI scaling data | `results/vpi_resolution_scaling_benchmark/summary.csv` | 720p to 4K VPI CUDA speedup data | ignored |
| VPI correctness sanity check | `results/vpi_highres_warp_module_demo_20260718/vpi_correctness_summary.csv` | Encoded-output difference summary | ignored |
| GStreamer readiness probe | `results/gst_nvmm_probe_20260718_summary.md` | Minimum decode/NVMM/convert/fakesink readiness | ignored |
| GStreamer latency boundary | `results/gst_nvmm_decode_convert_latency_20260718/summary.md` | fakesink, hardware encode, CPU-readable, appsink latency anchors | ignored |
| GStreamer appsrc boundary | `results/gst_appsrc_encode_boundary_20260718/summary.md` | appsink -> appsrc -> encode pass-through boundary | ignored |
| MMAPI backend probe | `results/vpi_backend_support_probe_20260718/summary.md` | Jetson VPI/GStreamer/nvpmodel backend readiness probe | ignored |
| VPI optical-flow probe | `results/vpi_optical_flow_probe_20260718/summary.md` | Dense flow and PyrLK backend support boundary | ignored |
| CUDA-memory VPI warp experiment | `results/vpi_cuda_mem_warp_20260718/warp_4k_1000.log` | C++ CUDA pitch-linear memory -> VPI CUDA warp timing without Python readback | ignored |
| MMAPI scratch-buffer transcode warp | `results/mmapi_vpi_transcode_warp_20260719/run_scratch_transform.log` | block-linear NV12 main path -> scratch -> VPI CUDA warp -> NVENC path | ignored |
| Same-source inverse-matrix device warp | `results/same_source_matrix_20260719/device_matrix_inverse.log` | offline CPU matrix -> inverse matrix -> MMAPI/VPI/NVENC device-side warp | ignored |
| Same-source device review video | `C:\Users\Admin\Videos\orin nx\review\performance\20260719_same_source_matrix_device_warp\20260719_same_source_matrix_device_warp_raw_cpu_device_compare.mp4` | raw / CPU stabilized / device inverse-matrix comparison | outside repo |
| Presentation guide | `docs/presentation/README.md` | Reading order for interview-style docs | tracked |
| One-page summary | `docs/presentation/one_page_summary.md` | Fast project overview | tracked |

Do not commit ignored evidence unless a future task explicitly selects a small
representative artifact.
