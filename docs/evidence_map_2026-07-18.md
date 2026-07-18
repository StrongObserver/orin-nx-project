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
| Presentation guide | `docs/presentation/README.md` | Reading order for interview-style docs | tracked |
| One-page summary | `docs/presentation/one_page_summary.md` | Fast project overview | tracked |

Do not commit ignored evidence unless a future task explicitly selects a small
representative artifact.
