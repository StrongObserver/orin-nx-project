# Orin NX EIS External Knowledge Base

## Purpose

This knowledge base is a small routing layer for the Orin NX EIS project. It is
not a second progress log and not a dump of every useful article. Its job is to
help future agents break out of local parameter loops by pointing them to the
right outside reference when the current harness evidence says the project is
stuck.

Use this knowledge base only when a real blocker appears:

- quality does not improve after a scoped attempt;
- metrics improve but visual review vetoes the result;
- a change helps `nus_running_gate_v1` while hurting `nus_regular_gate_v1`;
- VPI, CUDA, GStreamer, NVMM, NVDEC, or NVENC usage is unclear;
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

The knowledge base should reinforce those boundaries. It should not reopen a
blind LP weight sweep or turn Running into the main success target.
