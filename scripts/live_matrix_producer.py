from __future__ import annotations

import argparse
import csv
import math
import sys
import time
from collections import deque
from pathlib import Path

import cv2
import numpy as np


MATRIX_HEADER = ["frame_index", "m00", "m01", "m02", "m10", "m11", "m12", "m20", "m21", "m22"]
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


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
    parser.add_argument(
        "--matrix-mode",
        choices=[
            "cumulative_raw",
            "window_correction",
            "window_correction_cpu_style",
            "offline_lp_rigid",
            "bounded_delay_lp_rigid",
            "local_window_lp_rigid",
        ],
        default="window_correction",
    )
    parser.add_argument("--output-convention", choices=["source_to_dest", "inverse"], default="inverse")
    parser.add_argument("--producer-delay-frames", type=int, default=0)
    parser.add_argument("--feature-grid-size", type=int, default=12)
    parser.add_argument("--foreground-reject-threshold", type=float, default=10.0)
    parser.add_argument("--min-inliers", type=int, default=12)
    parser.add_argument("--min-inlier-ratio", type=float, default=0.10)
    parser.add_argument("--lp-trim-ratio", type=float, default=0.10)
    parser.add_argument("--lp-w1", type=float, default=50.0)
    parser.add_argument("--lp-w2", type=float, default=10.0)
    parser.add_argument("--lp-w3", type=float, default=20.0)
    parser.add_argument("--lp-w4", type=float, default=30.0)
    parser.add_argument("--stabilization-strength", type=float, default=0.80)
    parser.add_argument(
        "--lp-prefix-stride",
        type=int,
        default=1,
        help=(
            "For bounded_delay_lp_rigid only, solve LP prefixes every N frames and reuse the most recent "
            "prefix between solves. Default 1 preserves the original per-prefix behavior."
        ),
    )
    parser.add_argument(
        "--lock-published-prefix",
        action="store_true",
        help=(
            "For bounded_delay_lp_rigid, add a soft continuity penalty toward already emitted LP output "
            "matrices when later prefixes are re-solved. Default off preserves historical behavior."
        ),
    )
    parser.add_argument(
        "--published-prefix-weight",
        type=float,
        default=0.0,
        help=(
            "Soft continuity weight for already emitted LP output matrices. Values >0 enable the penalty. "
            "--lock-published-prefix uses 100 when this is left at 0."
        ),
    )
    parser.add_argument(
        "--intent-reference-weight",
        type=float,
        default=0.0,
        help="Soft LP weight toward a low-pass camera-intent correction path. Default 0 preserves historical behavior.",
    )
    parser.add_argument(
        "--intent-reference-radius",
        type=int,
        default=30,
        help="Gaussian radius for the low-pass intent trajectory used by --intent-reference-weight.",
    )
    parser.add_argument(
        "--intent-reference-stdev",
        type=float,
        default=0.0,
        help="Gaussian stdev for the low-pass intent trajectory; <=0 uses radius/3.",
    )
    parser.add_argument("--mask-safety-max-invalid", type=float, default=0.01)
    parser.add_argument("--min-features", type=int, default=24)
    parser.add_argument("--ransac-threshold", type=float, default=3.0)
    parser.add_argument("--flush-each-row", action="store_true")
    parser.add_argument(
        "--incremental-prefix-output",
        action="store_true",
        help=(
            "For bounded_delay_lp_rigid, write each matrix as soon as its scheduled LP prefix "
            "has been solved. Matrix math is unchanged; only output scheduling changes."
        ),
    )
    parser.add_argument(
        "--timing-summary",
        type=Path,
        default=None,
        help="Optional one-row CSV with producer stage timing. Does not change matrix output.",
    )
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


def prepare_output_matrix(mat: np.ndarray, output_convention: str) -> np.ndarray:
    if output_convention == "source_to_dest":
        return mat
    return np.linalg.inv(mat)


def add_ms(timing: dict[str, float], key: str, start: float) -> None:
    timing[key] = timing.get(key, 0.0) + (time.perf_counter() - start) * 1000.0


def scheduled_prefix_len(frame_number: int, total_motions: int, delay: int, prefix_stride: int) -> int:
    if frame_number < 1:
        raise ValueError("frame_number must be at least 1")
    if total_motions < 1:
        raise ValueError("total_motions must be at least 1")
    delay = max(0, int(delay))
    prefix_stride = max(1, int(prefix_stride))
    prefix_len = min(total_motions, frame_number + delay)
    if prefix_stride > 1 and prefix_len < total_motions:
        first_prefix = min(total_motions, 1 + delay)
        if prefix_len > first_prefix:
            offset = prefix_len - first_prefix
            prefix_len = first_prefix + (offset // prefix_stride) * prefix_stride
    return prefix_len


def gaussian_average(values: np.ndarray, radius: int, stdev: float) -> np.ndarray:
    if radius <= 0:
        return values.copy()
    if stdev <= 0:
        stdev = max(1.0, float(radius) / 3.0)
    offsets = np.arange(-radius, radius + 1, dtype=np.float64)
    weights = np.exp(-0.5 * (offsets / stdev) * (offsets / stdev))
    weights /= np.sum(weights)
    padded = np.pad(values, (radius, radius), mode="edge")
    return np.convolve(padded, weights, mode="same")[radius:-radius]


def smooth_pose_reference(poses: np.ndarray, radius: int, stdev: float) -> np.ndarray:
    if len(poses) == 0:
        return poses.copy()
    out = poses.astype(np.float64, copy=True)
    for col in range(out.shape[1]):
        out[:, col] = gaussian_average(out[:, col], radius, stdev)
    return out.astype(np.float32)


def transform_vec_to_mat(vec: np.ndarray) -> np.ndarray:
    dx, dy, angle = [float(v) for v in vec]
    c = math.cos(angle)
    s = math.sin(angle)
    return np.array(
        [
            [c, -s, dx],
            [s, c, dy],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float32,
    )


def write_timing_summary(path: Path | None, timing: dict[str, object]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(timing.keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(timing)


def write_offline_lp_rigid(
    args: argparse.Namespace,
    cap: cv2.VideoCapture,
    first_gray: np.ndarray,
    width: int,
    height: int,
    post_geometry: np.ndarray,
) -> int:
    from src.cpu_stabilize import (
        apply_mask_safety_rollback_mats,
        estimate_transform,
        interpolate_invalid_transforms,
        limit_transform_sequence,
        solve_lp_motion_stabilizer_rigid,
    )

    total_t0 = time.perf_counter()
    timing: dict[str, object] = {
        "matrix_mode": args.matrix_mode,
        "output_convention": args.output_convention,
        "producer_delay_frames": int(args.producer_delay_frames),
        "lp_prefix_stride": max(1, int(args.lp_prefix_stride)),
        "incremental_prefix_output": bool(args.incremental_prefix_output),
        "lock_published_prefix": bool(args.lock_published_prefix),
        "intent_reference_weight": float(args.intent_reference_weight),
        "intent_reference_radius": int(args.intent_reference_radius),
        "estimate_scale": float(args.estimate_scale),
        "feature_grid_size": int(args.feature_grid_size),
        "frames_written": 0,
        "motion_rows": 0,
        "lp_solve_calls": 0,
        "lp_solve_prefix_frames_total": 0,
        "lp_solve_max_ms": 0.0,
        "lp_solve_total_ms": 0.0,
        "mask_safety_total_ms": 0.0,
        "candidate_build_total_ms": 0.0,
        "matrix_write_total_ms": 0.0,
        "decode_total_ms": 0.0,
        "gray_total_ms": 0.0,
        "estimate_total_ms": 0.0,
        "interpolate_limit_total_ms": 0.0,
        "output_matrix_total_ms": 0.0,
        "preprocess_complete_ms": 0.0,
        "first_row_elapsed_ms": 0.0,
        "first_solved_row_elapsed_ms": 0.0,
        "last_row_elapsed_ms": 0.0,
    }
    prev_gray = first_gray
    transforms = []
    valid_mask = []
    details_rows = []
    frame_index = 1
    while True:
        if args.max_frames and frame_index >= args.max_frames:
            break
        t_decode = time.perf_counter()
        ok, frame = cap.read()
        add_ms(timing, "decode_total_ms", t_decode)
        if not ok:
            break
        t_gray = time.perf_counter()
        curr_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        add_ms(timing, "gray_total_ms", t_gray)
        t0 = time.perf_counter()
        transform, details = estimate_transform(
            prev_gray,
            curr_gray,
            args.estimate_scale,
            args.feature_grid_size,
            args.foreground_reject_threshold,
            args.min_inliers,
            args.min_inlier_ratio,
            args.ransac_threshold,
        )
        estimate_ms = (time.perf_counter() - t0) * 1000.0
        timing["estimate_total_ms"] = float(timing["estimate_total_ms"]) + estimate_ms
        if transform is None:
            transform = np.array([0.0, 0.0, 0.0], dtype=np.float32)
            valid = False
        else:
            valid = True
        transforms.append(transform)
        valid_mask.append(valid)
        details_rows.append((frame_index, details, estimate_ms))
        prev_gray = curr_gray
        frame_index += 1

    if not transforms:
        raise RuntimeError("Input video has too few frames")

    transforms_np = np.asarray(transforms, dtype=np.float32)
    valid_np = np.asarray(valid_mask, dtype=bool)
    t_pre_lp = time.perf_counter()
    transforms_for_smoothing = interpolate_invalid_transforms(transforms_np, valid_np)
    transforms_limited, _, _ = limit_transform_sequence(
        transforms_for_smoothing,
        width,
        max_translation_ratio=0.05,
        max_rotation_deg=2.0,
        accel_limit_px=10.0,
        accel_limit_deg=0.5,
    )
    add_ms(timing, "interpolate_limit_total_ms", t_pre_lp)
    timing["preprocess_complete_ms"] = (time.perf_counter() - total_t0) * 1000.0
    strength = float(np.clip(args.stabilization_strength, 0.0, 1.0))
    identity = np.eye(3, dtype=np.float32)
    published_prefix_weight = float(args.published_prefix_weight)
    if args.lock_published_prefix and published_prefix_weight <= 0.0:
        published_prefix_weight = 100.0
    lock_published_prefix = published_prefix_weight > 0.0
    timing["published_prefix_weight"] = published_prefix_weight
    trajectory = np.cumsum(transforms_limited, axis=0)
    intent_reference_mats: list[np.ndarray] | None = None
    intent_reference_weight = max(0.0, float(args.intent_reference_weight))
    if intent_reference_weight > 0.0:
        radius = max(1, int(args.intent_reference_radius))
        intent_trajectory = smooth_pose_reference(trajectory, radius, float(args.intent_reference_stdev))
        intent_delta = intent_trajectory - trajectory
        intent_transforms = transforms_limited + intent_delta
        intent_reference_mats = [transform_vec_to_mat(vec) for vec in intent_transforms]

    published_solver_mats: list[np.ndarray] = []

    def output_to_solver_domain(mat: np.ndarray) -> np.ndarray:
        if strength <= 1e-6:
            return identity.copy()
        return (identity + (mat.astype(np.float32) - identity) / strength).astype(np.float32)

    def solve_output_mats_for_prefix(prefix_len: int, locked_prefix_mats: list[np.ndarray] | None = None) -> list[np.ndarray]:
        solve_t0 = time.perf_counter()
        lp_mats = solve_lp_motion_stabilizer_rigid(
            transforms_limited[:prefix_len],
            width,
            height,
            trim_ratio=args.lp_trim_ratio,
            w1=args.lp_w1,
            w2=args.lp_w2,
            w3=args.lp_w3,
            w4=args.lp_w4,
            anchor_first=False,
            locked_prefix_mats=locked_prefix_mats,
            locked_prefix_weight=published_prefix_weight,
            reference_mats=None if intent_reference_mats is None else intent_reference_mats[:prefix_len],
            reference_weight=intent_reference_weight,
        )
        solve_ms = (time.perf_counter() - solve_t0) * 1000.0
        timing["lp_solve_calls"] = int(timing["lp_solve_calls"]) + 1
        timing["lp_solve_prefix_frames_total"] = int(timing["lp_solve_prefix_frames_total"]) + int(prefix_len)
        timing["lp_solve_total_ms"] = float(timing["lp_solve_total_ms"]) + solve_ms
        timing["lp_solve_max_ms"] = max(float(timing["lp_solve_max_ms"]), solve_ms)
        t_candidates = time.perf_counter()
        candidate_mats = [identity + strength * (mat.astype(np.float32) - identity) for mat in lp_mats[1:]]
        zoom_curve = np.full(len(candidate_mats), float(args.zoom), dtype=np.float32)
        add_ms(timing, "candidate_build_total_ms", t_candidates)
        t_mask = time.perf_counter()
        output_mats, _, _, _, _ = apply_mask_safety_rollback_mats(
            candidate_mats,
            width,
            height,
            args.crop_ratio,
            1.0,
            zoom_curve,
            args.mask_safety_max_invalid,
        )
        add_ms(timing, "mask_safety_total_ms", t_mask)
        return output_mats

    log_fieldnames = [
        "frame_index",
        "matrix_mode",
        "output_convention",
        "detected",
        "tracked",
        "inliers",
        "inlier_ratio",
        "fallback_reason",
        "estimate_ms",
        "producer_elapsed_us",
        "producer_delay_frames",
    ]

    def write_identity_row(writer: csv.writer, log_writer: csv.DictWriter) -> None:
        writer.writerow([0, *matrix_cells(np.eye(3, dtype=np.float64))])
        log_writer.writerow(
            {
                "frame_index": 0,
                "matrix_mode": "identity_first",
                "output_convention": args.output_convention,
                "detected": 0,
                "tracked": 0,
                "inliers": 0,
                "inlier_ratio": "0.000000",
                "fallback_reason": "",
                "estimate_ms": "0.000000",
                "producer_elapsed_us": "0.000000",
                "producer_delay_frames": (
                    int(args.producer_delay_frames)
                    if args.matrix_mode in {"bounded_delay_lp_rigid", "local_window_lp_rigid"}
                    else 0
                ),
            }
        )

    def write_output_row(
        writer: csv.writer,
        log_writer: csv.DictWriter,
        mat: np.ndarray,
        detail_row: tuple[int, dict[str, object], float],
    ) -> None:
        idx, details, estimate_ms = detail_row
        t_row = time.perf_counter()
        device_mat = prepare_output_matrix(post_geometry @ mat, args.output_convention)
        writer.writerow([idx, *matrix_cells(device_mat)])
        row_elapsed_us = (time.perf_counter() - t_row) * 1_000_000.0
        log_writer.writerow(
            {
                "frame_index": idx,
                "matrix_mode": args.matrix_mode,
                "output_convention": args.output_convention,
                "detected": details["detected_features"],
                "tracked": details["tracked_features"],
                "inliers": details["inliers"],
                "inlier_ratio": f"{details['inlier_ratio']:.6f}",
                "fallback_reason": details["fallback_reason"],
                "estimate_ms": f"{estimate_ms:.6f}",
                "producer_elapsed_us": f"{row_elapsed_us:.6f}",
                "producer_delay_frames": (
                    int(args.producer_delay_frames)
                    if args.matrix_mode in {"bounded_delay_lp_rigid", "local_window_lp_rigid"}
                    else 0
                ),
            }
        )
        timing["matrix_write_total_ms"] = float(timing["matrix_write_total_ms"]) + row_elapsed_us / 1000.0

    if args.incremental_prefix_output:
        if args.matrix_mode != "bounded_delay_lp_rigid":
            raise ValueError("--incremental-prefix-output requires --matrix-mode bounded_delay_lp_rigid")
        delay = max(0, int(args.producer_delay_frames))
        prefix_stride = max(1, int(args.lp_prefix_stride))
        prefix_cache: dict[int, list[np.ndarray]] = {}
        args.log.parent.mkdir(parents=True, exist_ok=True)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        t_output_matrix = time.perf_counter()
        with args.output.open("w", newline="", encoding="utf-8") as out, args.log.open(
            "w", newline="", encoding="utf-8"
        ) as log:
            writer = csv.writer(out)
            writer.writerow(MATRIX_HEADER)
            log_writer = csv.DictWriter(log, fieldnames=log_fieldnames)
            log_writer.writeheader()
            write_identity_row(writer, log_writer)
            if args.flush_each_row:
                out.flush()
                log.flush()
            timing["first_row_elapsed_ms"] = (time.perf_counter() - total_t0) * 1000.0
            for frame_number in range(1, len(transforms_limited) + 1):
                prefix_len = scheduled_prefix_len(
                    frame_number, len(transforms_limited), delay, prefix_stride
                )
                if prefix_len not in prefix_cache:
                    locked = published_solver_mats if lock_published_prefix else None
                    prefix_cache[prefix_len] = solve_output_mats_for_prefix(prefix_len, locked)
                output_mat = prefix_cache[prefix_len][frame_number - 1]
                if lock_published_prefix:
                    published_solver_mats.append(output_to_solver_domain(output_mat))
                write_output_row(writer, log_writer, output_mat, details_rows[frame_number - 1])
                if args.flush_each_row:
                    out.flush()
                    log.flush()
                if frame_number == 1:
                    timing["first_solved_row_elapsed_ms"] = (time.perf_counter() - total_t0) * 1000.0
            timing["last_row_elapsed_ms"] = (time.perf_counter() - total_t0) * 1000.0
        add_ms(timing, "output_matrix_total_ms", t_output_matrix)
        timing["motion_rows"] = len(details_rows)
        timing["frames_written"] = len(details_rows) + 1
        timing["total_elapsed_ms"] = (time.perf_counter() - total_t0) * 1000.0
        write_timing_summary(args.timing_summary, timing)
        return len(details_rows) + 1

    if args.matrix_mode == "offline_lp_rigid":
        output_mats = solve_output_mats_for_prefix(len(transforms_limited))
    elif args.matrix_mode == "local_window_lp_rigid":
        delay = max(0, int(args.producer_delay_frames))
        output_mats = []
        window_cache: dict[tuple[int, int], list[np.ndarray]] = {}
        n = len(transforms_limited)
        for frame_number in range(1, n + 1):
            start_frame = max(1, frame_number - delay)
            end_frame = min(n, frame_number + delay)
            start_idx = start_frame - 1
            end_idx = end_frame
            key = (start_idx, end_idx)
            if key not in window_cache:
                window_cache[key] = solve_output_mats_for_prefix(end_idx - start_idx)
            local_index = frame_number - start_frame
            output_mats.append(window_cache[key][local_index])
    else:
        delay = max(0, int(args.producer_delay_frames))
        prefix_stride = max(1, int(args.lp_prefix_stride))
        prefix_cache: dict[int, list[np.ndarray]] = {}
        t_output_matrix = time.perf_counter()
        output_mats = []
        for frame_number in range(1, len(transforms_limited) + 1):
            prefix_len = scheduled_prefix_len(
                frame_number, len(transforms_limited), delay, prefix_stride
            )
            if prefix_len not in prefix_cache:
                locked = published_solver_mats if lock_published_prefix else None
                prefix_cache[prefix_len] = solve_output_mats_for_prefix(prefix_len, locked)
            output_mat = prefix_cache[prefix_len][frame_number - 1]
            output_mats.append(output_mat)
            if lock_published_prefix:
                published_solver_mats.append(output_to_solver_domain(output_mat))
        add_ms(timing, "output_matrix_total_ms", t_output_matrix)

    args.log.parent.mkdir(parents=True, exist_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as out, args.log.open("w", newline="", encoding="utf-8") as log:
        writer = csv.writer(out)
        writer.writerow(MATRIX_HEADER)
        log_writer = csv.DictWriter(log, fieldnames=log_fieldnames)
        log_writer.writeheader()
        write_identity_row(writer, log_writer)
        timing["first_row_elapsed_ms"] = (time.perf_counter() - total_t0) * 1000.0
        if len(output_mats) != len(details_rows):
            raise RuntimeError(f"matrix/detail length mismatch: {len(output_mats)} vs {len(details_rows)}")
        for row_index, (mat, detail_row) in enumerate(zip(output_mats, details_rows), start=1):
            write_output_row(writer, log_writer, mat, detail_row)
            if args.flush_each_row:
                out.flush()
            if row_index == 1:
                timing["first_solved_row_elapsed_ms"] = (time.perf_counter() - total_t0) * 1000.0
        timing["last_row_elapsed_ms"] = (time.perf_counter() - total_t0) * 1000.0
    timing["motion_rows"] = len(details_rows)
    timing["frames_written"] = len(output_mats) + 1
    timing["total_elapsed_ms"] = (time.perf_counter() - total_t0) * 1000.0
    write_timing_summary(args.timing_summary, timing)
    return len(output_mats) + 1


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
    if args.matrix_mode in {"offline_lp_rigid", "bounded_delay_lp_rigid", "local_window_lp_rigid"}:
        rows_written = write_offline_lp_rigid(args, cap, prev_gray, width, height, post_geometry)
        cap.release()
        print(f"rows_written: {rows_written}")
        print(f"input: {args.input}")
        print(f"output: {args.output}")
        print(f"output_convention: {args.output_convention}")
        print(f"log: {args.log}")
        return 0
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
            "output_convention",
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
                "output_convention": args.output_convention,
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
                if args.matrix_mode == "window_correction_cpu_style":
                    output_mat = cumulative @ np.linalg.inv(desired_pose)
                else:
                    output_mat = desired_pose @ np.linalg.inv(cumulative)
            device_mat = prepare_output_matrix(post_geometry @ output_mat, args.output_convention)
            writer.writerow([frame_index, *matrix_cells(device_mat)])
            if args.flush_each_row:
                out.flush()
            log_writer.writerow(
                {
                    "frame_index": frame_index,
                    "matrix_mode": args.matrix_mode,
                    "output_convention": args.output_convention,
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
    print(f"output_convention: {args.output_convention}")
    print(f"log: {args.log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
