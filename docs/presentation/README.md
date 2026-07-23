# Presentation Guide

Read these files in order for a short interview-style walkthrough. The current
positioning is heterogeneous video compute and device-side dataflow
optimization; EIS is the representative workload, not the whole project
identity.

1. `final_benchmark_table.md`
   - Compact final table for quality, CPU timing, VPI module speed/perf-watt,
     MMAPI device-stage timing, NvBuffer pair, and Nsight attribution.

2. `dataflow_architecture.md`
   - Current quality-to-device dataflow, memory-format boundary, and accepted
     C++ MMAPI/VPI/NVENC path.

3. `claim_boundary.md`
   - Safe claims, forbidden claims, and resume/interview wording.

4. `assets/device_dataflow_architecture.svg`
   - Visual dataflow diagram for CPU matrix generation, MMAPI/VPI/NVENC, and
     profiling bottlenecks.

5. `assets/evidence_stack.svg`
   - Layered evidence stack from harness checks to portfolio wording.

6. `../reproducibility_guide.md`
   - Layered commands and expected outputs for control plane, quality, VPI,
     MMAPI, Nsight, and lifecycle evidence.

7. `../evidence_reader_path.md`
   - Reader-oriented route from common questions to the right evidence.

8. `project_story.md`
   - Project motivation, current result, and three-minute explanation.

9. `baseline_and_metrics.md`
   - Regular gate, dual baseline wording, and metric meanings.

10. `performance_optimization.md`
   - How `estimate_scale=0.5 + feature_grid_size=16` became the Regular
     performance baseline.

11. `hardware_acceleration_boundary.md`
   - VPI module acceleration, full-pipeline negative result, GStreamer/NVMM
     dataflow boundary, the current MMAPI/VPI/NVENC device-side warp path, and
     the NvBuffer pair, stream-only reuse, and C++ Remap follow-ups.

12. `../vpi_remap_cpp_probe_2026-07-23.md`
   - C++ Remap/WarpMap module probe after Python Remap native abort; includes
     OpenCV vs VPI CUDA timing and NV12_ER feasibility.

13. `../nsight_device_stage_profile_result_2026-07-23.md`
   - Completed NVTX/Nsight result: wrapper/sync/transform/lifecycle cost
     dominates, and P6/P7 scheduler work is not triggered.

14. `../device_stage_lifecycle_perf_result_2026-07-23.md`
   - Stream-only reuse lifecycle follow-up with a 10-run same-source repeat.

15. `resume_bullets.md`
   - Short, medium, and long resume wording with claim boundaries.

16. `../../configs/harness/contracts/final_evidence_package_closeout_v1.json`
   - Current final evidence package closeout contract.

17. `../regular_gate_residual_closed_loop_2026-07-21.md`
   - The accepted `resid_r15_s07` Regular-gate quality recovery result.

18. `../regular_gate_nvbuffer_pair_resid_2026-07-23.md`
   - Format-matched NvBuffer pair follow-up that preserves the quality anchor
     and gives a small measured device-stage gain.

19. `../device_stage_demo_handoff_2026-07-19.md`
   - Accepted device-side stage demo, review assets, result table, and claim
     boundaries.

20. `../hybrid_realtime_eis_plan_2026-07-19.md`
   - Hybrid real-time plan, updated to use Regular05 source_to_dest for
     EIS-quality work.

21. `../hybrid_realtime_matrix_handoff_2026-07-19.md`
   - Historical outdoor-car mock/FIFO/live handoff result; dataflow smoke only.

22. `../layered_artifact_diagnosis_2026-07-19.md`
   - Why outdoor-car is dataflow smoke only, and how Regular05 should be used
     for EIS quality review.

23. `../../configs/harness/contracts/presentation_closeout_v1.json`
   - Previous closeout contract, superseded by Nsight and final evidence
     package closeout.

24. `../../configs/harness/contracts/regular05_hybrid_matrix_handoff_v1.json`
   - Current Regular05 source_to_dest handoff contract and quality boundary.

25. `challenge_boundary.md`
   - Operating envelope: where Regular succeeds and where challenge sets expose
     model limits.

26. `interview_qna.md`
   - Concise answers to likely interview questions.

Do not present local `results/` videos or CSV files as repository artifacts.
They are evidence paths for local review, not files intended for GitHub.
