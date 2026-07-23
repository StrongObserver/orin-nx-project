# Harness / Loop Anti-Retreat Review - 2026-07-18

## Problem

The project exposed a Loop/Harness design flaw:

```text
Negative evidence was too easy to interpret as a reason to stop the next core
engineering track and polish the current stable baseline instead.
```

That is wrong for this project.

A stable CPU baseline is a checkpoint for Git, comparison, rollback, and
before/after evidence. It is not the final project target.

## Root Cause

The old rules were strong on:

- reproducibility;
- avoiding overclaim;
- separating Regular from Challenge;
- preserving review evidence;
- stopping blind retries.

They were weak on:

- forcing a next exploration route after a negative result;
- distinguishing "stop this bad action" from "stop the project track";
- keeping the three unfinished core tracks visible after a stable baseline;
- preventing documentation loops from replacing core engineering progress.

## Correct Rule

Negative results must be converted into routing evidence.

| Negative result | Correct meaning | Next route |
|---|---|---|
| VPI backend swap is slower | Bad placement/dataflow, not proof VPI is useless | Backend support table, module benchmark, conversion/readback diagnosis |
| Python appsink/appsrc is costly | Python round trip is bad, not proof NVMM/GStreamer is useless | Non-Python NVMM/CUDA/C++ pipeline route |
| Challenge clips fail | Current global warp has limits | Keep boundary evidence, explore mesh/grid only under a new contract |
| CPU baseline is stable | Checkpoint exists | Preserve it, then continue unfinished core tracks |

## Active Core Tracks

The project is not complete until these are either completed or explicitly
descoped by the user:

1. VPI backend validation and heterogeneous acceleration.
2. Device-side dataflow profiling around MMAPI/NVDEC/NVENC, NvBufSurface,
   NvBuffer, VPI wrappers, sync, and transform sandwich.
3. Hardware decode/encode, perf/watt, final architecture/result table, and
   NVTX/Nsight timeline evidence.

## Files Updated

```text
configs/harness/loop_profiles.json
scripts/harness_runner.py
docs/loop_engineering_v2.md
docs/harness_engineering_v1.md
```

## New Control-Plane Check

Run:

```powershell
py -3.12 scripts\harness_runner.py check-loop-rules
```

This verifies that the anti-retreat guardrails remain machine-readable:

- stable checkpoint is not terminal goal;
- documentation loop cannot replace core progress;
- negative result is evidence, not terminal state;
- active core tracks are declared;
- performance-loop recovery routes exist for slow VPI swaps, costly Python
  dataflow, and operator speedup that does not become end-to-end speedup.

## Practical Next Rule

After a stable baseline or negative result, the next task must answer:

```text
Which unfinished core track does this route to next?
```

If the answer is only "write better docs" while measured dataflow/profiling
evidence is missing, the loop is wrong. If the answer is "compress measured
results into final tables, diagrams, and interview wording," the loop is valid
only when it links to existing evidence and does not invent a larger claim.
