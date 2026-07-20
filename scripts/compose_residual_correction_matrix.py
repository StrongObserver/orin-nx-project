from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import cv2
import numpy as np


MATRIX_FIELDS = ["m00", "m01", "m02", "m10", "m11", "m12", "m20", "m21", "m22"]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def row_to_matrix(row: dict[str, str]) -> np.ndarray:
    return np.array([float(row[field]) for field in MATRIX_FIELDS], dtype=np.float64).reshape(3, 3)


def matrix_to_cells(mat: np.ndarray) -> dict[str, str]:
    return {field: f"{float(value):.9f}" for field, value in zip(MATRIX_FIELDS, mat.reshape(-1))}


def moving_average(values: np.ndarray, radius: int) -> np.ndarray:
    if radius <= 0:
        return values.copy()
    kernel = np.ones(2 * radius + 1, dtype=np.float64)
    kernel /= kernel.sum()
    padded = np.pad(values, (radius, radius), mode="edge")
    return np.convolve(padded, kernel, mode="valid")


def gaussian_average(values: np.ndarray, radius: int, stdev: float) -> np.ndarray:
    if radius <= 0:
        return values.copy()
    if stdev <= 0:
        stdev = max(1.0, radius / 3.0)
    offsets = np.arange(-radius, radius + 1, dtype=np.float64)
    kernel = np.exp(-0.5 * (offsets / stdev) * (offsets / stdev))
    kernel /= kernel.sum()
    padded = np.pad(values, (radius, radius), mode="edge")
    return np.convolve(padded, kernel, mode="valid")


def estimate_pair(prev_gray: np.ndarray, curr_gray: np.ndarray) -> tuple[np.ndarray, dict[str, float | int | str]]:
    pts = cv2.goodFeaturesToTrack(prev_gray, maxCorners=500, qualityLevel=0.01, minDistance=20, blockSize=3)
    detected = 0 if pts is None else int(len(pts))
    if pts is None or len(pts) < 8:
        return np.zeros(3, dtype=np.float64), {"detected": detected, "tracked": 0, "inliers": 0, "inlier_ratio": 0.0, "fallback": "too_few_features"}
    curr_pts, status, _ = cv2.calcOpticalFlowPyrLK(prev_gray, curr_gray, pts, None)
    if curr_pts is None or status is None:
        return np.zeros(3, dtype=np.float64), {"detected": detected, "tracked": 0, "inliers": 0, "inlier_ratio": 0.0, "fallback": "lk_failed"}
    valid = status.reshape(-1) == 1
    prev_good = pts[valid]
    curr_good = curr_pts[valid]
    tracked = int(len(prev_good))
    if tracked < 8:
        return np.zeros(3, dtype=np.float64), {"detected": detected, "tracked": tracked, "inliers": 0, "inlier_ratio": 0.0, "fallback": "too_few_tracked"}
    mat, inliers = cv2.estimateAffinePartial2D(prev_good, curr_good, method=cv2.RANSAC, ransacReprojThreshold=3.0)
    if mat is None or inliers is None:
        return np.zeros(3, dtype=np.float64), {"detected": detected, "tracked": tracked, "inliers": 0, "inlier_ratio": 0.0, "fallback": "ransac_failed"}
    inlier_count = int(inliers.sum())
    ratio = float(inlier_count / max(1, tracked))
    dx = float(mat[0, 2])
    dy = float(mat[1, 2])
    angle = math.atan2(float(mat[1, 0]), float(mat[0, 0]))
    return np.array([dx, dy, angle], dtype=np.float64), {"detected": detected, "tracked": tracked, "inliers": inlier_count, "inlier_ratio": ratio, "fallback": ""}


def transform_to_matrix(transform: np.ndarray) -> np.ndarray:
    dx, dy, angle = [float(v) for v in transform]
    c = math.cos(angle)
    s = math.sin(angle)
    return np.array([[c, -s, dx], [s, c, dy], [0.0, 0.0, 1.0]], dtype=np.float64)


def estimate_residual_transforms(video: Path, max_frames: int) -> tuple[np.ndarray, list[dict[str, object]]]:
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video}")
    ok, prev = cap.read()
    if not ok:
        raise RuntimeError(f"Cannot read first frame: {video}")
    prev_gray = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)
    transforms = [np.zeros(3, dtype=np.float64)]
    log_rows: list[dict[str, object]] = [{"frame": 0, "dx": "0.000000000", "dy": "0.000000000", "angle": "0.000000000", "detected": 0, "tracked": 0, "inliers": 0, "inlier_ratio": "0.000000000", "fallback": ""}]
    frame = 1
    while True:
        if max_frames and frame >= max_frames:
            break
        ok, cur = cap.read()
        if not ok:
            break
        cur_gray = cv2.cvtColor(cur, cv2.COLOR_BGR2GRAY)
        motion, detail = estimate_pair(prev_gray, cur_gray)
        transforms.append(motion)
        log_rows.append(
            {
                "frame": frame,
                "dx": f"{float(motion[0]):.9f}",
                "dy": f"{float(motion[1]):.9f}",
                "angle": f"{float(motion[2]):.9f}",
                "detected": int(detail["detected"]),
                "tracked": int(detail["tracked"]),
                "inliers": int(detail["inliers"]),
                "inlier_ratio": f"{float(detail['inlier_ratio']):.9f}",
                "fallback": str(detail["fallback"]),
            }
        )
        prev_gray = cur_gray
        frame += 1
    cap.release()
    return np.asarray(transforms, dtype=np.float64), log_rows


def smooth_trajectory(trajectory: np.ndarray, radius: int, method: str, stdev: float) -> np.ndarray:
    out = trajectory.copy()
    for col in range(out.shape[1]):
        if method == "gaussian":
            out[:, col] = gaussian_average(trajectory[:, col], radius, stdev)
        else:
            out[:, col] = moving_average(trajectory[:, col], radius)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Compose a second-pass residual correction into an existing device matrix CSV.")
    parser.add_argument("--video", type=Path, required=True, help="Video produced by the base matrix, used to estimate residual motion.")
    parser.add_argument("--matrix", type=Path, required=True, help="Base matrix CSV to compose with residual correction.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--motion-log", type=Path, default=None)
    parser.add_argument("--radius", type=int, default=15)
    parser.add_argument("--method", choices=["gaussian", "moving_average"], default="gaussian")
    parser.add_argument("--stdev", type=float, default=0.0)
    parser.add_argument("--strength", type=float, default=1.0)
    parser.add_argument("--max-frames", type=int, default=0)
    parser.add_argument("--first-frame-copy-next", action="store_true")
    args = parser.parse_args()

    matrix_rows = read_rows(args.matrix)
    transforms, log_rows = estimate_residual_transforms(args.video, args.max_frames or len(matrix_rows))
    n = min(len(matrix_rows), len(transforms))
    matrix_rows = matrix_rows[:n]
    transforms = transforms[:n]
    trajectory = np.cumsum(transforms, axis=0)
    smooth = smooth_trajectory(trajectory, max(0, int(args.radius)), args.method, float(args.stdev))
    correction = (smooth - trajectory) * float(np.clip(args.strength, 0.0, 2.0))
    if args.first_frame_copy_next and len(correction) > 1:
        correction[0] = correction[1]

    out_rows = []
    for row, corr in zip(matrix_rows, correction):
        base = row_to_matrix(row)
        corr_mat = transform_to_matrix(corr)
        out = corr_mat @ base
        out_row = {"frame_index": row["frame_index"]}
        out_row.update(matrix_to_cells(out))
        out_rows.append(out_row)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["frame_index", *MATRIX_FIELDS])
        writer.writeheader()
        writer.writerows(out_rows)
    if args.motion_log is not None:
        args.motion_log.parent.mkdir(parents=True, exist_ok=True)
        with args.motion_log.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(log_rows[0].keys()))
            writer.writeheader()
            writer.writerows(log_rows[:n])
    print(f"rows: {len(out_rows)}")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
