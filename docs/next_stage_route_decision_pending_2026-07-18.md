# Next-Stage Route Decision Pending - 2026-07-18

## Decision

Do not choose the next major engineering route yet.

The Regular CPU baseline has reached a clean milestone, and the next step should
be chosen with outside reference input instead of guesswork.

## Current Default Priority

This is only a default ordering, not a final decision:

```text
1. GStreamer/NVMM latency measurement
2. VPI high-resolution module demo/report
3. Challenge-set boundary package
4. Mesh/grid warp research
```

## Why Defer

- GStreamer/NVMM integration can show Jetson engineering depth, but it may turn
  into dataflow work before it produces EIS speedup.
- VPI has a clean module-level result already, but full-pipeline speedup is not
  established.
- Challenge-set packaging is valuable for boundary explanation, but it is not a
  new optimization result.
- Mesh/grid warp may address real model limits, but it is a larger algorithm
  branch and may be too heavy for the current resume stage.

## Required Input Before Final Choice

Ask internal AI or search for references using:

```text
docs/next_stage_internal_ai_prompt_2026-07-18.md
```

Useful return artifacts:

- official Jetson/GStreamer/VPI samples;
- internal or public EIS implementation references;
- dataflow commands and known pitfalls;
- minimal demo suggestions;
- recommended route for resume/interview value.

## Stop Rule

Do not start mesh/grid warp, GStreamer integration, or another performance loop
until the returned references are reviewed and a new Done Contract is written.
