from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import cv2
import numpy as np


def estimate_motion(prev_gray: np.ndarray, curr_gray: np.ndarray) -> tuple[float, float, float, int, int, float]:
    pts = cv2.goodFeaturesToTrack(prev_gray, maxCorners=500, qualityLevel=0.01, minDistance=20, blockSize=3)
    detected = 0 if pts is None else int(len(pts))
    if pts is None or len(pts) < 8:
        return 0.0, 0.0, 0.0, detected, 0, 0.0
    curr_pts, status, _ = cv2.calcOpticalFlowPyrLK(prev_gray, curr_gray, pts, None)
    if curr_pts is None or status is None:
        return 0.0, 0.0, 0.0, detected, 0, 0.0
    valid = status.reshape(-1) == 1
    prev_good = pts[valid]
    curr_good = curr_pts[valid]
    tracked = int(len(prev_good))
    if tracked < 8:
        return 0.0, 0.0, 0.0, detected, tracked, 0.0
    mat, inliers = cv2.estimateAffinePartial2D(prev_good, curr_good, method=cv2.RANSAC, ransacReprojThreshold=3.0)
    if mat is None or inliers is None:
        return 0.0, 0.0, 0.0, detected, tracked, 0.0
    inlier_count = int(inliers.sum())
    ratio = float(inlier_count / max(1, tracked))
    dx = float(mat[0, 2])
    dy = float(mat[1, 2])
    angle = math.atan2(float(mat[1, 0]), float(mat[0, 0]))
    return dx, dy, angle, detected, tracked, ratio


def summarize(values: np.ndarray) -> dict[str, str]:
    if len(values) == 0:
        return {"mean": "0.000000000", "p95": "0.000000000", "max": "0.000000000"}
    return {
        "mean": f"{float(np.mean(values)):.9f}",
        "p95": f"{float(np.percentile(values, 95)):.9f}",
        "max": f"{float(np.max(values)):.9f}",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure residual global frame-to-frame motion in a video.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--max-frames", type=int, default=0)
    args = parser.parse_args()

    cap = cv2.VideoCapture(str(args.input))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {args.input}")
    ok, prev = cap.read()
    if not ok:
        raise RuntimeError(f"Cannot read first frame: {args.input}")
    prev_gray = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)
    rows = []
    frame = 1
    while True:
        if args.max_frames and frame >= args.max_frames:
            break
        ok, cur = cap.read()
        if not ok:
            break
        cur_gray = cv2.cvtColor(cur, cv2.COLOR_BGR2GRAY)
        dx, dy, angle, detected, tracked, ratio = estimate_motion(prev_gray, cur_gray)
        trans = math.hypot(dx, dy)
        rows.append(
            {
                "frame": frame,
                "dx": f"{dx:.9f}",
                "dy": f"{dy:.9f}",
                "trans": f"{trans:.9f}",
                "angle": f"{angle:.9f}",
                "detected": detected,
                "tracked": tracked,
                "inlier_ratio": f"{ratio:.9f}",
            }
        )
        prev_gray = cur_gray
        frame += 1
    cap.release()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    frames_csv = args.out_dir / "residual_motion_frames.csv"
    with frames_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["frame"])
        writer.writeheader()
        writer.writerows(rows)

    trans = np.array([float(row["trans"]) for row in rows], dtype=np.float64)
    angle = np.abs(np.array([float(row["angle"]) for row in rows], dtype=np.float64))
    trans_s = summarize(trans)
    angle_s = summarize(angle)
    summary = {
        "input": str(args.input),
        "frames": len(rows) + 1 if rows else 0,
        "motion_pairs": len(rows),
        "trans_mean": trans_s["mean"],
        "trans_p95": trans_s["p95"],
        "trans_max": trans_s["max"],
        "angle_abs_mean": angle_s["mean"],
        "angle_abs_p95": angle_s["p95"],
        "angle_abs_max": angle_s["max"],
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
