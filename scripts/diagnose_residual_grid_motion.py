from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import cv2
import numpy as np


def grid_points(gray: np.ndarray, rows: int, cols: int, max_corners_per_cell: int) -> np.ndarray:
    h, w = gray.shape[:2]
    pts_all = []
    for gy in range(rows):
        y0 = int(round(gy * h / rows))
        y1 = int(round((gy + 1) * h / rows))
        for gx in range(cols):
            x0 = int(round(gx * w / cols))
            x1 = int(round((gx + 1) * w / cols))
            roi = gray[y0:y1, x0:x1]
            pts = cv2.goodFeaturesToTrack(
                roi,
                maxCorners=max_corners_per_cell,
                qualityLevel=0.01,
                minDistance=8,
                blockSize=3,
            )
            if pts is None:
                continue
            pts[:, 0, 0] += x0
            pts[:, 0, 1] += y0
            pts_all.append(pts)
    if not pts_all:
        return np.empty((0, 1, 2), dtype=np.float32)
    return np.concatenate(pts_all, axis=0).astype(np.float32)


def robust_global(prev_pts: np.ndarray, curr_pts: np.ndarray) -> tuple[np.ndarray | None, np.ndarray | None]:
    if len(prev_pts) < 8:
        return None, None
    mat, inliers = cv2.estimateAffinePartial2D(prev_pts, curr_pts, method=cv2.RANSAC, ransacReprojThreshold=3.0)
    if mat is None or inliers is None:
        return None, None
    return mat.astype(np.float64), inliers.reshape(-1).astype(bool)


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose local residual motion after global frame-to-frame alignment.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--grid-rows", type=int, default=4)
    parser.add_argument("--grid-cols", type=int, default=4)
    parser.add_argument("--max-frames", type=int, default=0)
    parser.add_argument("--max-corners-per-cell", type=int, default=40)
    args = parser.parse_args()

    cap = cv2.VideoCapture(str(args.input))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {args.input}")
    ok, prev = cap.read()
    if not ok:
        raise RuntimeError("Cannot read first frame")
    prev_gray = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)
    h, w = prev_gray.shape[:2]
    cell_w = w / args.grid_cols
    cell_h = h / args.grid_rows
    rows = []
    frame = 1
    while True:
        if args.max_frames and frame >= args.max_frames:
            break
        ok, cur = cap.read()
        if not ok:
            break
        cur_gray = cv2.cvtColor(cur, cv2.COLOR_BGR2GRAY)
        pts = grid_points(prev_gray, args.grid_rows, args.grid_cols, args.max_corners_per_cell)
        if len(pts) < 8:
            prev_gray = cur_gray
            frame += 1
            continue
        curr_pts, status, _ = cv2.calcOpticalFlowPyrLK(prev_gray, cur_gray, pts, None)
        if curr_pts is None or status is None:
            prev_gray = cur_gray
            frame += 1
            continue
        valid = status.reshape(-1) == 1
        prev_good = pts.reshape(-1, 2)[valid]
        curr_good = curr_pts.reshape(-1, 2)[valid]
        mat, inliers = robust_global(prev_good, curr_good)
        if mat is None or inliers is None:
            prev_gray = cur_gray
            frame += 1
            continue
        prev_in = prev_good[inliers]
        curr_in = curr_good[inliers]
        pred = (mat[:, :2] @ prev_in.T).T + mat[:, 2]
        residual = curr_in - pred
        mags = np.linalg.norm(residual, axis=1)
        cell_means = []
        cell_counts = []
        for gy in range(args.grid_rows):
            for gx in range(args.grid_cols):
                mask = (
                    (prev_in[:, 0] >= gx * cell_w)
                    & (prev_in[:, 0] < (gx + 1) * cell_w)
                    & (prev_in[:, 1] >= gy * cell_h)
                    & (prev_in[:, 1] < (gy + 1) * cell_h)
                )
                vals = mags[mask]
                cell_counts.append(int(len(vals)))
                cell_means.append(float(vals.mean()) if len(vals) else 0.0)
        nonzero = np.array([v for v, c in zip(cell_means, cell_counts) if c >= 3], dtype=np.float64)
        rows.append(
            {
                "frame": frame,
                "tracked": int(len(prev_good)),
                "inliers": int(len(prev_in)),
                "inlier_ratio": f"{float(len(prev_in) / max(1, len(prev_good))):.9f}",
                "global_residual_mean": f"{float(mags.mean()) if len(mags) else 0.0:.9f}",
                "global_residual_p95": f"{float(np.percentile(mags, 95)) if len(mags) else 0.0:.9f}",
                "cell_mean_max": f"{float(nonzero.max()) if len(nonzero) else 0.0:.9f}",
                "cell_mean_std": f"{float(nonzero.std()) if len(nonzero) else 0.0:.9f}",
                "cell_mean_range": f"{float(nonzero.max() - nonzero.min()) if len(nonzero) else 0.0:.9f}",
                "valid_cells": int(len(nonzero)),
            }
        )
        prev_gray = cur_gray
        frame += 1
    cap.release()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    frames_csv = args.out_dir / "residual_grid_frames.csv"
    with frames_csv.open("w", newline="", encoding="utf-8") as f:
        fieldnames = list(rows[0].keys()) if rows else ["frame"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    def vals(key: str) -> np.ndarray:
        return np.array([float(row[key]) for row in rows], dtype=np.float64)

    summary = {
        "input": str(args.input),
        "frames": len(rows) + 1 if rows else 0,
        "pairs": len(rows),
    }
    for key in ("global_residual_mean", "global_residual_p95", "cell_mean_max", "cell_mean_std", "cell_mean_range"):
        arr = vals(key) if rows else np.array([], dtype=np.float64)
        summary[f"{key}_avg"] = f"{float(arr.mean()) if len(arr) else 0.0:.9f}"
        summary[f"{key}_p95"] = f"{float(np.percentile(arr, 95)) if len(arr) else 0.0:.9f}"
        summary[f"{key}_max"] = f"{float(arr.max()) if len(arr) else 0.0:.9f}"
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
