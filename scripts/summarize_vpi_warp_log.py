from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


LINE_RE = re.compile(
    r"VPI_(?:TRANSCODE|ENC|EGLIMAGE(?:_(?:REUSE|STREAM_REUSE))?)_WARP\s+frame=(?P<frame>\d+)\s+"
    r"elapsed_ms=(?P<elapsed>[0-9.]+)\s+avg_ms=(?P<avg>[0-9.]+)"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize VPI warp timing lines from MMAPI patch logs.")
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
                "elapsed_ms": f"{float(match.group('elapsed')):.6f}",
                "running_avg_ms": f"{float(match.group('avg')):.6f}",
            }
        )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    timing_csv = args.out_dir / "vpi_warp_timing_samples.csv"
    with timing_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["frame", "elapsed_ms", "running_avg_ms"])
        writer.writeheader()
        writer.writerows(rows)

    final_avg = float(rows[-1]["running_avg_ms"]) if rows else 0.0
    max_sample_frame = int(rows[-1]["frame"]) if rows else 0
    summary = {
        "log": str(args.log),
        "timing_sample_count": len(rows),
        "last_sample_frame": max_sample_frame,
        "last_running_avg_ms": f"{final_avg:.6f}",
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
                "# VPI Warp Log Summary",
                "",
                f"- log: `{args.log}`",
                f"- timing sample count: {len(rows)}",
                f"- last sample frame: {max_sample_frame}",
                f"- last running average: {final_avg:.6f} ms",
                "",
                "This summarizes only the VPI warp timing lines printed by the MMAPI patch. It is not end-to-end pipeline latency.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    print(f"timing_csv: {timing_csv}")
    print(f"summary_csv: {summary_csv}")
    print(f"summary_md: {summary_md}")
    print(f"timing_sample_count: {len(rows)}")
    print(f"last_sample_frame: {max_sample_frame}")
    print(f"last_running_avg_ms: {final_avg:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
