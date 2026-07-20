from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


LINE_RE = re.compile(
    r"EGL_STAGE_TIMING\s+frame=(?P<frame>\d+)\s+"
    r"input_transform_ms=(?P<input>[0-9.]+)\s+"
    r"wrapper_call_ms=(?P<wrapper>[0-9.]+)\s+"
    r"output_transform_ms=(?P<output>[0-9.]+)\s+"
    r"total_stage_ms=(?P<total>[0-9.]+)\s+"
    r"avg_total_stage_ms=(?P<avg>[0-9.]+)"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize EGLImage-wrapper stage timing lines from MMAPI logs.")
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows: list[dict[str, str | int]] = []
    for line in args.log.read_text(encoding="utf-8", errors="replace").splitlines():
        match = LINE_RE.search(line)
        if not match:
            continue
        rows.append(
            {
                "frame": int(match.group("frame")),
                "input_transform_ms": f"{float(match.group('input')):.6f}",
                "wrapper_call_ms": f"{float(match.group('wrapper')):.6f}",
                "output_transform_ms": f"{float(match.group('output')):.6f}",
                "total_stage_ms": f"{float(match.group('total')):.6f}",
                "running_avg_total_stage_ms": f"{float(match.group('avg')):.6f}",
            }
        )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    samples_csv = args.out_dir / "egl_stage_timing_samples.csv"
    with samples_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "frame",
                "input_transform_ms",
                "wrapper_call_ms",
                "output_transform_ms",
                "total_stage_ms",
                "running_avg_total_stage_ms",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "log": str(args.log),
        "timing_sample_count": len(rows),
        "last_sample_frame": int(rows[-1]["frame"]) if rows else 0,
        "last_input_transform_ms": rows[-1]["input_transform_ms"] if rows else "0.000000",
        "last_wrapper_call_ms": rows[-1]["wrapper_call_ms"] if rows else "0.000000",
        "last_output_transform_ms": rows[-1]["output_transform_ms"] if rows else "0.000000",
        "last_total_stage_ms": rows[-1]["total_stage_ms"] if rows else "0.000000",
        "last_running_avg_total_stage_ms": rows[-1]["running_avg_total_stage_ms"] if rows else "0.000000",
    }
    summary_csv = args.out_dir / "summary.csv"
    with summary_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary.keys()))
        writer.writeheader()
        writer.writerow(summary)

    print(f"samples: {samples_csv}")
    print(f"summary: {summary_csv}")
    print(f"timing_sample_count: {summary['timing_sample_count']}")
    print(f"last_sample_frame: {summary['last_sample_frame']}")
    print(f"last_running_avg_total_stage_ms: {summary['last_running_avg_total_stage_ms']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
