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
| Same-source device review video, standardized name | `C:\Users\Admin\Videos\orin nx\review\performance\20260719_same_source_matrix_device_warp\20260719_device_matrix_warp_demo_sample_outdoor_car_jetson_inverse_matrix_raw_cpu_device_compare.mp4` | Same review asset with explicit demo/clip/platform/config naming | outside repo |
| Device matrix warp contract | `configs/harness/contracts/device_matrix_warp_demo_v1.json` | Claim boundary for offline matrix-driven MMAPI/VPI/NVENC warp demo | tracked |
| Device matrix warp report | `docs/device_matrix_warp_demo_2026-07-19.md` | Stage decision and reproduction chain for device-side matrix warp | tracked |
| Device stage demo handoff | `docs/device_stage_demo_handoff_2026-07-19.md` | Accepted stage demo boundary, best review assets, and claim wording | tracked |
| Hybrid real-time EIS plan | `docs/hybrid_realtime_eis_plan_2026-07-19.md` | Minimal CPU-online-estimation to MMAPI/VPI/NVENC matrix-handoff plan | tracked |
| Hybrid real-time matrix handoff contract | `configs/harness/contracts/hybrid_realtime_matrix_handoff_v1.json` | Machine-readable next-stage contract for online matrix handoff prototype | tracked |
| Hybrid matrix handoff result | `docs/hybrid_realtime_matrix_handoff_2026-07-19.md` | Mock online matrix handoff result with frame-index and latency evidence | tracked |
| Hybrid matrix handoff evidence | `results/hybrid_realtime_matrix_handoff_20260719/handoff_summary/summary.csv` | Matrix handoff fallback, frame-index alignment, and microsecond timing summary | ignored |
| Hybrid matrix handoff review video | `C:\Users\Admin\Videos\orin nx\review\performance\20260719_hybrid_realtime_matrix_handoff\20260719_hybrid_realtime_matrix_handoff_sample_outdoor_car_jetson_mock_handoff_grid_compare.mp4` | Source / CPU / accepted device / mock handoff review asset | outside repo |
| Hybrid FIFO stream handoff evidence | `results/hybrid_realtime_matrix_handoff_20260719/handoff_summary_stream/summary.csv` | Producer/consumer FIFO matrix stream fallback and frame-index summary | ignored |
| Hybrid FIFO stream review video | `C:\Users\Admin\Videos\orin nx\review\performance\20260719_hybrid_realtime_matrix_handoff\20260719_hybrid_realtime_matrix_handoff_sample_outdoor_car_jetson_stream_handoff_grid_compare.mp4` | Source / CPU / mock handoff / FIFO stream review asset | outside repo |
| Hybrid live CPU provider evidence | `results/hybrid_realtime_matrix_handoff_20260719/remote_outputs/live_cpu_provider_producer.csv`, `results/hybrid_realtime_matrix_handoff_20260719/remote_outputs/live_window_provider_producer.csv` | First live CPU matrix producer timing and feature-tracking evidence | ignored |
| Hybrid live CPU provider review video | `C:\Users\Admin\Videos\orin nx\review\performance\20260719_hybrid_realtime_matrix_handoff\20260719_hybrid_realtime_matrix_handoff_sample_outdoor_car_jetson_live_cpu_provider_grid_compare.mp4` | Source / CPU / stream baseline / live provider review asset | outside repo |
| Layered artifact diagnosis | `docs/layered_artifact_diagnosis_2026-07-19.md` | Separates outdoor-car dataflow smoke from real Regular05 EIS quality review | tracked |
| Outdoor-car layered baselines | `results/layered_artifact_diagnosis_20260719/direct_video_diff_source_vs_pass_through/correctness_summary.csv`, `results/layered_artifact_diagnosis_20260719/direct_video_diff_source_vs_vpi_identity/correctness_summary.csv` | Pass-through and VPI identity are clean enough; artifact comes from nontrivial matrix geometry on this source | ignored |
| Regular05 device replay | `results/regular05_device_replay_20260719/direct_video_diff_cpu_vs_device/correctness_summary.csv` | Device replay on real shaky Regular clip | ignored |
| Regular05 device replay review video | `C:\Users\Admin\Videos\orin nx\review\performance\20260719_regular05_device_replay\20260719_regular05_device_replay_regular_gate05_regular_6_jetson_source_cpu_device_grid.mp4` | Source / CPU / device replay review for real EIS source | outside repo |
| Regular05 fixed device replay | `results/regular05_device_replay_20260719/direct_video_diff_cpu_vs_device_forward/correctness_summary.csv` | Source-to-dest matrix convention fixes Regular05 device black-border replay | ignored |
| Regular05 bad-vs-fixed review video | `C:\Users\Admin\Videos\orin nx\review\performance\20260719_regular05_device_replay\20260719_regular05_device_replay_regular_gate05_regular_6_jetson_source_cpu_bad_fixed_grid.mp4` | Source / CPU / bad inverse / fixed source-to-dest device replay comparison | outside repo |
| Device matrix panel diff | `results/device_matrix_warp_demo_20260719/triptych_cpu_vs_device/summary.md` | 120-frame CPU panel vs device panel diff from review video; shows this is not CPU-output equivalence | ignored |
| Device matrix extracted-panel videos | `results/device_matrix_warp_demo_20260719/panels/` | Local fallback raw/cpu/device panel videos extracted from the review MP4 | ignored |
| Device matrix panel-video diff | `results/device_matrix_warp_demo_20260719/panel_video_diff_cpu_vs_device/correctness_summary.csv` | Standard two-video diff over extracted CPU/device panels | ignored |
| Device-ready matrix candidates | `results/device_matrix_warp_demo_20260719/device_matrices_inverse_*.csv` | 120-row inverse matrix candidates for the next Jetson A/B run | ignored |
| Device VPI timing summaries | `results/device_matrix_warp_demo_20260719/timing_*/summary.md` | Parsed VPI warp timing from existing MMAPI logs; module timing only | ignored |
| Device matrix A/B raw outputs | `results/device_matrix_warp_demo_20260719/remote_outputs/device_aligned_identity_first_120f.h264`, `results/device_matrix_warp_demo_20260719/remote_outputs/device_post_geometry_120f.h264` | Jetson outputs for 120-row aligned and post-geometry matrix candidates | ignored |
| Device matrix A/B direct diff | `results/device_matrix_warp_demo_20260719/direct_video_diff_cpu_vs_post_geometry/correctness_summary.csv` | Direct CPU-vs-device diff; post-geometry is current best candidate | ignored |
| Device matrix A/B review video | `C:\Users\Admin\Videos\orin nx\review\performance\20260719_same_source_matrix_device_warp\20260719_device_matrix_warp_demo_sample_outdoor_car_jetson_post_geometry_grid_compare.mp4` | Four-panel source / CPU / old inverse / post-geometry review asset | outside repo |
| Device matrix current best diff | `results/device_matrix_warp_demo_20260719/direct_video_diff_cpu_vs_post_geometry_identity_first/correctness_summary.csv` | Current best linear VPI device candidate: post-geometry plus first-frame identity | ignored |
| Device matrix identity transcode baseline | `results/device_matrix_warp_demo_20260719/jetson_diff_source_vs_identity_transcode/correctness_summary.csv` | Codec/colorspace/dataflow pixel-diff floor measured on Jetson | ignored |
| Device matrix Catmull-Rom test | `results/device_matrix_warp_demo_20260719/jetson_diff_cpu_vs_post_geometry_idfirst_catmull/correctness_summary.csv` | Catmull-Rom interpolation was slower and worse than linear | ignored |
| Device matrix current best review video | `C:\Users\Admin\Videos\orin nx\review\performance\20260719_same_source_matrix_device_warp\20260719_device_matrix_warp_demo_sample_outdoor_car_jetson_post_geometry_identity_first_grid_compare.mp4` | Four-panel review asset for current best device candidate | outside repo |
| Device evidence helper scripts | `scripts/prepare_device_matrix_csv.py`, `scripts/extract_review_panel.py`, `scripts/summarize_vpi_warp_log.py` | Prepare 120-row device matrices, extract review panels, and summarize VPI timing logs | tracked |
| Presentation guide | `docs/presentation/README.md` | Reading order for interview-style docs | tracked |
| One-page summary | `docs/presentation/one_page_summary.md` | Fast project overview | tracked |

Do not commit ignored evidence unless a future task explicitly selects a small
representative artifact.
