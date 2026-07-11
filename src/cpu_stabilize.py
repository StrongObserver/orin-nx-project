import argparse
import csv
import math
import time
from pathlib import Path

import cv2
import numpy as np


def moving_average(curve: np.ndarray, radius: int) -> np.ndarray:
    window_size = 2 * radius + 1
    filt = np.ones(window_size, dtype=np.float32) / window_size
    curve_pad = np.pad(curve, (radius, radius), mode="edge")
    return np.convolve(curve_pad, filt, mode="same")[radius:-radius]


def smooth_trajectory(trajectory: np.ndarray, radius: int) -> np.ndarray:
    smoothed = np.copy(trajectory)
    for i in range(trajectory.shape[1]):
        smoothed[:, i] = moving_average(trajectory[:, i], radius)
    return smoothed


def fix_border(frame: np.ndarray, scale: float) -> np.ndarray:
    h, w = frame.shape[:2]
    mat = cv2.getRotationMatrix2D((w / 2, h / 2), 0, scale)
    return cv2.warpAffine(frame, mat, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def fixed_center_crop_and_resize(frame: np.ndarray, crop_ratio: float) -> np.ndarray:
    if crop_ratio <= 0 or crop_ratio > 1:
        raise ValueError("crop_ratio must be in (0, 1]")
    if crop_ratio == 1:
        return frame

    h, w = frame.shape[:2]
    crop_w = int(w * crop_ratio)
    crop_h = int(h * crop_ratio)
    x0 = (w - crop_w) // 2
    y0 = (h - crop_h) // 2
    cropped = frame[y0 : y0 + crop_h, x0 : x0 + crop_w]
    return cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)


def black_pixel_ratio(frame: np.ndarray, threshold: int = 8) -> float:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return float(np.mean(gray <= threshold))


class VPIWarpPerspective:
    def __init__(self, backend_name: str):
        import vpi

        backend_map = {
            "vpi_cpu": vpi.Backend.CPU,
            "vpi_cuda": vpi.Backend.CUDA,
            "vpi_vic": vpi.Backend.VIC,
        }
        if backend_name not in backend_map:
            raise ValueError(f"Unsupported VPI warp backend: {backend_name}")
        self.vpi = vpi
        self.backend = backend_map[backend_name]

    def warp_affine(self, frame_bgr: np.ndarray, mat_2x3: np.ndarray) -> np.ndarray:
        mat_3x3 = np.eye(3, dtype=np.float64)
        mat_3x3[:2, :] = mat_2x3.astype(np.float64)
        with self.vpi.Backend.CUDA:
            frame_vpi = self.vpi.asimage(frame_bgr).convert(self.vpi.Format.NV12_ER)
        with self.backend:
            warped = frame_vpi.perspwarp(mat_3x3)
        with self.vpi.Backend.CUDA:
            warped = warped.convert(self.vpi.Format.RGB8)
        with warped.rlock_cpu() as data_rgb:
            rgb = np.array(data_rgb, copy=True)
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def estimate_transform(prev_gray: np.ndarray, curr_gray: np.ndarray):
    prev_pts = cv2.goodFeaturesToTrack(
        prev_gray,
        maxCorners=200,
        qualityLevel=0.01,
        minDistance=30,
        blockSize=3,
    )
    if prev_pts is None or len(prev_pts) < 8:
        return np.array([0.0, 0.0, 0.0], dtype=np.float32), 0

    curr_pts, status, _ = cv2.calcOpticalFlowPyrLK(prev_gray, curr_gray, prev_pts, None)
    if curr_pts is None or status is None:
        return np.array([0.0, 0.0, 0.0], dtype=np.float32), 0

    valid = status.reshape(-1) == 1
    prev_good = prev_pts[valid]
    curr_good = curr_pts[valid]
    if len(prev_good) < 8:
        return np.array([0.0, 0.0, 0.0], dtype=np.float32), int(len(prev_good))

    mat, _ = cv2.estimateAffinePartial2D(prev_good, curr_good)
    if mat is None:
        return np.array([0.0, 0.0, 0.0], dtype=np.float32), int(len(prev_good))

    dx = mat[0, 2]
    dy = mat[1, 2]
    da = math.atan2(mat[1, 0], mat[0, 0])
    return np.array([dx, dy, da], dtype=np.float32), int(len(prev_good))


def stabilize_video(
    input_path: Path,
    output_path: Path,
    metrics_path: Path,
    smoothing_radius: int,
    border_scale: float,
    crop_ratio: float,
    warp_backend: str,
):
    cap = cv2.VideoCapture(str(input_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open input video: {input_path}")

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    ok, prev = cap.read()
    if not ok:
        raise RuntimeError("Cannot read first frame")
    prev_gray = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)

    transforms = []
    feature_counts = []
    estimate_times_ms = []

    while True:
        ok, curr = cap.read()
        if not ok:
            break
        curr_gray = cv2.cvtColor(curr, cv2.COLOR_BGR2GRAY)

        t0 = time.perf_counter()
        transform, n_features = estimate_transform(prev_gray, curr_gray)
        t1 = time.perf_counter()

        transforms.append(transform)
        feature_counts.append(n_features)
        estimate_times_ms.append((t1 - t0) * 1000.0)

        prev_gray = curr_gray

    cap.release()

    if not transforms:
        raise RuntimeError("Input video has too few frames")

    transforms = np.array(transforms, dtype=np.float32)

    trajectory = np.cumsum(transforms, axis=0)
    smoothed_trajectory = smooth_trajectory(trajectory, smoothing_radius)
    difference = smoothed_trajectory - trajectory
    transforms_smooth = transforms + difference

    output_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"Cannot open output video: {output_path}")

    cap = cv2.VideoCapture(str(input_path))
    ok, frame = cap.read()
    if not ok:
        raise RuntimeError("Cannot re-read first frame")
    writer.write(fixed_center_crop_and_resize(frame, crop_ratio))

    warp_times_ms = []
    black_ratios = []
    frames_written = 1
    black_ratios.append(black_pixel_ratio(fixed_center_crop_and_resize(frame, crop_ratio)))
    vpi_warper = None if warp_backend == "opencv_cpu" else VPIWarpPerspective(warp_backend)

    for i, transform in enumerate(transforms_smooth):
        ok, frame = cap.read()
        if not ok:
            break

        dx, dy, da = transform
        mat = np.array(
            [
                [math.cos(da), -math.sin(da), dx],
                [math.sin(da), math.cos(da), dy],
            ],
            dtype=np.float32,
        )

        t0 = time.perf_counter()
        if vpi_warper is None:
            stabilized = cv2.warpAffine(frame, mat, (width, height), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        else:
            stabilized = vpi_warper.warp_affine(frame, mat)
        stabilized = fix_border(stabilized, border_scale)
        stabilized = fixed_center_crop_and_resize(stabilized, crop_ratio)
        t1 = time.perf_counter()

        writer.write(stabilized)
        warp_times_ms.append((t1 - t0) * 1000.0)
        black_ratios.append(black_pixel_ratio(stabilized))
        frames_written += 1

    cap.release()
    writer.release()

    with metrics_path.open("w", newline="", encoding="utf-8") as f:
        csv_writer = csv.writer(f)
        csv_writer.writerow(["frame_index", "tracked_features", "estimate_ms", "warp_ms", "dx", "dy", "da_rad"])
        for i, transform in enumerate(transforms_smooth):
            warp_ms = warp_times_ms[i] if i < len(warp_times_ms) else ""
            csv_writer.writerow([i + 1, feature_counts[i], f"{estimate_times_ms[i]:.3f}", f"{warp_ms:.3f}" if warp_ms != "" else "", f"{transform[0]:.6f}", f"{transform[1]:.6f}", f"{transform[2]:.6f}"])

    summary = {
        "input": str(input_path),
        "output": str(output_path),
        "metrics": str(metrics_path),
        "width": width,
        "height": height,
        "fps": fps,
        "input_frame_count": frame_count,
        "frames_written": frames_written,
        "avg_estimate_ms": float(np.mean(estimate_times_ms)),
        "avg_warp_ms": float(np.mean(warp_times_ms)) if warp_times_ms else 0.0,
        "max_black_pixel_ratio": float(np.max(black_ratios)) if black_ratios else 0.0,
        "avg_black_pixel_ratio": float(np.mean(black_ratios)) if black_ratios else 0.0,
        "smoothing_radius": smoothing_radius,
        "border_scale": border_scale,
        "crop_ratio": crop_ratio,
        "warp_backend": warp_backend,
    }
    return summary


def main():
    parser = argparse.ArgumentParser(description="CPU baseline video stabilization with OpenCV.")
    parser.add_argument("--input", required=True, type=Path, help="Input shaky video path")
    parser.add_argument("--output", required=True, type=Path, help="Output stabilized video path")
    parser.add_argument("--metrics", required=True, type=Path, help="Output per-frame CSV metrics path")
    parser.add_argument("--smoothing-radius", type=int, default=45, help="Moving average radius for trajectory smoothing")
    parser.add_argument("--border-scale", type=float, default=1.00, help="Extra scale before final fixed crop")
    parser.add_argument("--crop-ratio", type=float, default=0.80, help="Fixed center crop ratio, then resize back to original size")
    parser.add_argument(
        "--warp-backend",
        choices=["opencv_cpu", "vpi_cpu", "vpi_cuda", "vpi_vic"],
        default="opencv_cpu",
        help="Backend for the per-frame geometric warp stage",
    )
    args = parser.parse_args()

    total_t0 = time.perf_counter()
    summary = stabilize_video(args.input, args.output, args.metrics, args.smoothing_radius, args.border_scale, args.crop_ratio, args.warp_backend)
    total_t1 = time.perf_counter()

    print("CPU stabilization baseline finished")
    for key, value in summary.items():
        print(f"{key}: {value}")
    print(f"total_wall_time_s: {total_t1 - total_t0:.3f}")


if __name__ == "__main__":
    main()
