from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

import numpy as np


LINE_RE = re.compile(
    r"MATRIX_HANDOFF\s+frame=(?P<frame>\d+)\s+matrix_index=(?P<matrix_index>-?\d+)\s+"
    r"fallback=(?P<fallback>[01])\s+elapsed_us=(?P<elapsed>[0-9.]+)"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize MATRIX_HANDOFF lines from MMAPI logs.")
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
                "matrix_index": int(match.group("matrix_index")),
                "fallback": int(match.group("fallback")),
                "elapsed_us": f"{float(match.group('elapsed')):.6f}",
            }
        )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    rows_csv = args.out_dir / "matrix_handoff_samples.csv"
    with rows_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["frame", "matrix_index", "fallback", "elapsed_us"])
        writer.writeheader()
        writer.writerows(rows)

    elapsed = np.array([float(row["elapsed_us"]) for row in rows], dtype=np.float64)
    fallback_count = int(sum(int(row["fallback"]) for row in rows))
    frame_index_mismatch_count = int(
        sum(1 for row in rows if int(row["matrix_index"]) >= 0 and int(row["matrix_index"]) != int(row["frame"]) - 1)
    )
    summary = {
        "log": str(args.log),
        "sample_count": len(rows),
        "fallback_count": fallback_count,
        "frame_index_mismatch_count": frame_index_mismatch_count,
        "elapsed_us_avg": f"{float(elapsed.mean()):.6f}" if len(elapsed) else "0.000000",
        "elapsed_us_p95": f"{float(np.percentile(elapsed, 95)):.6f}" if len(elapsed) else "0.000000",
        "elapsed_us_max": f"{float(elapsed.max()):.6f}" if len(elapsed) else "0.000000",
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
                "# Matrix Handoff Log Summary",
                "",
                f"- log: `{args.log}`",
                f"- samples: {len(rows)}",
                f"- fallback count: {fallback_count}",
                f"- frame-index mismatch count: {frame_index_mismatch_count}",
                f"- avg elapsed: {summary['elapsed_us_avg']} us",
                f"- p95 elapsed: {summary['elapsed_us_p95']} us",
                f"- max elapsed: {summary['elapsed_us_max']} us",
                "",
            ]
        ),
        encoding="utf-8",
    )

    print(f"samples: {rows_csv}")
    print(f"summary: {summary_csv}")
    print(f"summary_md: {summary_md}")
    print(f"sample_count: {len(rows)}")
    print(f"fallback_count: {fallback_count}")
    print(f"frame_index_mismatch_count: {frame_index_mismatch_count}")
    print(f"elapsed_us_avg: {summary['elapsed_us_avg']}")
    print(f"elapsed_us_p95: {summary['elapsed_us_p95']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
