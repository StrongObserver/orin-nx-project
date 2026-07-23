from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


REMAP_RE = re.compile(
    r"VPI_(?:EGLIMAGE_(?:DYNAMIC_)?REMAP(?:_STREAM_REUSE)?|NVBUFFER_(?:DYNAMIC_)?REMAP)_PAD_CROP\s+frame=(?P<frame>\d+)\s+"
    r"mode=(?P<mode>\S+)\s+scratch_width=(?P<scratch_width>\d+)\s+"
    r"scratch_height=(?P<scratch_height>\d+)\s+elapsed_ms=(?P<elapsed>[0-9.]+)\s+"
    r"avg_ms=(?P<avg>[0-9.]+)"
)

STAGE_RE = re.compile(
    r"(?:REMAP|NVBUFFER_REMAP)_PAD_CROP_STAGE_TIMING\s+frame=(?P<frame>\d+)\s+"
    r"main_width=(?P<main_width>\d+)\s+main_height=(?P<main_height>\d+)\s+"
    r"scratch_width=(?P<scratch_width>\d+)\s+scratch_height=(?P<scratch_height>\d+)\s+"
    r"input_transform_ms=(?P<input>[0-9.]+)\s+(?:payload_create_ms=(?P<payload>[0-9.]+)\s+)?wrapper_call_ms=(?P<wrapper>[0-9.]+)\s+"
    r"output_transform_ms=(?P<output>[0-9.]+)\s+total_stage_ms=(?P<total>[0-9.]+)\s+"
    r"avg_total_stage_ms=(?P<avg>[0-9.]+)"
)

PAYLOAD_RE = re.compile(
    r"VPI_(?:REMAP|NVBUFFER_REMAP|DYNAMIC_REMAP|NVBUFFER_DYNAMIC_REMAP)_PAD_CROP_PAYLOAD_READY(?:\s+frame=(?P<frame>\d+))?\s+mode=(?P<mode>\S+)\s+(?:payload_create_ms=(?P<payload>[0-9.]+)\s+)?"
    r"width=(?P<width>\d+)\s+height=(?P<height>\d+)\s+"
    r"grid_width=(?P<grid_width>\d+)\s+grid_height=(?P<grid_height>\d+)\s+"
    r"points=(?P<points>\S+)"
)

SCRATCH_RE = re.compile(
    r"(?:REMAP|NVBUFFER_REMAP)_PAD_CROP_SCRATCH_ALLOC\s+main_width=(?P<main_width>\d+)\s+"
    r"main_height=(?P<main_height>\d+)\s+scratch_width=(?P<scratch_width>\d+)\s+"
    r"scratch_height=(?P<scratch_height>\d+)"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize Remap pad/crop timing lines from MMAPI logs.")
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    remap_rows: list[dict[str, str | int]] = []
    stage_rows: list[dict[str, str | int]] = []
    payload: dict[str, str] = {}
    scratch: dict[str, str] = {}

    for line in args.log.read_text(encoding="utf-8", errors="replace").splitlines():
        if match := SCRATCH_RE.search(line):
            scratch = match.groupdict()
            continue
        if match := PAYLOAD_RE.search(line):
            payload = match.groupdict()
            continue
        if match := REMAP_RE.search(line):
            remap_rows.append(
                {
                    "frame": int(match.group("frame")),
                    "mode": match.group("mode"),
                    "scratch_width": int(match.group("scratch_width")),
                    "scratch_height": int(match.group("scratch_height")),
                    "elapsed_ms": f"{float(match.group('elapsed')):.6f}",
                    "running_avg_ms": f"{float(match.group('avg')):.6f}",
                }
            )
            continue
        if match := STAGE_RE.search(line):
            stage_rows.append(
                {
                    "frame": int(match.group("frame")),
                    "main_width": int(match.group("main_width")),
                    "main_height": int(match.group("main_height")),
                    "scratch_width": int(match.group("scratch_width")),
                    "scratch_height": int(match.group("scratch_height")),
                    "input_transform_ms": f"{float(match.group('input')):.6f}",
                    "payload_create_ms": f"{float(match.group('payload') or 0.0):.6f}",
                    "wrapper_call_ms": f"{float(match.group('wrapper')):.6f}",
                    "output_transform_ms": f"{float(match.group('output')):.6f}",
                    "total_stage_ms": f"{float(match.group('total')):.6f}",
                    "running_avg_total_stage_ms": f"{float(match.group('avg')):.6f}",
                }
            )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    remap_csv = args.out_dir / "remap_timing_samples.csv"
    with remap_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["frame", "mode", "scratch_width", "scratch_height", "elapsed_ms", "running_avg_ms"],
        )
        writer.writeheader()
        writer.writerows(remap_rows)

    stage_csv = args.out_dir / "stage_timing_samples.csv"
    with stage_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "frame",
                "main_width",
                "main_height",
                "scratch_width",
                "scratch_height",
                "input_transform_ms",
                "payload_create_ms",
                "wrapper_call_ms",
                "output_transform_ms",
                "total_stage_ms",
                "running_avg_total_stage_ms",
            ],
        )
        writer.writeheader()
        writer.writerows(stage_rows)

    last_remap = remap_rows[-1] if remap_rows else {}
    last_stage = stage_rows[-1] if stage_rows else {}
    summary = {
        "log": str(args.log),
        "mode": str(payload.get("mode") or last_remap.get("mode", "")),
        "main_width": scratch.get("main_width") or str(last_stage.get("main_width", "")),
        "main_height": scratch.get("main_height") or str(last_stage.get("main_height", "")),
        "scratch_width": scratch.get("scratch_width") or payload.get("width") or str(last_stage.get("scratch_width", "")),
        "scratch_height": scratch.get("scratch_height") or payload.get("height") or str(last_stage.get("scratch_height", "")),
        "grid_width": payload.get("grid_width", ""),
        "grid_height": payload.get("grid_height", ""),
        "points": payload.get("points", ""),
        "remap_sample_count": len(remap_rows),
        "stage_sample_count": len(stage_rows),
        "last_sample_frame": last_stage.get("frame", last_remap.get("frame", 0)),
        "last_remap_elapsed_ms": last_remap.get("elapsed_ms", "0.000000"),
        "last_remap_running_avg_ms": last_remap.get("running_avg_ms", "0.000000"),
        "last_input_transform_ms": last_stage.get("input_transform_ms", "0.000000"),
        "last_payload_create_ms": last_stage.get("payload_create_ms", "0.000000"),
        "last_wrapper_call_ms": last_stage.get("wrapper_call_ms", "0.000000"),
        "last_output_transform_ms": last_stage.get("output_transform_ms", "0.000000"),
        "last_total_stage_ms": last_stage.get("total_stage_ms", "0.000000"),
        "last_running_avg_total_stage_ms": last_stage.get("running_avg_total_stage_ms", "0.000000"),
    }
    summary_csv = args.out_dir / "summary.csv"
    with summary_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary.keys()))
        writer.writeheader()
        writer.writerow(summary)

    summary_md = args.out_dir / "summary.md"
    summary_md.write_text(
        "\n".join(
            [
                "# Remap Pad/Crop Log Summary",
                "",
                f"- log: `{args.log}`",
                f"- mode: {summary['mode']}",
                f"- main: {summary['main_width']}x{summary['main_height']}",
                f"- scratch: {summary['scratch_width']}x{summary['scratch_height']}",
                f"- grid: {summary['grid_width']}x{summary['grid_height']} ({summary['points']} points)",
                f"- last sample frame: {summary['last_sample_frame']}",
                f"- last Remap elapsed: {summary['last_remap_elapsed_ms']} ms",
                f"- last Remap running avg: {summary['last_remap_running_avg_ms']} ms",
                f"- last payload create: {summary['last_payload_create_ms']} ms",
                f"- last total stage: {summary['last_total_stage_ms']} ms",
                f"- last stage running avg: {summary['last_running_avg_total_stage_ms']} ms",
                "",
                "This summarizes only the Remap pad/crop diagnostic log. It is not EIS quality or end-to-end pipeline latency.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    print(f"remap_csv: {remap_csv}")
    print(f"stage_csv: {stage_csv}")
    print(f"summary_csv: {summary_csv}")
    print(f"summary_md: {summary_md}")
    print(f"mode: {summary['mode']}")
    print(f"last_sample_frame: {summary['last_sample_frame']}")
    print(f"last_remap_running_avg_ms: {summary['last_remap_running_avg_ms']}")
    print(f"last_running_avg_total_stage_ms: {summary['last_running_avg_total_stage_ms']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
