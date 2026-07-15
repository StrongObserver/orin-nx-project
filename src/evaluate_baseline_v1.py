import argparse
import csv
import json
import math
import time
from pathlib import Path

import cv2
import numpy as np


RESIDUAL_STD_PASS_THRESHOLD = 0.15
RESIDUAL_STD_ACCEPTABLE_THRESHOLD = 0.10
# The acceptance gate for acceleration spikes is non-regression: stabilized top-5%
# pose acceleration should not be worse than the original video.
SECOND_DIFF_TOP5_PASS_THRESHOLD = 0.0
SECOND_DIFF_TOP5_ACCEPTABLE_THRESHOLD = 0.0
SR_PASS_THRESHOLD = 1.2
SR_FAIL_THRESHOLD = 1.0
BLACK_BORDER_MEAN_PASS = 0.001
BLACK_BORDER_P95_FAIL = 0.01
CROP_LOSS_ACCEPTABLE = 0.10
CROP_LOSS_FAIL = 0.15


def resize_gray_for_estimation(frame_bgr: np.ndarray, estimate_scale: float) -> np.ndarray:
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    if estimate_scale == 1.0:
        return gray
    h, w = gray.shape[:2]
    return cv2.resize(
        gray,
        (max(16, int(round(w * estimate_scale))), max(16, int(round(h * estimate_scale)))),
        interpolation=cv2.INTER_AREA,
    )


def estimate_pair_motion(prev_gray: np.ndarray, curr_gray: np.ndarray, estimate_scale: float):
    min_distance = max(5, int(round(30 * estimate_scale)))
    prev_pts = cv2.goodFeaturesToTrack(
        prev_gray,
        maxCorners=300,
        qualityLevel=0.01,
        minDistance=min_distance,
        blockSize=3,
    )
    if prev_pts is None or len(prev_pts) < 8:
        return None, 0, 0

    curr_pts, status, _ = cv2.calcOpticalFlowPyrLK(prev_gray, curr_gray, prev_pts, None)
    if curr_pts is None or status is None:
        return None, 0, 0

    valid = status.reshape(-1) == 1
    prev_good = prev_pts[valid]
    curr_good = curr_pts[valid]
    if len(prev_good) < 8:
        return None, int(len(prev_good)), 0

    mat, inliers = cv2.estimateAffinePartial2D(
        prev_good,
        curr_good,
        method=cv2.RANSAC,
        ransacReprojThreshold=3.0,
        maxIters=2000,
        confidence=0.99,
    )
    if mat is None:
        return None, int(len(prev_good)), 0

    inlier_count = int(np.sum(inliers)) if inliers is not None else int(len(prev_good))
    dx = float(mat[0, 2] / estimate_scale)
    dy = float(mat[1, 2] / estimate_scale)
    da = float(math.atan2(mat[1, 0], mat[0, 0]))
    return (dx, dy, da), int(len(prev_good)), inlier_count


def black_border_ratio(frame_bgr: np.ndarray, threshold: int = 8) -> float:
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    black = (gray <= threshold).astype(np.uint8)
    num_labels, labels = cv2.connectedComponents(black, connectivity=8)
    if num_labels <= 1:
        return 0.0

    border_labels = set(np.unique(labels[0, :]))
    border_labels.update(np.unique(labels[-1, :]))
    border_labels.update(np.unique(labels[:, 0]))
    border_labels.update(np.unique(labels[:, -1]))
    border_labels.discard(0)
    if not border_labels:
        return 0.0

    border_black = np.isin(labels, list(border_labels))
    return float(np.mean(border_black))


def moving_average(curve: np.ndarray, radius: int) -> np.ndarray:
    if radius <= 0 or len(curve) == 0:
        return np.array(curve, copy=True)
    window_size = 2 * radius + 1
    filt = np.ones(window_size, dtype=np.float64) / window_size
    curve_pad = np.pad(curve, (radius, radius), mode="edge")
    return np.convolve(curve_pad, filt, mode="same")[radius:-radius]


def smooth_pose_sequence(pose: np.ndarray, radius: int) -> np.ndarray:
    smoothed = np.array(pose, copy=True)
    for i in range(pose.shape[1]):
        smoothed[:, i] = moving_average(pose[:, i], radius)
    return smoothed


def normalized_pose_norm(values: np.ndarray, angle_scale: float) -> np.ndarray:
    return np.sqrt(values[:, 0] ** 2 + values[:, 1] ** 2 + (values[:, 2] * angle_scale) ** 2)


def summarize_top_magnitudes(values: np.ndarray, top_k: int = 10, frame_offset: int = 1) -> str:
    if len(values) == 0:
        return ""
    top_k = min(top_k, len(values))
    indices = np.argsort(values)[-top_k:][::-1]
    return ";".join(f"{int(i + frame_offset)}:{float(values[i]):.6f}" for i in indices)


def summarize_motion(transforms: np.ndarray, residual_radius: int, angle_scale: float) -> dict:
    if transforms.size == 0:
        return {
            "valid_motion_frames": 0,
            "angle_scale_pixels": angle_scale,
            "dx_std": None,
            "dy_std": None,
            "da_std": None,
            "motion_energy": None,
            "motion_p95": None,
            "residual_trans_std": None,
            "residual_pose_energy": None,
            "pose_1st_derivative_std": None,
            "second_diff_mean": None,
            "second_diff_p95": None,
            "second_diff_top5_mean": None,
            "second_diff_max": None,
            "second_diff_top_frames": "",
            "legacy_jerk_diff_p95": None,
            "legacy_jerk_diff_top5_mean": None,
            "legacy_jerk_diff_top_frames": "",
        }

    dx = transforms[:, 0]
    dy = transforms[:, 1]
    da = transforms[:, 2]
    motion_mag = np.sqrt(dx * dx + dy * dy)
    motion_energy = dx * dx + dy * dy + (da * angle_scale) * (da * angle_scale)
    pose_1st_derivative = normalized_pose_norm(transforms, angle_scale)

    trajectory = np.cumsum(transforms, axis=0)
    smoothed_trajectory = smooth_pose_sequence(trajectory, residual_radius)
    residual = trajectory - smoothed_trajectory
    residual_trans = np.sqrt(residual[:, 0] ** 2 + residual[:, 1] ** 2)
    residual_pose = normalized_pose_norm(residual, angle_scale)

    # ``transforms`` are frame-to-frame pose deltas, i.e. first derivative of the
    # cumulative pose trajectory. Therefore the second derivative of pose is the
    # first difference of these deltas. The previous implementation used the
    # second difference of transforms, which is actually closer to the third
    # derivative / jerk of pose and made the acceptance metric over-sensitive.
    if len(transforms) >= 2:
        second = transforms[1:] - transforms[:-1]
        second_mag = normalized_pose_norm(second, angle_scale)
        top_n = max(1, int(math.ceil(len(second_mag) * 0.05)))
        second_top = np.sort(second_mag)[-top_n:]
        second_mean = float(np.mean(second_mag))
        second_p95 = float(np.percentile(second_mag, 95))
        second_top5_mean = float(np.mean(second_top))
        second_max = float(np.max(second_mag))
        second_top_frames = summarize_top_magnitudes(second_mag, top_k=10, frame_offset=1)
    else:
        second_mean = None
        second_p95 = None
        second_top5_mean = None
        second_max = None
        second_top_frames = ""

    if len(transforms) >= 3:
        legacy_jerk = transforms[:-2] - 2.0 * transforms[1:-1] + transforms[2:]
        legacy_jerk_mag = normalized_pose_norm(legacy_jerk, angle_scale)
        legacy_top_n = max(1, int(math.ceil(len(legacy_jerk_mag) * 0.05)))
        legacy_jerk_top = np.sort(legacy_jerk_mag)[-legacy_top_n:]
        legacy_jerk_p95 = float(np.percentile(legacy_jerk_mag, 95))
        legacy_jerk_top5_mean = float(np.mean(legacy_jerk_top))
        legacy_jerk_top_frames = summarize_top_magnitudes(legacy_jerk_mag, top_k=10, frame_offset=1)
    else:
        legacy_jerk_p95 = None
        legacy_jerk_top5_mean = None
        legacy_jerk_top_frames = ""

    return {
        "valid_motion_frames": int(len(transforms)),
        "angle_scale_pixels": float(angle_scale),
        "dx_std": float(np.std(dx)),
        "dy_std": float(np.std(dy)),
        "da_std": float(np.std(da)),
        "motion_energy": float(np.mean(motion_energy)),
        "motion_p95": float(np.percentile(motion_mag, 95)),
        "residual_trans_std": float(np.std(residual_trans)),
        "residual_pose_energy": float(np.mean(residual_pose * residual_pose)),
        "pose_1st_derivative_std": float(np.std(pose_1st_derivative)),
        "second_diff_mean": second_mean,
        "second_diff_p95": second_p95,
        "second_diff_top5_mean": second_top5_mean,
        "second_diff_max": second_max,
        "second_diff_top_frames": second_top_frames,
        "legacy_jerk_diff_p95": legacy_jerk_p95,
        "legacy_jerk_diff_top5_mean": legacy_jerk_top5_mean,
        "legacy_jerk_diff_top_frames": legacy_jerk_top_frames,
    }


def max_consecutive_over(values, threshold: float) -> int:
    best = 0
    current = 0
    for value in values:
        if value > threshold:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def summarize_invalid_mask_metrics(metrics_csv: Path) -> dict:
    values = []
    with metrics_csv.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if "invalid_mask_ratio" not in (reader.fieldnames or []):
            raise ValueError(f"metrics CSV has no invalid_mask_ratio column: {metrics_csv}")
        for row in reader:
            value = row.get("invalid_mask_ratio", "")
            if value != "":
                values.append(float(value))
    if not values:
        return {
            "avg_black_border_ratio": 0.0,
            "p95_black_border_ratio": 0.0,
            "max_black_border_ratio": 0.0,
            "max_consecutive_black_border_over_1pct": 0,
            "black_border_metric_source": str(metrics_csv),
        }
    arr = np.array(values, dtype=np.float64)
    return {
        "avg_black_border_ratio": float(np.mean(arr)),
        "p95_black_border_ratio": float(np.percentile(arr, 95)),
        "max_black_border_ratio": float(np.max(arr)),
        "max_consecutive_black_border_over_1pct": max_consecutive_over(arr, 0.01),
        "black_border_metric_source": str(metrics_csv),
    }


def affine_from_pose(dx: float, dy: float, da: float) -> np.ndarray:
    c = math.cos(float(da))
    s = math.sin(float(da))
    return np.array([[c, -s, float(dx)], [s, c, float(dy)], [0.0, 0.0, 1.0]], dtype=np.float64)


def pose_from_affine(mat: np.ndarray) -> np.ndarray:
    return np.array([float(mat[0, 2]), float(mat[1, 2]), math.atan2(float(mat[1, 0]), float(mat[0, 0]))], dtype=np.float64)


def top5_second_mean_from_transforms(transforms: np.ndarray, angle_scale: float) -> float:
    if len(transforms) < 2:
        return 0.0
    second = transforms[1:] - transforms[:-1]
    mag = normalized_pose_norm(second, angle_scale)
    top_n = max(1, int(math.ceil(len(mag) * 0.05)))
    return float(np.mean(np.sort(mag)[-top_n:]))


def summarize_cpu_pose_metrics(metrics_csv: Path, angle_scale: float = 0.0) -> dict:
    rows = []
    with metrics_csv.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        needed = {"dx", "dy", "da_rad", "raw_dx", "raw_dy", "raw_da_rad"}
        if not needed.issubset(set(reader.fieldnames or [])):
            return {}
        for row in reader:
            rows.append(row)
    if not rows:
        return {}

    effective_angle_scale = angle_scale if angle_scale > 0 else 1.0
    raw = np.array([[float(r["raw_dx"]), float(r["raw_dy"]), float(r["raw_da_rad"])] for r in rows], dtype=np.float64)
    stab = np.array([[float(r["dx"]), float(r["dy"]), float(r["da_rad"])] for r in rows], dtype=np.float64)

    s_mats = [np.eye(3, dtype=np.float64)] + [affine_from_pose(*pose) for pose in stab]
    effective = []
    for i, raw_pose in enumerate(raw):
        out = s_mats[i + 1] @ affine_from_pose(*raw_pose) @ np.linalg.inv(s_mats[i])
        effective.append(pose_from_affine(out))
    effective_np = np.asarray(effective, dtype=np.float64)

    raw_top5 = top5_second_mean_from_transforms(raw, effective_angle_scale)
    effective_top5 = top5_second_mean_from_transforms(effective_np, effective_angle_scale)
    stab_warp_top5 = top5_second_mean_from_transforms(stab, effective_angle_scale)
    return {
        "cpu_pose_raw_second_top5_mean": raw_top5,
        "cpu_pose_effective_second_top5_mean": effective_top5,
        "cpu_pose_stab_warp_second_top5_mean": stab_warp_top5,
        "cpu_pose_effective_second_top5_improve": safe_improvement(raw_top5, effective_top5),
        "cpu_pose_metric_source": str(metrics_csv),
    }


def analyze_video(video_path: Path, estimate_scale: float, max_frames: int, black_threshold: int, residual_radius: int, angle_scale: float, warmup_frames: int = 0) -> dict:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    ok, prev = cap.read()
    if not ok:
        raise RuntimeError(f"Cannot read first frame: {video_path}")

    prev_gray = resize_gray_for_estimation(prev, estimate_scale)
    transforms = []
    tracked_counts = []
    inlier_counts = []
    black_ratios = [black_border_ratio(prev, threshold=black_threshold)]
    frames_read = 1

    while True:
        if max_frames > 0 and frames_read >= max_frames:
            break
        ok, curr = cap.read()
        if not ok:
            break
        curr_gray = resize_gray_for_estimation(curr, estimate_scale)
        motion, tracked_count, inlier_count = estimate_pair_motion(prev_gray, curr_gray, estimate_scale)
        if motion is not None:
            transforms.append(motion)
        tracked_counts.append(tracked_count)
        inlier_counts.append(inlier_count)
        black_ratios.append(black_border_ratio(curr, threshold=black_threshold))
        prev_gray = curr_gray
        frames_read += 1

    cap.release()

    warmup_frames = max(0, int(warmup_frames))
    if warmup_frames > 0:
        transforms = transforms[warmup_frames:]
        tracked_counts = tracked_counts[warmup_frames:]
        inlier_counts = inlier_counts[warmup_frames:]
        black_ratios = black_ratios[min(warmup_frames, len(black_ratios)) :]

    transforms_np = np.array(transforms, dtype=np.float64)
    effective_angle_scale = float(angle_scale) if angle_scale > 0 else float(0.5 * math.hypot(width, height))
    summary = summarize_motion(transforms_np, residual_radius, effective_angle_scale)
    summary.update(
        {
            "video": str(video_path),
            "width": width,
            "height": height,
            "fps": fps,
            "reported_frame_count": frame_count,
            "frames_analyzed": frames_read,
            "warmup_frames_skipped": warmup_frames,
            "avg_tracked_features": float(np.mean(tracked_counts)) if tracked_counts else 0.0,
            "avg_inliers": float(np.mean(inlier_counts)) if inlier_counts else 0.0,
            "avg_black_border_ratio": float(np.mean(black_ratios)) if black_ratios else 0.0,
            "p95_black_border_ratio": float(np.percentile(black_ratios, 95)) if black_ratios else 0.0,
            "max_black_border_ratio": float(np.max(black_ratios)) if black_ratios else 0.0,
            "max_consecutive_black_border_over_1pct": max_consecutive_over(black_ratios, 0.01),
        }
    )
    return summary


def safe_ratio(before, after):
    if before is None or after is None or after <= 1e-12:
        return None
    return float(before / after)


def safe_improvement(before, after):
    if before is None or after is None or before <= 1e-12:
        return None
    return float(1.0 - after / before)


def safe_db(ratio):
    if ratio is None or ratio <= 1e-12:
        return None
    return float(10.0 * math.log10(ratio))


def classify_improvement(value, pass_threshold: float, acceptable_threshold: float) -> str:
    if value is None:
        return "unknown"
    if value >= pass_threshold:
        return "pass"
    if value >= acceptable_threshold:
        return "acceptable"
    if value >= 0.0:
        return "weak"
    return "fail"


def classify_sr(value) -> str:
    if value is None:
        return "unknown"
    if value >= SR_PASS_THRESHOLD:
        return "pass"
    if value >= SR_FAIL_THRESHOLD:
        return "weak"
    return "fail"


def classify_crop_loss(crop_loss_ratio) -> str:
    if crop_loss_ratio is None:
        return "unknown"
    eps = 1e-9
    if crop_loss_ratio < CROP_LOSS_ACCEPTABLE - eps:
        return "pass"
    if crop_loss_ratio <= CROP_LOSS_FAIL + eps:
        return "acceptable"
    return "fail"


def classify_black_border(stabilized_metrics: dict) -> str:
    mean_ratio = stabilized_metrics["avg_black_border_ratio"]
    p95_ratio = stabilized_metrics["p95_black_border_ratio"]
    consecutive_over_1pct = stabilized_metrics["max_consecutive_black_border_over_1pct"]
    if p95_ratio > BLACK_BORDER_P95_FAIL or consecutive_over_1pct >= 3:
        return "fail"
    if mean_ratio < BLACK_BORDER_MEAN_PASS:
        return "pass"
    return "acceptable"


def derive_objective_grade(result: dict) -> str:
    """Objective-only grade; subjective veto must still be checked manually."""
    failed = {
        result["sr_residual_pose_class"],
        result["residual_trans_std_class"],
        result["pose_1st_derivative_std_class"],
        result["second_diff_top5_mean_class"],
        result["crop_loss_class"],
        result["black_border_class"],
    }
    if "fail" in failed:
        return "D"
    if result["sr_residual_pose_class"] == "pass" and result["residual_trans_std_class"] == "pass" and result["second_diff_top5_mean_class"] == "pass" and result["crop_loss_class"] in {"pass", "acceptable"} and result["black_border_class"] == "pass":
        return "A_or_B_candidate"
    if "acceptable" in failed or "weak" in failed:
        return "C_candidate"
    return "B_candidate"


def derive_layered_acceptance(result: dict, scenario_role: str) -> str:
    """Layered EIS gate: hard degradation gates first, scene-dependent smoothness second.

    `objective_grade` intentionally remains the old single-score view for
    regression comparison.  This field records the more production-like reading:
    crop/black are hard gates; stability and smoothness are separate dimensions;
    challenge/stress clips should not be the only all-metrics hard gate.
    """
    if result["black_border_class"] == "fail":
        return "hard_fail_black_border"
    if result["crop_loss_class"] == "fail":
        return "hard_fail_crop"

    stability_ok = result["sr_residual_pose_class"] == "pass" and result["residual_trans_std_class"] == "pass"
    smoothness_ok = result["second_diff_top5_mean_class"] == "pass"
    if stability_ok and smoothness_ok:
        return "pass_all_objective_gates"
    if stability_ok and scenario_role in {"challenge", "diagnostic"}:
        return "challenge_stability_pass_smoothness_diagnostic"
    if stability_ok:
        return "stability_pass_smoothness_fail"
    return "stability_fail"


def evaluate_pair(name: str, original: Path, stabilized: Path, crop_ratio: float, estimate_scale: float, max_frames: int, black_threshold: int, residual_radius: int, angle_scale: float, scenario_role: str, mask_metrics_csv: Path | None = None, warmup_frames: int = 0) -> dict:
    t0 = time.perf_counter()
    original_metrics = analyze_video(original, estimate_scale, max_frames, black_threshold, residual_radius, angle_scale, warmup_frames)
    stabilized_metrics = analyze_video(stabilized, estimate_scale, max_frames, black_threshold, residual_radius, angle_scale, warmup_frames)
    if mask_metrics_csv is not None:
        stabilized_metrics.update(summarize_invalid_mask_metrics(mask_metrics_csv))
        stabilized_metrics.update(summarize_cpu_pose_metrics(mask_metrics_csv, angle_scale))
    t1 = time.perf_counter()

    crop_loss_ratio = None if crop_ratio <= 0 else float(1.0 - crop_ratio)
    result = {
        "name": name,
        "original": str(original),
        "stabilized": str(stabilized),
        "crop_ratio": crop_ratio,
        "crop_loss_ratio": crop_loss_ratio,
        "estimate_scale": estimate_scale,
        "max_frames": max_frames,
        "residual_radius": residual_radius,
        "angle_scale": angle_scale,
        "warmup_frames": int(max(0, warmup_frames)),
        "scenario_role": scenario_role,
        "original_metrics": original_metrics,
        "stabilized_metrics": stabilized_metrics,
        "stability_ratio_energy": safe_ratio(original_metrics["motion_energy"], stabilized_metrics["motion_energy"]),
        "sr_residual_pose": safe_ratio(original_metrics["residual_pose_energy"], stabilized_metrics["residual_pose_energy"]),
        "stability_ratio_dx_std": safe_ratio(original_metrics["dx_std"], stabilized_metrics["dx_std"]),
        "stability_ratio_dy_std": safe_ratio(original_metrics["dy_std"], stabilized_metrics["dy_std"]),
        "improve_residual_trans_std": safe_improvement(original_metrics["residual_trans_std"], stabilized_metrics["residual_trans_std"]),
        "improve_pose_1st_derivative_std": safe_improvement(original_metrics["pose_1st_derivative_std"], stabilized_metrics["pose_1st_derivative_std"]),
        "improve_second_diff_top5_mean": safe_improvement(original_metrics["second_diff_top5_mean"], stabilized_metrics["second_diff_top5_mean"]),
        "smoothness_ratio_second_p95": safe_ratio(original_metrics["second_diff_p95"], stabilized_metrics["second_diff_p95"]),
        "smoothness_ratio_second_top5_mean": safe_ratio(original_metrics["second_diff_top5_mean"], stabilized_metrics["second_diff_top5_mean"]),
        "legacy_improve_jerk_diff_top5_mean": safe_improvement(original_metrics["legacy_jerk_diff_top5_mean"], stabilized_metrics["legacy_jerk_diff_top5_mean"]),
        "legacy_smoothness_ratio_jerk_p95": safe_ratio(original_metrics["legacy_jerk_diff_p95"], stabilized_metrics["legacy_jerk_diff_p95"]),
        "eval_wall_time_s": float(t1 - t0),
    }
    result.update(
        {
            "sr_residual_pose_db": safe_db(result["sr_residual_pose"]),
            "stability_ratio_energy_db": safe_db(result["stability_ratio_energy"]),
            "sr_residual_pose_class": classify_sr(result["sr_residual_pose"]),
            "stability_ratio_energy_class": classify_sr(result["stability_ratio_energy"]),
            "residual_trans_std_class": classify_improvement(result["improve_residual_trans_std"], RESIDUAL_STD_PASS_THRESHOLD, RESIDUAL_STD_ACCEPTABLE_THRESHOLD),
            "pose_1st_derivative_std_class": classify_improvement(result["improve_pose_1st_derivative_std"], RESIDUAL_STD_PASS_THRESHOLD, RESIDUAL_STD_ACCEPTABLE_THRESHOLD),
            "second_diff_top5_mean_class": classify_improvement(result["improve_second_diff_top5_mean"], SECOND_DIFF_TOP5_PASS_THRESHOLD, SECOND_DIFF_TOP5_ACCEPTABLE_THRESHOLD),
            "crop_loss_class": classify_crop_loss(crop_loss_ratio),
            "black_border_class": classify_black_border(stabilized_metrics),
            "subjective_veto_required": "frame_shift/rollback/jello/local_distortion/continuous_black_border must be checked manually from side-by-side video",
        }
    )
    result["objective_grade"] = derive_objective_grade(result)
    result["layered_acceptance"] = derive_layered_acceptance(result, scenario_role)
    return result


def flatten_pair_result(result: dict) -> dict:
    original = result["original_metrics"]
    stabilized = result["stabilized_metrics"]
    return {
        "name": result["name"],
        "original": result["original"],
        "stabilized": result["stabilized"],
        "crop_ratio": result["crop_ratio"],
        "crop_loss_ratio": result["crop_loss_ratio"],
        "scenario_role": result["scenario_role"],
        "warmup_frames": result["warmup_frames"],
        "layered_acceptance": result["layered_acceptance"],
        "frames_analyzed": min(original["frames_analyzed"], stabilized["frames_analyzed"]),
        "orig_dx_std": original["dx_std"],
        "stab_dx_std": stabilized["dx_std"],
        "orig_dy_std": original["dy_std"],
        "stab_dy_std": stabilized["dy_std"],
        "orig_da_std": original["da_std"],
        "stab_da_std": stabilized["da_std"],
        "orig_motion_energy": original["motion_energy"],
        "stab_motion_energy": stabilized["motion_energy"],
        "stability_ratio_energy": result["stability_ratio_energy"],
        "stability_ratio_energy_db": result["stability_ratio_energy_db"],
        "stability_ratio_energy_class": result["stability_ratio_energy_class"],
        "orig_residual_trans_std": original["residual_trans_std"],
        "stab_residual_trans_std": stabilized["residual_trans_std"],
        "improve_residual_trans_std": result["improve_residual_trans_std"],
        "residual_trans_std_class": result["residual_trans_std_class"],
        "orig_residual_pose_energy": original["residual_pose_energy"],
        "stab_residual_pose_energy": stabilized["residual_pose_energy"],
        "sr_residual_pose": result["sr_residual_pose"],
        "sr_residual_pose_db": result["sr_residual_pose_db"],
        "sr_residual_pose_class": result["sr_residual_pose_class"],
        "orig_pose_1st_derivative_std": original["pose_1st_derivative_std"],
        "stab_pose_1st_derivative_std": stabilized["pose_1st_derivative_std"],
        "improve_pose_1st_derivative_std": result["improve_pose_1st_derivative_std"],
        "pose_1st_derivative_std_class": result["pose_1st_derivative_std_class"],
        "orig_second_top5_mean": original["second_diff_top5_mean"],
        "stab_second_top5_mean": stabilized["second_diff_top5_mean"],
        "improve_second_diff_top5_mean": result["improve_second_diff_top5_mean"],
        "second_diff_top5_mean_class": result["second_diff_top5_mean_class"],
        "orig_second_p95": original["second_diff_p95"],
        "stab_second_p95": stabilized["second_diff_p95"],
        "orig_second_top_frames": original.get("second_diff_top_frames", ""),
        "stab_second_top_frames": stabilized.get("second_diff_top_frames", ""),
        "smoothness_ratio_second_p95": result["smoothness_ratio_second_p95"],
        "orig_legacy_jerk_top5_mean": original.get("legacy_jerk_diff_top5_mean"),
        "stab_legacy_jerk_top5_mean": stabilized.get("legacy_jerk_diff_top5_mean"),
        "legacy_improve_jerk_diff_top5_mean": result.get("legacy_improve_jerk_diff_top5_mean"),
        "orig_legacy_jerk_p95": original.get("legacy_jerk_diff_p95"),
        "stab_legacy_jerk_p95": stabilized.get("legacy_jerk_diff_p95"),
        "legacy_smoothness_ratio_jerk_p95": result.get("legacy_smoothness_ratio_jerk_p95"),
        "orig_legacy_jerk_top_frames": original.get("legacy_jerk_diff_top_frames", ""),
        "stab_legacy_jerk_top_frames": stabilized.get("legacy_jerk_diff_top_frames", ""),
        "cpu_pose_raw_second_top5_mean": stabilized.get("cpu_pose_raw_second_top5_mean"),
        "cpu_pose_effective_second_top5_mean": stabilized.get("cpu_pose_effective_second_top5_mean"),
        "cpu_pose_stab_warp_second_top5_mean": stabilized.get("cpu_pose_stab_warp_second_top5_mean"),
        "cpu_pose_effective_second_top5_improve": stabilized.get("cpu_pose_effective_second_top5_improve"),
        "stab_avg_black_border_ratio": stabilized["avg_black_border_ratio"],
        "stab_p95_black_border_ratio": stabilized["p95_black_border_ratio"],
        "stab_max_black_border_ratio": stabilized["max_black_border_ratio"],
        "max_consecutive_black_border_over_1pct": stabilized["max_consecutive_black_border_over_1pct"],
        "black_border_class": result["black_border_class"],
        "crop_loss_class": result["crop_loss_class"],
        "objective_grade": result["objective_grade"],
        "orig_avg_tracked_features": original["avg_tracked_features"],
        "stab_avg_tracked_features": stabilized["avg_tracked_features"],
        "orig_avg_inliers": original["avg_inliers"],
        "stab_avg_inliers": stabilized["avg_inliers"],
        "eval_wall_time_s": result["eval_wall_time_s"],
    }


def parse_pair(pair_text: str):
    pair_text = pair_text.strip().strip('"').strip("'")
    parts = pair_text.split("|")
    if len(parts) not in {4, 5}:
        raise ValueError("--pair must use format: name|original_path|stabilized_path|crop_ratio[|scenario_role]")
    cleaned = [part.strip().strip('"').strip("'") for part in parts]
    name, original, stabilized, crop_ratio = cleaned[:4]
    scenario_role = cleaned[4] if len(cleaned) == 5 else None
    if scenario_role is not None and scenario_role not in {"gate", "challenge", "diagnostic"}:
        raise ValueError("scenario_role must be one of: gate, challenge, diagnostic")
    return name, Path(original), Path(stabilized), float(crop_ratio), scenario_role


def parse_named_path(text: str):
    text = text.strip().strip('"').strip("'")
    parts = text.split("|")
    if len(parts) != 2:
        raise ValueError("named path must use format: name|path")
    name, path = [part.strip().strip('"').strip("'") for part in parts]
    return name, Path(path)


def main():
    parser = argparse.ArgumentParser(description="Evaluate Baseline V1 EIS quality metrics for original/stabilized video pairs.")
    parser.add_argument("--pair", action="append", required=True, help="Format: name|original_path|stabilized_path|crop_ratio[|scenario_role]")
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-csv", required=True, type=Path)
    parser.add_argument("--mask-metrics", action="append", default=[], help="Optional format: name|cpu_stabilize_metrics_csv. Uses invalid_mask_ratio for black-border metrics of that pair")
    parser.add_argument("--estimate-scale", type=float, default=0.5, help="Downscale factor for metric motion estimation")
    parser.add_argument("--max-frames", type=int, default=600, help="Max frames per video to evaluate; <=0 means all frames")
    parser.add_argument("--black-threshold", type=int, default=8, help="Pixel threshold for black border detection")
    parser.add_argument("--residual-radius", type=int, default=45, help="Moving-average radius for intent trajectory used by residual metrics")
    parser.add_argument("--angle-scale", type=float, default=0.0, help="Pixel-equivalent scale for rotation when combining dx/dy/da norms; <=0 uses half image diagonal")
    parser.add_argument("--warmup-frames", type=int, default=0, help="Skip this many initial motion samples when computing image-motion proxy metrics")
    parser.add_argument("--scenario-role", choices=["gate", "challenge", "diagnostic"], default="gate", help="Evaluation role: gate requires all objective dimensions; challenge/diagnostic keep smoothness failures separate from hard degradation gates")
    args = parser.parse_args()

    mask_metrics_by_name = dict(parse_named_path(item) for item in args.mask_metrics)
    results = []
    for pair_text in args.pair:
        name, original, stabilized, crop_ratio, pair_role = parse_pair(pair_text)
        scenario_role = pair_role or args.scenario_role
        results.append(
            evaluate_pair(
                name,
                original,
                stabilized,
                crop_ratio,
                args.estimate_scale,
                args.max_frames,
                args.black_threshold,
                args.residual_radius,
                args.angle_scale,
                scenario_role,
                mask_metrics_by_name.get(name),
                args.warmup_frames,
            )
        )

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "metric_version": "baseline_v1_1_sop_aligned_image_motion_metrics",
        "thresholds": {
            "sr_pass": SR_PASS_THRESHOLD,
            "sr_fail_below": SR_FAIL_THRESHOLD,
            "residual_std_improvement_pass": RESIDUAL_STD_PASS_THRESHOLD,
            "residual_std_improvement_acceptable": RESIDUAL_STD_ACCEPTABLE_THRESHOLD,
            "second_diff_top5_improvement_pass": SECOND_DIFF_TOP5_PASS_THRESHOLD,
            "second_diff_top5_improvement_acceptable": SECOND_DIFF_TOP5_ACCEPTABLE_THRESHOLD,
            "crop_loss_pass_lt": CROP_LOSS_ACCEPTABLE,
            "crop_loss_fail_gt": CROP_LOSS_FAIL,
            "black_border_mean_pass_lt": BLACK_BORDER_MEAN_PASS,
            "black_border_p95_fail_gt": BLACK_BORDER_P95_FAIL,
        },
        "scenario_role": args.scenario_role,
        "warmup_frames": args.warmup_frames,
        "notes": {
            "stability_ratio_energy": "original motion_energy / stabilized motion_energy; >1 means stabilized video has lower estimated frame-to-frame motion energy.",
            "sr_residual_pose": "original residual_pose_energy / stabilized residual_pose_energy after low-pass intent trajectory removal; >1 means stabilized residual pose energy is lower.",
            "improve_residual_trans_std": "1 - stabilized residual_trans_std / original residual_trans_std; >=0.15 pass, 0.10~0.15 acceptable.",
            "pose_1st_derivative_std": "STD of normalized per-frame pose delta norm. Rotation da is scaled by --angle-scale before combining with dx/dy.",
            "second_diff_top5_mean": "Mean of the largest 5% normalized pose second-derivative magnitudes. Since measured transforms are frame-to-frame pose deltas, this is computed as the first difference of transforms.",
            "legacy_jerk_diff_top5_mean": "Diagnostic only: the old implementation's second difference of frame-to-frame transforms, closer to pose third derivative / jerk, not the acceptance gate.",
            "smoothness_ratio_second_p95": "original second-difference p95 / stabilized second-difference p95; >1 means fewer high-frequency acceleration spikes.",
            "crop_loss_ratio": "1 - crop_ratio; target <=0.15 for final EIS baseline.",
            "black_border_ratio": "Near-black connected components touching the image boundary only; mean <0.1% pass, p95 >1% or continuous frames over 1% fail.",
            "objective_grade": "Objective-only grade. Subjective veto items still require manual review: frame shift, rollback, jello/rolling shutter, local distortion, continuous black border.",
            "layered_acceptance": "Production-style layered reading: black/crop are hard gates; stability and smoothness are reported separately. challenge/diagnostic clips do not single-handedly hard-fail the baseline on image-motion smoothness proxy.",
        },
        "results": results,
    }
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    rows = [flatten_pair_result(result) for result in results]
    with args.output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote JSON: {args.output_json}")
    print(f"Wrote CSV: {args.output_csv}")
    for row in rows:
        print(
            f"{row['name']}: SR_pose={row['sr_residual_pose']:.3f}, "
            f"residual_improve={row['improve_residual_trans_std']:.3f}, "
            f"acc_top5_improve={row['improve_second_diff_top5_mean']:.3f}, "
            f"crop_loss={row['crop_loss_ratio']:.3f}, "
            f"black_p95={row['stab_p95_black_border_ratio']:.6f}, "
            f"grade={row['objective_grade']}, "
            f"layered={row['layered_acceptance']}"
        )


if __name__ == "__main__":
    main()
