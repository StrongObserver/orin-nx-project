from __future__ import annotations

import argparse
import csv
from pathlib import Path

import cv2
import numpy as np


MATRIX_FIELDS = ["m00", "m01", "m02", "m10", "m11", "m12", "m20", "m21", "m22"]


def read_matrices(path: Path) -> list[np.ndarray]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    out = []
    for row in rows:
        out.append(np.array([float(row[field]) for field in MATRIX_FIELDS], dtype=np.float64).reshape(3, 3))
    return out


def invalid_ratio(mat: np.ndarray, width: int, height: int, margin_px: float) -> float:
    inv = np.linalg.inv(mat)
    xs, ys = np.meshgrid(np.arange(width, dtype=np.float64), np.arange(height, dtype=np.float64))
    points = np.stack([xs, ys, np.ones_like(xs)], axis=-1).reshape(-1, 3)
    mapped = (inv @ points.T).T
    xy = mapped[:, :2] / mapped[:, 2:3]
    valid = (
        (xy[:, 0] >= margin_px)
        & (xy[:, 0] <= width - 1.0 - margin_px)
        & (xy[:, 1] >= margin_px)
        & (xy[:, 1] <= height - 1.0 - margin_px)
    )
    return float(1.0 - valid.mean())


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure source-valid output coverage implied by matrix geometry.")
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--width", type=int, required=True)
    parser.add_argument("--height", type=int, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--margin-px", type=float, default=0.0)
    args = parser.parse_args()

    mats = read_matrices(args.matrix)
    rows = []
    for index, mat in enumerate(mats):
        rows.append({"frame": index, "invalid_ratio": f"{invalid_ratio(mat, args.width, args.height, args.margin_px):.9f}"})

    args.out_dir.mkdir(parents=True, exist_ok=True)
    frames_csv = args.out_dir / "valid_coverage_frames.csv"
    with frames_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["frame", "invalid_ratio"])
        writer.writeheader()
        writer.writerows(rows)

    values = np.array([float(row["invalid_ratio"]) for row in rows], dtype=np.float64)
    summary = {
        "matrix": str(args.matrix),
        "frames": len(rows),
        "margin_px": f"{args.margin_px:.3f}",
        "mean_invalid_ratio": f"{float(values.mean()) if len(values) else 0.0:.9f}",
        "p95_invalid_ratio": f"{float(np.percentile(values, 95)) if len(values) else 0.0:.9f}",
        "max_invalid_ratio": f"{float(values.max()) if len(values) else 0.0:.9f}",
        "frames_gt_0p01": int(np.sum(values > 0.01)) if len(values) else 0,
    }
    summary_csv = args.out_dir / "summary.csv"
    with summary_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary.keys()))
        writer.writeheader()
        writer.writerow(summary)

    print(f"frames: {frames_csv}")
    print(f"summary: {summary_csv}")
    for key, value in summary.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
