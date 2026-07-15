import argparse
import csv
import math
from pathlib import Path

import cv2
import numpy as np


def fixed_center_crop_and_resize(frame: np.ndarray, crop_ratio: float) -> np.ndarray:
    if crop_ratio <= 0 or crop_ratio > 1:
        raise ValueError("crop_ratio must be in (0, 1]")
    if crop_ratio == 1:
        return frame
    h, w = frame.shape[:2]
    crop_w = int(round(w * crop_ratio))
    crop_h = int(round(h * crop_ratio))
    x0 = (w - crop_w) // 2
    y0 = (h - crop_h) // 2
    cropped = frame[y0 : y0 + crop_h, x0 : x0 + crop_w]
    return cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)


def open_video(path: Path) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {path}")
    return cap


def transcode_variant(src: Path, dst: Path, crop_ratio: float) -> dict[str, float]:
    cap = open_video(src)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    dst.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(dst), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        cap.release()
        raise RuntimeError(f"Cannot open writer: {dst}")

    frames = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        writer.write(fixed_center_crop_and_resize(frame, crop_ratio))
        frames += 1
    cap.release()
    writer.release()
    return {"frames": frames, "fps": fps, "width": width, "height": height}


def video_quality_metrics(path: Path, max_samples: int) -> dict[str, float]:
    cap = open_video(path)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if frame_count <= 0:
        cap.release()
        raise RuntimeError(f"Cannot inspect empty video: {path}")

    sample_count = min(max_samples, frame_count)
    indices = np.linspace(0, frame_count - 1, sample_count, dtype=int)
    laplacian = []
    tenengrad = []
    luma = []
    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
        ok, frame = cap.read()
        if not ok:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        laplacian.append(float(cv2.Laplacian(gray, cv2.CV_64F).var()))
        gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        tenengrad.append(float(np.mean(gx * gx + gy * gy)))
        luma.append(float(np.mean(gray)))
    cap.release()

    def mean(values: list[float]) -> float:
        return float(np.mean(values)) if values else 0.0

    def percentile(values: list[float], pct: float) -> float:
        return float(np.percentile(values, pct)) if values else 0.0

    return {
        "frames": frame_count,
        "sampled_frames": len(laplacian),
        "laplacian_var_mean": mean(laplacian),
        "laplacian_var_p10": percentile(laplacian, 10),
        "laplacian_var_p50": percentile(laplacian, 50),
        "tenengrad_mean": mean(tenengrad),
        "tenengrad_p10": percentile(tenengrad, 10),
        "tenengrad_p50": percentile(tenengrad, 50),
        "mean_luma": mean(luma),
    }


def affine_motion_metrics(path: Path, max_frames: int) -> dict[str, float]:
    cap = open_video(path)
    ok, prev = cap.read()
    if not ok:
        cap.release()
        raise RuntimeError(f"Cannot read first frame: {path}")
    prev_gray = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)

    scales = []
    anisotropies = []
    shear_proxies = []
    translations = []
    rotations = []
    valid = 0
    total = 0
    while max_frames <= 0 or total < max_frames:
        ok, frame = cap.read()
        if not ok:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        total += 1

        pts = cv2.goodFeaturesToTrack(prev_gray, maxCorners=400, qualityLevel=0.01, minDistance=12, blockSize=3)
        if pts is None or len(pts) < 12:
            prev_gray = gray
            continue
        next_pts, status, _ = cv2.calcOpticalFlowPyrLK(prev_gray, gray, pts, None)
        if next_pts is None or status is None:
            prev_gray = gray
            continue
        mask = status.reshape(-1).astype(bool)
        src = pts.reshape(-1, 2)[mask]
        dst = next_pts.reshape(-1, 2)[mask]
        if len(src) < 12:
            prev_gray = gray
            continue
        mat, inliers = cv2.estimateAffine2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=3.0)
        if mat is None or inliers is None or int(np.sum(inliers)) < 12:
            prev_gray = gray
            continue

        linear = mat[:2, :2].astype(np.float64)
        trans = mat[:2, 2].astype(np.float64)
        try:
            singular = np.linalg.svd(linear, compute_uv=False)
        except np.linalg.LinAlgError:
            prev_gray = gray
            continue
        if singular[1] <= 1e-9:
            prev_gray = gray
            continue

        scale = float(np.sqrt(abs(np.linalg.det(linear))))
        anisotropy = float(singular[0] / singular[1])
        gram = linear.T @ linear
        mean_square_scale = float(np.trace(gram) * 0.5)
        shear_proxy = float(np.linalg.norm(gram - np.eye(2) * mean_square_scale, ord="fro"))
        rotation = float(np.degrees(np.arctan2(linear[1, 0] - linear[0, 1], linear[0, 0] + linear[1, 1])))

        scales.append(abs(scale - 1.0))
        anisotropies.append(abs(anisotropy - 1.0))
        shear_proxies.append(shear_proxy)
        translations.append(float(np.linalg.norm(trans)))
        rotations.append(abs(rotation))
        valid += 1
        prev_gray = gray

    cap.release()

    def mean(values: list[float]) -> float:
        return float(np.mean(values)) if values else 0.0

    def percentile(values: list[float], pct: float) -> float:
        return float(np.percentile(values, pct)) if values else 0.0

    return {
        "affine_pairs_total": total,
        "affine_pairs_valid": valid,
        "scale_abs_delta_mean": mean(scales),
        "scale_abs_delta_p95": percentile(scales, 95),
        "anisotropy_abs_delta_mean": mean(anisotropies),
        "anisotropy_abs_delta_p95": percentile(anisotropies, 95),
        "shear_proxy_mean": mean(shear_proxies),
        "shear_proxy_p95": percentile(shear_proxies, 95),
        "translation_norm_mean": mean(translations),
        "translation_norm_p95": percentile(translations, 95),
        "rotation_abs_deg_mean": mean(rotations),
        "rotation_abs_deg_p95": percentile(rotations, 95),
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def load_summary(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with path.open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return rows[0] if rows else {}


def load_eval_rows(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", newline="", encoding="utf-8") as f:
        return {row["name"]: row for row in csv.DictReader(f)}


def as_float(row: dict[str, str], key: str) -> float:
    try:
        return float(row.get(key, ""))
    except ValueError:
        return math.nan


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect blur and jello boundary diagnostics for selected gate clips.")
    parser.add_argument("--raw-dir", type=Path, default=Path("results/nus_running_gate_v1/raw_clips"))
    parser.add_argument("--stable-reference-dir", type=Path, default=Path("results/nus_running_gate_v1/stable_reference"))
    parser.add_argument("--current-dir", type=Path, default=Path("results/nus_running_gate_v1/lp_affine_trim010"))
    parser.add_argument("--current-suffix", default="lp_affine_trim010_crop85")
    parser.add_argument("--out-dir", type=Path, default=Path("results/diagnostics/artifact_boundary_v1"))
    parser.add_argument("--clip", action="append", required=True, help="Clip stem, e.g. gate02_running_4")
    parser.add_argument("--max-samples", type=int, default=80)
    parser.add_argument("--variant-dir", action="append", default=[], help="name=path:suffix for extra pipeline variants")
    parser.add_argument("--affine-max-frames", type=int, default=300)
    args = parser.parse_args()

    rows = []
    affine_rows = []
    for clip in args.clip:
        raw = args.raw_dir / f"{clip}.mp4"
        stable_ref = args.stable_reference_dir / f"{clip}_stable.mp4"
        current = args.current_dir / f"{clip}_{args.current_suffix}.mp4"
        if not raw.exists():
            raise FileNotFoundError(raw)

        generated = [
            ("raw", raw, "source"),
        ]
        encode_only = args.out_dir / "blur_variants" / f"{clip}_encode_only.mp4"
        transcode_variant(raw, encode_only, 1.0)
        generated.append(("encode_only", encode_only, "read_write_mp4v_no_crop_no_warp"))
        for crop in (0.95, 0.85, 0.80):
            dst = args.out_dir / "blur_variants" / f"{clip}_crop{int(round(crop * 100)):02d}_only.mp4"
            transcode_variant(raw, dst, crop)
            generated.append((f"crop{int(round(crop * 100)):02d}_only", dst, f"center_crop_resize_{crop:.2f}"))
        if current.exists():
            generated.append(("current_lp_affine_trim010", current, "current_pipeline"))
        if stable_ref.exists():
            generated.append(("author_stable_reference", stable_ref, "dataset_reference"))

        for variant_arg in args.variant_dir:
            name, rest = variant_arg.split("=", 1)
            dir_text, suffix = rest.split(":", 1)
            path = Path(dir_text) / f"{clip}_{suffix}.mp4"
            if path.exists():
                generated.append((name, path, "pipeline_variant"))

        raw_metrics = None
        for variant_name, path, source_type in generated:
            metrics = video_quality_metrics(path, args.max_samples)
            if variant_name == "raw":
                raw_metrics = metrics
            lap_ratio = metrics["laplacian_var_mean"] / raw_metrics["laplacian_var_mean"] if raw_metrics else 1.0
            ten_ratio = metrics["tenengrad_mean"] / raw_metrics["tenengrad_mean"] if raw_metrics else 1.0
            rows.append(
                {
                    "clip": clip,
                    "variant": variant_name,
                    "source_type": source_type,
                    "path": str(path),
                    **{k: f"{v:.6f}" if isinstance(v, float) else v for k, v in metrics.items()},
                    "laplacian_ratio_vs_raw": f"{lap_ratio:.6f}",
                    "tenengrad_ratio_vs_raw": f"{ten_ratio:.6f}",
                }
            )
            affine = affine_motion_metrics(path, args.affine_max_frames)
            affine_rows.append(
                {
                    "clip": clip,
                    "variant": variant_name,
                    "source_type": source_type,
                    "path": str(path),
                    **{k: f"{v:.6f}" if isinstance(v, float) else v for k, v in affine.items()},
                }
            )

    write_csv(args.out_dir / "sharpness_metrics.csv", rows)
    write_csv(args.out_dir / "affine_motion_metrics.csv", affine_rows)
    print(f"Wrote sharpness metrics: {args.out_dir / 'sharpness_metrics.csv'}")
    print(f"Wrote affine motion metrics: {args.out_dir / 'affine_motion_metrics.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
