import argparse
import csv
import math
from pathlib import Path

import cv2
import numpy as np


SUMMARY_COLUMNS = [
    "name",
    "path",
    "width",
    "height",
    "fps",
    "pairs",
    "valid_pairs",
    "avg_tracked",
    "avg_inliers",
    "avg_inlier_ratio",
    "motion_p50",
    "motion_p95",
    "residual_p50",
    "residual_p95",
    "local_global_ratio_p50",
    "local_global_ratio_p95",
    "row_residual_range_p50",
    "row_residual_range_p95",
    "lower_half_feature_fraction",
    "dominant_dy_freq_hz",
    "running_band_energy_ratio",
    "scene_gate_class",
    "recommended_mode",
    "decision_reasons",
]


def open_video(path: Path) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {path}")
    return cap


def percentile(values: list[float], pct: float) -> float:
    return float(np.percentile(values, pct)) if values else 0.0


def mean(values: list[float]) -> float:
    return float(np.mean(values)) if values else 0.0


def estimate_pair(prev_gray: np.ndarray, gray: np.ndarray) -> dict[str, float] | None:
    pts = cv2.goodFeaturesToTrack(prev_gray, maxCorners=500, qualityLevel=0.01, minDistance=10, blockSize=3)
    if pts is None or len(pts) < 12:
        return None
    next_pts, status, _ = cv2.calcOpticalFlowPyrLK(prev_gray, gray, pts, None)
    if next_pts is None or status is None:
        return None

    mask = status.reshape(-1).astype(bool)
    src = pts.reshape(-1, 2)[mask]
    dst = next_pts.reshape(-1, 2)[mask]
    tracked = len(src)
    if tracked < 12:
        return None

    mat, inliers = cv2.estimateAffinePartial2D(
        src,
        dst,
        method=cv2.RANSAC,
        ransacReprojThreshold=3.0,
        maxIters=2000,
        confidence=0.99,
    )
    if mat is None or inliers is None:
        return None

    inlier_mask = inliers.reshape(-1).astype(bool)
    inliers_count = int(np.sum(inlier_mask))
    if inliers_count < 12:
        return None

    src_h = np.hstack([src, np.ones((tracked, 1), dtype=np.float32)])
    pred = (mat @ src_h.T).T
    residual = dst - pred
    residual_norm = np.linalg.norm(residual, axis=1)
    inlier_residual_norm = residual_norm[inlier_mask]

    h = prev_gray.shape[0]
    band_medians = []
    for lo, hi in ((0.0, 1.0 / 3.0), (1.0 / 3.0, 2.0 / 3.0), (2.0 / 3.0, 1.0)):
        band_mask = inlier_mask & (src[:, 1] >= lo * h) & (src[:, 1] < hi * h)
        if np.sum(band_mask) >= 6:
            band_medians.append(np.median(residual[band_mask], axis=0))
    row_range = 0.0
    if len(band_medians) >= 2:
        for i in range(len(band_medians)):
            for j in range(i + 1, len(band_medians)):
                row_range = max(row_range, float(np.linalg.norm(band_medians[i] - band_medians[j])))

    dx = float(mat[0, 2])
    dy = float(mat[1, 2])
    a = float(mat[0, 0])
    b = float(mat[1, 0])
    da = math.degrees(math.atan2(b, a))
    motion = math.hypot(dx, dy)
    residual_p95 = percentile(inlier_residual_norm.tolist(), 95)
    local_global_ratio = residual_p95 / max(1.0, motion)
    lower_half_fraction = float(np.mean(src[:, 1] >= 0.5 * h)) if tracked > 0 else 0.0

    return {
        "tracked": float(tracked),
        "inliers": float(inliers_count),
        "inlier_ratio": float(inliers_count / max(1, tracked)),
        "dx": dx,
        "dy": dy,
        "da_deg": da,
        "motion": motion,
        "residual_p50": percentile(inlier_residual_norm.tolist(), 50),
        "residual_p95": residual_p95,
        "local_global_ratio": local_global_ratio,
        "row_residual_range": row_range,
        "lower_half_fraction": lower_half_fraction,
    }


def frequency_features(dy_values: list[float], fps: float) -> tuple[float, float]:
    if len(dy_values) < 16 or fps <= 0:
        return 0.0, 0.0
    arr = np.asarray(dy_values, dtype=np.float64)
    arr = arr - np.mean(arr)
    if np.max(np.abs(arr)) < 1e-6:
        return 0.0, 0.0
    spec = np.abs(np.fft.rfft(arr)) ** 2
    freqs = np.fft.rfftfreq(len(arr), d=1.0 / fps)
    if len(spec) <= 1:
        return 0.0, 0.0
    spec[0] = 0.0
    dom_idx = int(np.argmax(spec))
    total = float(np.sum(spec))
    band_mask = (freqs >= 2.5) & (freqs <= 5.0)
    band_ratio = float(np.sum(spec[band_mask]) / total) if total > 0 else 0.0
    return float(freqs[dom_idx]), band_ratio


def classify(summary: dict[str, float]) -> tuple[str, str, str]:
    reasons = []
    motion_p95 = summary["motion_p95"]
    local_ratio_p95 = summary["local_global_ratio_p95"]
    row_range_p95 = summary["row_residual_range_p95"]
    running_band = summary["running_band_energy_ratio"]
    inlier_ratio = summary["avg_inlier_ratio"]

    high_motion = motion_p95 >= 12.0
    moderate_motion = motion_p95 >= 8.0
    high_local_residual = local_ratio_p95 >= 0.55
    row_varying = row_range_p95 >= 1.8
    running_frequency = running_band >= 0.25
    weak_conf = inlier_ratio < 0.70

    if high_motion:
        reasons.append(f"motion_p95={motion_p95:.2f}px")
    if high_local_residual:
        reasons.append(f"local/global_p95={local_ratio_p95:.2f}")
    if row_varying:
        reasons.append(f"row_residual_p95={row_range_p95:.2f}px")
    if running_frequency:
        reasons.append(f"2.5-5Hz_energy={running_band:.2f}")
    if weak_conf:
        reasons.append(f"inlier_ratio={inlier_ratio:.2f}")

    if high_motion and (high_local_residual or row_varying or running_frequency):
        return "challenge_degrade", "weak_similarity_or_off_rs_mesh_needed", "; ".join(reasons)
    if moderate_motion and row_varying and (high_local_residual or running_frequency):
        return "global_model_risk", "similarity_or_scene_gate_review", "; ".join(reasons)
    if weak_conf:
        return "global_model_risk", "similarity_or_scene_gate_review", "; ".join(reasons)
    return "normal_candidate", "standard_similarity_or_affine_allowed", "no_high_risk_signal"


def analyze_video(path: Path, max_frames: int) -> dict[str, str]:
    cap = open_video(path)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    ok, prev = cap.read()
    if not ok:
        cap.release()
        raise RuntimeError(f"Cannot read first frame: {path}")
    prev_gray = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)

    rows = []
    pairs = 0
    while max_frames <= 0 or pairs < max_frames:
        ok, frame = cap.read()
        if not ok:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        pair = estimate_pair(prev_gray, gray)
        if pair is not None:
            rows.append(pair)
        prev_gray = gray
        pairs += 1
    cap.release()

    dy_values = [row["dy"] for row in rows]
    dom_freq, band_ratio = frequency_features(dy_values, fps)
    summary_float = {
        "motion_p50": percentile([row["motion"] for row in rows], 50),
        "motion_p95": percentile([row["motion"] for row in rows], 95),
        "residual_p50": percentile([row["residual_p50"] for row in rows], 50),
        "residual_p95": percentile([row["residual_p95"] for row in rows], 95),
        "local_global_ratio_p50": percentile([row["local_global_ratio"] for row in rows], 50),
        "local_global_ratio_p95": percentile([row["local_global_ratio"] for row in rows], 95),
        "row_residual_range_p50": percentile([row["row_residual_range"] for row in rows], 50),
        "row_residual_range_p95": percentile([row["row_residual_range"] for row in rows], 95),
        "lower_half_feature_fraction": mean([row["lower_half_fraction"] for row in rows]),
        "avg_tracked": mean([row["tracked"] for row in rows]),
        "avg_inliers": mean([row["inliers"] for row in rows]),
        "avg_inlier_ratio": mean([row["inlier_ratio"] for row in rows]),
        "dominant_dy_freq_hz": dom_freq,
        "running_band_energy_ratio": band_ratio,
    }
    scene_class, recommended_mode, reasons = classify(summary_float)
    return {
        "name": path.stem,
        "path": str(path),
        "width": str(width),
        "height": str(height),
        "fps": f"{fps:.3f}",
        "pairs": str(pairs),
        "valid_pairs": str(len(rows)),
        **{key: f"{value:.6f}" for key, value in summary_float.items()},
        "scene_gate_class": scene_class,
        "recommended_mode": recommended_mode,
        "decision_reasons": reasons,
    }


def collect_paths(args) -> list[Path]:
    paths = [Path(item) for item in args.input]
    for input_dir in args.input_dir:
        paths.extend(sorted(Path(input_dir).glob(args.pattern)))
    unique = []
    seen = set()
    for path in paths:
        resolved = str(path)
        if resolved not in seen:
            unique.append(path)
            seen.add(resolved)
    return unique


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute scene-gate risk signals for EIS input clips.")
    parser.add_argument("--input", action="append", default=[], help="Input video path. Can be repeated.")
    parser.add_argument("--input-dir", action="append", default=[], help="Directory to scan for videos.")
    parser.add_argument("--pattern", default="*.mp4")
    parser.add_argument("--max-frames", type=int, default=300)
    parser.add_argument("--output-csv", type=Path, required=True)
    args = parser.parse_args()

    paths = collect_paths(args)
    if not paths:
        raise RuntimeError("No input videos found")
    rows = []
    for path in paths:
        row = analyze_video(path, args.max_frames)
        rows.append(row)
        print(
            f"{row['name']}: {row['scene_gate_class']} -> {row['recommended_mode']} "
            f"({row['decision_reasons']})"
        )
    write_csv(args.output_csv, rows)
    print(f"Wrote scene gate diagnostics: {args.output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
