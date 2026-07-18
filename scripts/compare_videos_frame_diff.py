from __future__ import annotations

import argparse
import csv
from pathlib import Path

import cv2
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare two videos frame by frame with simple absolute-difference metrics.")
    parser.add_argument("--a", type=Path, required=True)
    parser.add_argument("--b", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--max-frames", type=int, default=0)
    return parser.parse_args()


def open_video(path: Path) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {path}")
    return cap


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    cap_a = open_video(args.a)
    cap_b = open_video(args.b)

    rows: list[dict] = []
    frame_index = 0
    while True:
        ok_a, frame_a = cap_a.read()
        ok_b, frame_b = cap_b.read()
        if not ok_a or not ok_b:
            break
        if args.max_frames and frame_index >= args.max_frames:
            break
        if frame_a.shape != frame_b.shape:
            raise RuntimeError(f"Frame shape differs at {frame_index}: {frame_a.shape} vs {frame_b.shape}")

        diff = np.abs(frame_a.astype(np.int16) - frame_b.astype(np.int16))
        height, width = diff.shape[:2]
        y0, y1 = height // 4, (height * 3) // 4
        x0, x1 = width // 4, (width * 3) // 4
        center = diff[y0:y1, x0:x1]
        rows.append(
            {
                "frame": frame_index,
                "mean_abs_all": f"{float(diff.mean()):.6f}",
                "p95_abs_all": f"{float(np.percentile(diff, 95)):.6f}",
                "mean_abs_center": f"{float(center.mean()):.6f}",
                "p95_abs_center": f"{float(np.percentile(center, 95)):.6f}",
                "max_abs_all": int(diff.max()),
                "max_abs_center": int(center.max()),
            }
        )
        frame_index += 1

    cap_a.release()
    cap_b.release()

    frame_csv = args.out_dir / "frame_diff.csv"
    if rows:
        with frame_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    def avg(name: str) -> float:
        return sum(float(row[name]) for row in rows) / len(rows) if rows else 0.0

    summary = {
        "frames_compared": len(rows),
        "mean_abs_all_avg": f"{avg('mean_abs_all'):.6f}",
        "p95_abs_all_avg": f"{avg('p95_abs_all'):.6f}",
        "mean_abs_center_avg": f"{avg('mean_abs_center'):.6f}",
        "p95_abs_center_avg": f"{avg('p95_abs_center'):.6f}",
        "max_abs_all": max((int(row["max_abs_all"]) for row in rows), default=0),
        "max_abs_center": max((int(row["max_abs_center"]) for row in rows), default=0),
    }
    summary_csv = args.out_dir / "correctness_summary.csv"
    with summary_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary.keys()))
        writer.writeheader()
        writer.writerow(summary)

    print(f"frame_diff: {frame_csv}")
    print(f"summary: {summary_csv}")
    for key, value in summary.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
