# Orin NX Heterogeneous Video Compute External Knowledge Base

## Purpose

This knowledge base is a small routing layer for the Orin NX heterogeneous video
compute project. EIS remains the representative workload, so classic
stabilization references are still useful, but the current project target also
includes VPI/CUDA modules, MMAPI/NVDEC/NVENC dataflow, memory layout,
profiling, and perf/watt evidence. This is not a second progress log and not a
dump of every useful article.

Use this knowledge base only when a real blocker appears:

- workload quality does not improve after a scoped attempt;
- metrics improve but visual review vetoes the result;
- a change helps `nus_running_gate_v1` while hurting `nus_regular_gate_v1`;
- VPI, CUDA, GStreamer, NVMM, NVDEC, NVENC, Nsight, or NVTX usage is unclear;
- motion estimation fails because of foreground, weak texture, parallax, rolling
  shutter, or strong user intent motion;
- an agent cannot explain why a change helped and what it costs.

Do not load the whole knowledge base before every run. Start with
`routing.md`, then open only the source card that matches the blocker.

## Boundary

Public and commit-safe material lives under this directory.

Company or internship notes are not copied here. Their local-only routing index
lives under:

```text
.local_knowledge/internal_reference_index.md
```

That directory is ignored by Git. If a future agent needs the internal notes,
it should read the local index, then open the original Typora path on this
machine. Do not paste internal original text into public GitHub outputs.

## Entry Points

- [routing.md](routing.md): blocker-to-reference routing table.
- [public_sources.md](public_sources.md): curated public repos, papers, and
  official samples.
- [harness_integration.md](harness_integration.md): how the knowledge base plugs
  into the existing Harness/Loop system.

## Current Project Fit

The current main project boundary is:

- `nus_regular_gate_v1` is the main quality gate.
- `nus_running_gate_v1` is a challenge and failure-boundary gate.
- `regular05_perf_gate` is same-input Jetson performance evidence only.
- The current frozen CPU baseline is `regular_gate05 + lp_rigid_strength080_dynzoom106`.
- Same-input VPI backend replacement is a measured boundary result, not a
  full-pipeline acceleration result, for the current 640x360 Python path.
- The refined project target is heterogeneous video compute and device-side
  dataflow optimization, not another stabilization-parameter sweep.
- The preferred next technical reference area is Nsight/NVTX plus Jetson
  MMAPI/VPI/NVENC dataflow, unless a real quality blocker is reopened by the
  user.

The knowledge base should reinforce those boundaries. It should not reopen a
blind LP weight sweep or turn Running into the main success target.
