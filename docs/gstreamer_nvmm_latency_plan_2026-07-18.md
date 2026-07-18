# GStreamer / NVMM Latency Plan - 2026-07-18

## Purpose

The current EIS CPU baseline is good enough to stop local parameter tuning. The
next hardware-facing step should measure Jetson video dataflow latency before any
attempt to integrate GStreamer into the stabilizer.

This plan pairs with:

```text
configs/harness/contracts/gst_nvmm_decode_convert_latency_v1.json
```

## Starting Point

Minimum probe already passed:

```text
filesrc -> qtdemux -> h264parse -> nvv4l2decoder -> NVMM -> nvvidconv -> BGRx -> fakesink
```

Observed 1080p run:

```text
Execution ended after 0:00:01.601523038
```

Available Jetson plugins:

```text
gst-launch-1.0 1.16.3
nvvidconv
nvv4l2decoder
nvv4l2h264enc
```

## Loop Boundary

This is a dataflow loop, not an EIS algorithm loop.

Allowed:

- change sink type;
- change caps around NVMM and BGRx;
- compare fakesink, file output, and CPU readback boundary;
- repeat runs to get stable timing.

Frozen:

- do not modify `src/cpu_stabilize.py`;
- do not change Regular baseline configs;
- do not claim EIS acceleration;
- do not install system packages without approval.

## Proposed Subtasks

### P3.1 Repeat Minimum Probe

Run the current decode/NVMM/convert/fakesink pipeline 3 times on 1080p.

Record:

```text
exit code
EOS reached
wall time
```

Pass condition: all runs reach EOS.

### P3.2 Pure Hardware Decode / Convert / Encode Boundary

Run a no-CPU-processing path to establish the upper bound for hardware dataflow:

```text
filesrc -> qtdemux -> h264parse -> nvv4l2decoder -> nvvidconv -> nvv4l2h264enc -> qtmux -> filesink
```

Record:

```text
exit code
EOS reached
wall time
output file exists
input frames / output duration if available
```

Purpose: measure the hardware path before introducing CPU readback.

### P3.3 CPU Readback Boundary

Run a path that explicitly leaves NVMM/system hardware flow:

```text
nvv4l2decoder -> NVMM -> nvvidconv -> video/x-raw,format=BGRx -> CPU-readable sink
```

Record:

```text
wall time
average frame time if a callback or frame counter is available
whether caps negotiation forced a copy
```

Purpose: decide whether CPU readback dominates before EIS integration.

### P3.4 File Output Boundary

Replace `fakesink` with an encoded or raw file output path only if the minimal
probe is stable.

Purpose: measure whether output/encoding dominates.

Pass condition: output file exists and command reaches EOS.

## Expected Outputs

```text
results/gst_nvmm_decode_convert_latency_<YYYYMMDD>/summary.md
results/gst_nvmm_decode_convert_latency_<YYYYMMDD>/commands.txt
results/gst_nvmm_decode_convert_latency_<YYYYMMDD>/run_log_*.txt
```

## How To Present It

Good wording:

```text
I verified that the Jetson hardware decode and NVMM conversion path is available.
The next step is measuring where CPU readback or encoding cost appears before
integrating it into EIS.
```

Avoid:

```text
GStreamer accelerated the EIS pipeline.
The project has zero-copy EIS.
NVMM integration is complete.
```

## Stop Rules

Stop and report if:

- caps negotiation fails after one mechanical fix;
- required NVIDIA plugin is missing;
- the next step requires system package installation;
- the next step requires rewriting the EIS pipeline instead of measuring the
  dataflow boundary.
