from __future__ import annotations

import argparse
import csv
import math
import time
from collections import deque
from pathlib import Path

import cv2
import numpy as np


MATRIX_HEADER = ["frame_index", "m00", "m01", "m02", "m10", "m11", "m12", "m20", "m21", "m22"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Produce live-estimated device-ready matrices from a video into a FIFO or CSV file."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--max-frames", type=int, default=0)
    parser.add_argument("--estimate-scale", type=float, default=0.5)
    parser.add_argument("--crop-ratio", type=float, default=0.90)
    parser.add_argument("--zoom", type=float, default=1.06)
    parser.add_argument("--smoothing-window", type=int, default=1)
    parser.add_argument("--matrix-mode", choices=["cumulative_raw", "window_correction"], default="window_correction")
    parser.add_argument("--min-features", type=int, default=24)
    parser.add_argument("--ransac-threshold", type=float, default=3.0)
    parser.add_argument("--flush-each-row", action="store_true")
    return parser.parse_args()


def center_scale_3x3(width: int, height: int, scale: float) -> np.ndarray:
    center_x = float(width) * 0.5
    center_y = float(height) * 0.5
    return np.array(
        [
            [float(scale), 0.0, (1.0 - float(scale)) * center_x],
            [0.0, float(scale), (1.0 - float(scale)) * center_y],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )


def resize_gray(gray: np.ndarray, scale: float) -> np.ndarray:
    if scale == 1.0:
        return gray
    h, w = gray.shape[:2]
    return cv2.resize(gray, (max(1, int(round(w * scale))), max(1, int(round(h * scale)))), interpolation=cv2.INTER_AREA)


def affine_to_rigid(mat2x3: np.ndarray) -> np.ndarray:
    a = float(mat2x3[0, 0])
    b = float(mat2x3[1, 0])
    scale = max(1e-6, math.hypot(a, b))
    cos_t = a / scale
    sin_t = b / scale
    return np.array(
        [
            [cos_t, -sin_t, float(mat2x3[0, 2])],
            [sin_t, cos_t, float(mat2x3[1, 2])],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )


def rigid_to_pose(mat: np.ndarray) -> np.ndarray:
    return np.array(
        [
            float(mat[0, 2]),
            float(mat[1, 2]),
            math.atan2(float(mat[1, 0]), float(mat[0, 0])),
        ],
        dtype=np.float64,
    )


def pose_to_rigid(pose: np.ndarray) -> np.ndarray:
    dx, dy, angle = [float(v) for v in pose]
    c = math.cos(angle)
    s = math.sin(angle)
    return np.array(
        [
            [c, -s, dx],
            [s, c, dy],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )


def estimate_motion(prev_gray: np.ndarray, curr_gray: np.ndarray, scale: float, ransac_threshold: float):
    t0 = time.perf_counter()
    prev_est = resize_gray(prev_gray, scale)
    curr_est = resize_gray(curr_gray, scale)
    pts = cv2.goodFeaturesToTrack(
        prev_est,
        maxCorners=500,
        qualityLevel=0.01,
        minDistance=max(5, int(round(30 * scale))),
        blockSize=3,
    )
    detected = 0 if pts is None else int(len(pts))
    if pts is None or len(pts) < 8:
        return None, {
            "detected": detected,
            "tracked": 0,
            "inliers": 0,
            "inlier_ratio": 0.0,
            "fallback_reason": "too_few_features",
            "estimate_ms": (time.perf_counter() - t0) * 1000.0,
        }
    curr_pts, status, _ = cv2.calcOpticalFlowPyrLK(prev_est, curr_est, pts, None)
    if curr_pts is None or status is None:
        return None, {
            "detected": detected,
            "tracked": 0,
            "inliers": 0,
            "inlier_ratio": 0.0,
            "fallback_reason": "lk_failed",
            "estimate_ms": (time.perf_counter() - t0) * 1000.0,
        }
    valid = status.reshape(-1) == 1
    prev_good = pts[valid]
    curr_good = curr_pts[valid]
    tracked = int(len(prev_good))
    if tracked < 8:
        return None, {
            "detected": detected,
            "tracked": tracked,
            "inliers": 0,
            "inlier_ratio": 0.0,
            "fallback_reason": "too_few_tracked",
            "estimate_ms": (time.perf_counter() - t0) * 1000.0,
        }
    mat, inliers = cv2.estimateAffinePartial2D(
        prev_good,
        curr_good,
        method=cv2.RANSAC,
        ransacReprojThreshold=ransac_threshold,
        maxIters=2000,
        confidence=0.99,
    )
    if mat is None or inliers is None:
        return None, {
            "detected": detected,
            "tracked": tracked,
            "inliers": 0,
            "inlier_ratio": 0.0,
            "fallback_reason": "ransac_failed",
            "estimate_ms": (time.perf_counter() - t0) * 1000.0,
        }
    inlier_count = int(inliers.sum())
    inlier_ratio = float(inlier_count / max(1, tracked))
    mat = mat.astype(np.float64)
    mat[0, 2] /= scale
    mat[1, 2] /= scale
    return affine_to_rigid(mat), {
        "detected": detected,
        "tracked": tracked,
        "inliers": inlier_count,
        "inlier_ratio": inlier_ratio,
        "fallback_reason": "",
        "estimate_ms": (time.perf_counter() - t0) * 1000.0,
    }


def matrix_cells(mat: np.ndarray) -> list[str]:
    return [f"{float(value):.9f}" for value in mat.reshape(-1)]


def main() -> int:
    args = parse_args()
    cap = cv2.VideoCapture(str(args.input))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open input: {args.input}")
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    post_geometry = center_scale_3x3(width, height, args.zoom) @ center_scale_3x3(width, height, 1.0 / args.crop_ratio)
    # The existing accepted device matrix convention was built as crop @ zoom @ warp.
    post_geometry = center_scale_3x3(width, height, 1.0 / args.crop_ratio) @ center_scale_3x3(width, height, args.zoom)

    ok, first = cap.read()
    if not ok:
        raise RuntimeError("Cannot read first frame")
    prev_gray = cv2.cvtColor(first, cv2.COLOR_BGR2GRAY)
    cumulative = np.eye(3, dtype=np.float64)
    recent_transforms: deque[np.ndarray] = deque(maxlen=max(1, args.smoothing_window))
    trajectory_window: deque[np.ndarray] = deque(maxlen=max(1, args.smoothing_window))

    args.log.parent.mkdir(parents=True, exist_ok=True)
    log_file = args.log.open("w", newline="", encoding="utf-8")
    log_writer = csv.DictWriter(
        log_file,
        fieldnames=[
            "frame_index",
            "matrix_mode",
            "detected",
            "tracked",
            "inliers",
            "inlier_ratio",
            "fallback_reason",
            "estimate_ms",
            "producer_elapsed_us",
        ],
    )
    log_writer.writeheader()

    rows_written = 0
    with args.output.open("w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow(MATRIX_HEADER)

        t_row = time.perf_counter()
        writer.writerow([0, *matrix_cells(np.eye(3, dtype=np.float64))])
        if args.flush_each_row:
            out.flush()
        log_writer.writerow(
            {
                "frame_index": 0,
                "matrix_mode": "identity_first",
                "detected": 0,
                "tracked": 0,
                "inliers": 0,
                "inlier_ratio": "0.000000",
                "fallback_reason": "",
                "estimate_ms": "0.000000",
                "producer_elapsed_us": f"{(time.perf_counter() - t_row) * 1_000_000.0:.6f}",
            }
        )
        log_file.flush()
        rows_written += 1

        frame_index = 1
        while True:
            if args.max_frames and frame_index >= args.max_frames:
                break
            ok, frame = cap.read()
            if not ok:
                break
            curr_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            t_row = time.perf_counter()
            motion, details = estimate_motion(prev_gray, curr_gray, args.estimate_scale, args.ransac_threshold)
            if motion is None or details["tracked"] < args.min_features:
                motion = np.eye(3, dtype=np.float64)
                details["fallback_reason"] = details["fallback_reason"] or "below_min_features"
            cumulative = motion @ cumulative
            if args.matrix_mode == "cumulative_raw":
                recent_transforms.append(motion)
                output_mat = np.mean(np.stack(list(recent_transforms), axis=0), axis=0)
                output_mat[2, :] = [0.0, 0.0, 1.0]
            else:
                trajectory_window.append(rigid_to_pose(cumulative))
                smooth_pose = np.mean(np.stack(list(trajectory_window), axis=0), axis=0)
                desired_pose = pose_to_rigid(smooth_pose)
                output_mat = desired_pose @ np.linalg.inv(cumulative)
            device_mat = np.linalg.inv(post_geometry @ output_mat)
            writer.writerow([frame_index, *matrix_cells(device_mat)])
            if args.flush_each_row:
                out.flush()
            log_writer.writerow(
                {
                    "frame_index": frame_index,
                    "matrix_mode": args.matrix_mode,
                    "detected": details["detected"],
                    "tracked": details["tracked"],
                    "inliers": details["inliers"],
                    "inlier_ratio": f"{details['inlier_ratio']:.6f}",
                    "fallback_reason": details["fallback_reason"],
                    "estimate_ms": f"{details['estimate_ms']:.6f}",
                    "producer_elapsed_us": f"{(time.perf_counter() - t_row) * 1_000_000.0:.6f}",
                }
            )
            log_file.flush()
            rows_written += 1
            prev_gray = curr_gray
            frame_index += 1
    cap.release()
    log_file.close()
    print(f"rows_written: {rows_written}")
    print(f"input: {args.input}")
    print(f"output: {args.output}")
    print(f"log: {args.log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
