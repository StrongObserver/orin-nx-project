# Harness Integration For The Knowledge Base

## Design Rule

The knowledge base is a recovery mechanism, not a default context load.

```text
Harness first, knowledge base only when the loop is stuck or entering a new
technical domain.
```

Each real experiment still starts from the existing Harness flow:

```powershell
py -3.12 scripts\harness_runner.py doctor
py -3.12 scripts\harness_runner.py check-claim --gate-id nus_running_gate_v1 --claim main_gate_success_rate
py -3.12 scripts\harness_runner.py print-contract
```

## When To Invoke

Invoke the knowledge base when one of these stop or recovery rules fires:

| Harness signal | Knowledge-base action |
|---|---|
| Two scoped attempts fail or trade one metric for worse visual quality | Open [routing.md](routing.md), choose the matching blocker, and read one source card |
| A change helps `nus_running_gate_v1` while hurting Regular | Read `public:bundled_camera_paths` / `public:meshflow`, then reclassify the clip or stop |
| Visual veto: frame shift, rollback, jello, local pull, or unacceptable blur | Read the matched quality or model-boundary card; do not argue from metrics alone |
| VPI/CUDA/GStreamer/NVMM usage becomes the blocker | Read the relevant NVIDIA source card before implementing |
| The next change would require gyro, mesh, rolling-shutter, or major dataflow work | Treat it as a scope fork; summarize evidence before coding |

## Done Contract Extension

When a future Done Contract needs external knowledge, add only a small reference
field instead of pasting source content:

```json
{
  "knowledge_base_refs": [
    "public:l1_optimal_camera_paths",
    "internal:eis_algorithm_topic"
  ],
  "knowledge_base_trigger": "LP smoothing failed visual veto after one scoped attempt"
}
```

This keeps contracts compact and auditable.

## Loop Rule

The loop should use the knowledge base like this:

1. Define the blocker in one sentence.
2. Open [routing.md](routing.md).
3. Open at most two source cards or internal summaries.
4. Extract one concrete idea, one risk, and one verifier.
5. Either write/update a Done Contract or stop and report the boundary.

Do not open many papers or repos in one loop. If more than two sources seem
necessary, the task is probably not scoped tightly enough.

## Internal Notes Boundary

Internal Typora notes may guide local decisions, but public project files should
only contain:

- high-level, non-sensitive routing labels;
- local paths already known to this machine;
- conclusions phrased in project terms;
- no copied proprietary text, screenshots, private links, tokens, or credentials.

The local-only index is:

```text
.local_knowledge/internal_reference_index.md
```

It is ignored by Git. If that file is missing, rebuild it from the original
Typora paths listed in the project prompt rather than copying internal content
into this directory.

## Current Project Boundary

This knowledge-base work does not replace the Harness/Loop boundary:

```text
Current CPU baseline evidence:
results/evidence/20260718_jetson_regular05_perf/

Current frozen config:
lp_rigid + stabilization_strength=0.80 + crop90 + lanczos + sharpen0.25 + dynzoom1.06

Current backend boundary:
VPI CPU/CUDA/VIC backend swaps are slower than OpenCV CPU in the 640x360 Python full pipeline.
```

Do not start another LP parameter sweep simply because new references exist. Use
the knowledge base only if the next scoped loop hits a real blocker, such as
motion-estimation quality regression, unclear high-resolution VPI module usage,
or a GStreamer/NVMM dataflow question.
