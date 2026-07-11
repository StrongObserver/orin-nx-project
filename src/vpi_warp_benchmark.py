import argparse
import csv
import math
import statistics
import time
from pathlib import Path

import cv2
import numpy as np


def parse_args():
    parser = argparse.ArgumentParser(description="Benchmark OpenCV CPU warpPerspective against VPI perspective warp backends.")
    parser.add_argument("--input", required=True, type=Path, help="Input video path")
    parser.add_argument("--out-dir", required=True, type=Path, help="Output directory")
    parser.add_argument("--summary", type=Path, default=None, help="Summary CSV path")
    parser.add_argument(
        "--backend",
        required=True,
        choices=["opencv_cpu", "vpi_cpu", "vpi_cuda", "vpi_vic"],
        help="Backend to benchmark",
    )
    parser.add_argument("--max-frames", type=int, default=0, help="Limit processed frames; 0 means all frames")
    parser.add_argument("--warmup-frames", type=int, default=5, help="Frames excluded from timing statistics")
    parser.add_argument("--write-video", action="store_true", help="Write warped output video for visual sanity check")
    return parser.parse_args()


def make_eis_like_matrix(frame_index: int, width: int, height: int) -> np.ndarray:
    """Create a small deterministic transform similar to EIS compensation stress.

    This is not a full stabilizer. It gives every backend the same repeatable
    per-frame geometric warp so that timing is comparable.
    """
    t = frame_index / 15.0
    angle = math.sin(t * 0.9) * math.radians(1.8)
    scale = 0.965 + 0.01 * math.cos(t * 0.7)
    dx = math.sin(t * 1.3) * width * 0.018
    dy = math.cos(t * 1.1) * height * 0.018

    cos_a = math.cos(angle) * scale
    sin_a = math.sin(angle) * scale
    cx = width / 2.0
    cy = height / 2.0

    translate_to_origin = np.array([[1, 0, -cx], [0, 1, -cy], [0, 0, 1]], dtype=np.float64)
    affine = np.array([[cos_a, -sin_a, dx], [sin_a, cos_a, dy], [0, 0, 1]], dtype=np.float64)
    translate_back = np.array([[1, 0, cx], [0, 1, cy], [0, 0, 1]], dtype=np.float64)
    return translate_back @ affine @ translate_to_origin


def percentile(values, ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * ratio))))
    return float(ordered[index])


def open_capture(input_path: Path):
    cap = cv2.VideoCapture(str(input_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open input video: {input_path}")
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    return cap, width, height, fps, frame_count


def maybe_open_writer(args, width: int, height: int, fps: float):
    if not args.write_video:
        return None, ""
    output_path = args.out_dir / f"warp_{args.backend}.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"Cannot open output video: {output_path}")
    return writer, str(output_path)


def benchmark_opencv_cpu(args):
    cap, width, height, fps, input_frame_count = open_capture(args.input)
    writer, output_path = maybe_open_writer(args, width, height, fps)

    measured_ms = []
    processed = 0
    total_t0 = time.perf_counter()
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if args.max_frames and processed >= args.max_frames:
            break

        matrix = make_eis_like_matrix(processed, width, height)
        t0 = time.perf_counter()
        warped = cv2.warpPerspective(
            frame,
            matrix,
            (width, height),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT,
        )
        t1 = time.perf_counter()

        if processed >= args.warmup_frames:
            measured_ms.append((t1 - t0) * 1000.0)
        if writer is not None:
            writer.write(warped)
        processed += 1

    total_t1 = time.perf_counter()
    cap.release()
    if writer is not None:
        writer.release()

    return summarize(args, width, height, fps, input_frame_count, processed, measured_ms, total_t1 - total_t0, output_path)


def benchmark_vpi(args):
    import vpi

    backend_map = {
        "vpi_cpu": vpi.Backend.CPU,
        "vpi_cuda": vpi.Backend.CUDA,
        "vpi_vic": vpi.Backend.VIC,
    }
    backend = backend_map[args.backend]

    cap, width, height, fps, input_frame_count = open_capture(args.input)
    writer, output_path = maybe_open_writer(args, width, height, fps)

    measured_ms = []
    processed = 0
    total_t0 = time.perf_counter()
    while True:
        ok, frame_bgr = cap.read()
        if not ok:
            break
        if args.max_frames and processed >= args.max_frames:
            break

        matrix = make_eis_like_matrix(processed, width, height)

        t0 = time.perf_counter()
        with vpi.Backend.CUDA:
            frame_vpi = vpi.asimage(frame_bgr).convert(vpi.Format.NV12_ER)
        with backend:
            warped = frame_vpi.perspwarp(matrix)
        with vpi.Backend.CUDA:
            warped = warped.convert(vpi.Format.RGB8)
        with warped.rlock_cpu() as data_rgb:
            output_rgb = np.array(data_rgb, copy=True)
        t1 = time.perf_counter()

        if processed >= args.warmup_frames:
            measured_ms.append((t1 - t0) * 1000.0)
        if writer is not None:
            writer.write(cv2.cvtColor(output_rgb, cv2.COLOR_RGB2BGR))
        processed += 1

    total_t1 = time.perf_counter()
    cap.release()
    if writer is not None:
        writer.release()

    return summarize(args, width, height, fps, input_frame_count, processed, measured_ms, total_t1 - total_t0, output_path)


def summarize(args, width, height, fps, input_frame_count, processed, measured_ms, total_time_s, output_path):
    avg_ms = float(statistics.mean(measured_ms)) if measured_ms else 0.0
    median_ms = float(statistics.median(measured_ms)) if measured_ms else 0.0
    p90_ms = percentile(measured_ms, 0.90)
    p99_ms = percentile(measured_ms, 0.99)
    effective_fps = 1000.0 / avg_ms if avg_ms > 0 else 0.0
    return {
        "backend": args.backend,
        "input": str(args.input),
        "width": width,
        "height": height,
        "input_fps": f"{fps:.3f}",
        "input_frame_count": input_frame_count,
        "processed_frames": processed,
        "warmup_frames": min(args.warmup_frames, processed),
        "measured_frames": len(measured_ms),
        "avg_process_ms": f"{avg_ms:.3f}",
        "median_process_ms": f"{median_ms:.3f}",
        "p90_process_ms": f"{p90_ms:.3f}",
        "p99_process_ms": f"{p99_ms:.3f}",
        "effective_fps_from_avg": f"{effective_fps:.3f}",
        "total_wall_time_s": f"{total_time_s:.3f}",
        "write_video": int(args.write_video),
        "output_path": output_path,
        "note": "VPI timing includes BGR->NV12 conversion, warp, RGB conversion, and CPU readback; OpenCV timing measures warpPerspective only.",
    }


def append_summary(path: Path, row: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def main():
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    if args.summary is None:
        args.summary = args.out_dir / "summary.csv"

    if args.backend == "opencv_cpu":
        row = benchmark_opencv_cpu(args)
    else:
        row = benchmark_vpi(args)

    append_summary(args.summary, row)
    print("VPI warp benchmark finished")
    for key, value in row.items():
        print(f"{key}: {value}")
    print(f"summary: {args.summary}")


if __name__ == "__main__":
    main()
