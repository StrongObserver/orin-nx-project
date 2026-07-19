# Presentation Guide

Read these files in order for a short interview-style walkthrough:

1. `project_story.md`
   - Project motivation, current result, and three-minute explanation.

2. `baseline_and_metrics.md`
   - Regular gate, dual baseline wording, and metric meanings.

3. `performance_optimization.md`
   - How `estimate_scale=0.5 + feature_grid_size=16` became the Regular
     performance baseline.

4. `hardware_acceleration_boundary.md`
   - VPI module acceleration, full-pipeline negative result, GStreamer/NVMM
     dataflow boundary, and the current MMAPI/VPI/NVENC device-side warp path.

5. `../device_stage_demo_handoff_2026-07-19.md`
   - Accepted device-side stage demo, review assets, result table, and claim
     boundaries.

6. `../hybrid_realtime_eis_plan_2026-07-19.md`
   - Next-stage hybrid real-time matrix-handoff plan.

7. `challenge_boundary.md`
   - Operating envelope: where Regular succeeds and where challenge sets expose
     model limits.

8. `interview_qna.md`
   - Concise answers to likely interview questions.

Do not present local `results/` videos or CSV files as repository artifacts.
They are evidence paths for local review, not files intended for GitHub.
