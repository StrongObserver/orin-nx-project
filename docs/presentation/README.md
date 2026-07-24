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

8. `../backend_decision_table_2026-07-24.md`
   - One-page decision matrix for runnable, useful, negative, and deferred
     backend routes.

9. `../device_stage_stability_p99_repeat_2026-07-24.md`
   - Short-repeat p50/p95/p99 boundary for stream-only reuse and NvBuffer pair.

10. `../cuda_mmapi_route_recovery_2026-07-24.md`
   - CUDA-MMAPI route recovery after the CUDA-owned bridge negative closeout.

11. `../producer_boundary_and_next_route_2026-07-24.md`
   - Producer/FIFO/live boundary and why full real-time EIS remains unclaimed.

12. `../regular05_startup_black_fix_closeout_2026-07-24.md`
   - Objective startup black fix candidate and pending human-acceptance boundary.

13. `project_story.md`
   - Project motivation, current result, and three-minute explanation.

14. `baseline_and_metrics.md`
   - Regular gate, dual baseline wording, and metric meanings.

15. `performance_optimization.md`
   - How `estimate_scale=0.5 + feature_grid_size=16` became the Regular
     performance baseline.

16. `hardware_acceleration_boundary.md`
   - VPI module acceleration, full-pipeline negative result, GStreamer/NVMM
     dataflow boundary, the current MMAPI/VPI/NVENC device-side warp path, and
     the NvBuffer pair, stream-only reuse, and C++ Remap follow-ups.

17. `../vpi_remap_cpp_probe_2026-07-23.md`
   - C++ Remap/WarpMap module probe after Python Remap native abort; includes
     OpenCV vs VPI CUDA timing and NV12_ER feasibility.

18. `../remap_mmapi_integration_probe_2026-07-23.md`
   - Minimal MMAPI/VPI/NVENC scratch-stage Remap insertion; records the
     original 640x360 WarpGrid size boundary and the 640x368 diagnostic path.

19. `../remap_native_size_pad_crop_probe_2026-07-23.md`
   - Native 640x360 main-chain pad/crop closure for the 640x368 VPI Remap
     scratch-stage requirement.

20. `../nsight_device_stage_profile_result_2026-07-23.md`
   - Completed NVTX/Nsight result: wrapper/sync/transform/lifecycle cost
     dominates, and P6/P7 scheduler work is not triggered.

21. `../device_stage_lifecycle_perf_result_2026-07-23.md`
   - Stream-only reuse lifecycle follow-up with a 10-run same-source repeat.

22. `resume_bullets.md`
   - Short, medium, and long resume wording with claim boundaries.

23. `../../configs/harness/contracts/final_evidence_package_closeout_v1.json`
   - Current final evidence package closeout contract.

24. `../regular_gate_residual_closed_loop_2026-07-21.md`
   - The accepted `resid_r15_s07` Regular-gate quality recovery result.

25. `../regular_gate_nvbuffer_pair_resid_2026-07-23.md`
   - Format-matched NvBuffer pair follow-up that preserves the quality anchor
     and gives a small measured device-stage gain.

26. `../device_stage_demo_handoff_2026-07-19.md`
   - Accepted device-side stage demo, review assets, result table, and claim
     boundaries.

27. `../hybrid_realtime_eis_plan_2026-07-19.md`
   - Hybrid real-time plan, updated to use Regular05 source_to_dest for
     EIS-quality work.

28. `../hybrid_realtime_matrix_handoff_2026-07-19.md`
   - Historical outdoor-car mock/FIFO/live handoff result; dataflow smoke only.

29. `../layered_artifact_diagnosis_2026-07-19.md`
   - Why outdoor-car is dataflow smoke only, and how Regular05 should be used
     for EIS quality review.

30. `../../configs/harness/contracts/presentation_closeout_v1.json`
   - Previous closeout contract, superseded by Nsight and final evidence
     package closeout.

31. `../../configs/harness/contracts/regular05_hybrid_matrix_handoff_v1.json`
   - Current Regular05 source_to_dest handoff contract and quality boundary.

32. `challenge_boundary.md`
   - Operating envelope: where Regular succeeds and where challenge sets expose
     model limits.

33. `interview_qna.md`
   - Concise answers to likely interview questions.

Do not present local `results/` videos or CSV files as repository artifacts.
They are evidence paths for local review, not files intended for GitHub.
