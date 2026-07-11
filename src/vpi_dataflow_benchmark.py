from __future__ import annotations

import argparse
import csv
import math
import statistics
import time
from pathlib import Path

import cv2
import numpy as np


STAGE_FIELDS = [
    "wrap_ms",
    "convert_in_ms",
    "warp_ms",
    "convert_out_ms",
    "readback_ms",
    "bgr_output_ms",
    "total_process_ms",
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Break down OpenCV/VPI perspective-warp dataflow costs for the Jetson EIS pipeline."
    )
    parser.add_argument("--input", required=True, type=Path, help="Input video path")
    parser.add_argument("--out-dir", required=True, type=Path, help="Output directory")
    parser.add_argument("--summary", type=Path, default=None, help="Summary CSV path")
    parser.add_argument("--per-frame", type=Path, default=None, help="Optional per-frame CSV path")
    parser.add_argument(
        "--backend",
        required=True,
        choices=["opencv_cpu", "vpi_cpu", "vpi_cuda", "vpi_vic"],
        help="Backend to benchmark",
    )
    parser.add_argument("--max-frames", type=int, default=0, help="Limit processed frames; 0 means all frames")
    parser.add_argument("--warmup-frames", type=int, default=5, help="Frames excluded from timing statistics")
    parser.add_argument(
        "--vpi-convert-backend",
        choices=["cpu", "cuda", "vic"],
        default="cuda",
        help="Backend used for VPI BGR/RGB/NV12 format conversions",
    )
    parser.add_argument(
        "--write-video",
        action="store_true",
        help="Write warped output video. Disabled by default to avoid mixing encoder cost into benchmark.",
    )
    return parser.parse_args()


def make_eis_like_matrix(frame_index: int, width: int, height: int) -> np.ndarray:
    """Create a deterministic transform that mimics an EIS compensation warp."""
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


def mean(values) -> float:
    return float(statistics.mean(values)) if values else 0.0


def median(values) -> float:
    return float(statistics.median(values)) if values else 0.0


def elapsed_ms(t0: float, t1: float) -> float:
    return (t1 - t0) * 1000.0


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
    output_path = args.out_dir / f"dataflow_{args.backend}.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"Cannot open output video: {output_path}")
    return writer, str(output_path)


def empty_stage_row(frame_index: int, backend: str) -> dict:
    row = {"frame_index": frame_index, "backend": backend}
    for field in STAGE_FIELDS:
        row[field] = 0.0
    return row


def benchmark_opencv_cpu(args):
    cap, width, height, fps, input_frame_count = open_capture(args.input)
    writer, output_path = maybe_open_writer(args, width, height, fps)

    frame_rows = []
    processed = 0
    total_t0 = time.perf_counter()
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if args.max_frames and processed >= args.max_frames:
            break

        matrix = make_eis_like_matrix(processed, width, height)
        row = empty_stage_row(processed, args.backend)

        t0 = time.perf_counter()
        warped = cv2.warpPerspective(
            frame,
            matrix,
            (width, height),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT,
        )
        t1 = time.perf_counter()
        row["warp_ms"] = elapsed_ms(t0, t1)
        row["total_process_ms"] = row["warp_ms"]

        if writer is not None:
            writer.write(warped)
        frame_rows.append(row)
        processed += 1

    total_t1 = time.perf_counter()
    cap.release()
    if writer is not None:
        writer.release()

    return summarize(args, width, height, fps, input_frame_count, processed, frame_rows, total_t1 - total_t0, output_path)


def benchmark_vpi(args):
    import vpi

    backend_map = {
        "vpi_cpu": vpi.Backend.CPU,
        "vpi_cuda": vpi.Backend.CUDA,
        "vpi_vic": vpi.Backend.VIC,
    }
    convert_backend_map = {
        "cpu": vpi.Backend.CPU,
        "cuda": vpi.Backend.CUDA,
        "vic": vpi.Backend.VIC,
    }
    warp_backend = backend_map[args.backend]
    convert_backend = convert_backend_map[args.vpi_convert_backend]

    cap, width, height, fps, input_frame_count = open_capture(args.input)
    writer, output_path = maybe_open_writer(args, width, height, fps)

    frame_rows = []
    processed = 0
    total_t0 = time.perf_counter()
    while True:
        ok, frame_bgr = cap.read()
        if not ok:
            break
        if args.max_frames and processed >= args.max_frames:
            break

        matrix = make_eis_like_matrix(processed, width, height)
        row = empty_stage_row(processed, args.backend)

        process_t0 = time.perf_counter()

        t0 = time.perf_counter()
        frame_vpi = vpi.asimage(frame_bgr)
        t1 = time.perf_counter()
        row["wrap_ms"] = elapsed_ms(t0, t1)

        t0 = time.perf_counter()
        with convert_backend:
            frame_nv12 = frame_vpi.convert(vpi.Format.NV12_ER)
        t1 = time.perf_counter()
        row["convert_in_ms"] = elapsed_ms(t0, t1)

        t0 = time.perf_counter()
        with warp_backend:
            warped_nv12 = frame_nv12.perspwarp(matrix)
        t1 = time.perf_counter()
        row["warp_ms"] = elapsed_ms(t0, t1)

        t0 = time.perf_counter()
        with convert_backend:
            warped_rgb = warped_nv12.convert(vpi.Format.RGB8)
        t1 = time.perf_counter()
        row["convert_out_ms"] = elapsed_ms(t0, t1)

        t0 = time.perf_counter()
        with warped_rgb.rlock_cpu() as data_rgb:
            output_rgb = np.array(data_rgb, copy=True)
        t1 = time.perf_counter()
        row["readback_ms"] = elapsed_ms(t0, t1)

        if writer is not None:
            t0 = time.perf_counter()
            writer.write(cv2.cvtColor(output_rgb, cv2.COLOR_RGB2BGR))
            t1 = time.perf_counter()
            row["bgr_output_ms"] = elapsed_ms(t0, t1)

        process_t1 = time.perf_counter()
        row["total_process_ms"] = elapsed_ms(process_t0, process_t1)

        frame_rows.append(row)
        processed += 1

    total_t1 = time.perf_counter()
    cap.release()
    if writer is not None:
        writer.release()

    return summarize(args, width, height, fps, input_frame_count, processed, frame_rows, total_t1 - total_t0, output_path)


def measured_rows(args, frame_rows):
    warmup = min(args.warmup_frames, len(frame_rows))
    return frame_rows[warmup:]


def summarize(args, width, height, fps, input_frame_count, processed, frame_rows, total_time_s, output_path):
    rows = measured_rows(args, frame_rows)
    total_values = [row["total_process_ms"] for row in rows]
    summary = {
        "backend": args.backend,
        "input": str(args.input),
        "width": width,
        "height": height,
        "input_fps": f"{fps:.3f}",
        "input_frame_count": input_frame_count,
        "processed_frames": processed,
        "warmup_frames": min(args.warmup_frames, processed),
        "measured_frames": len(rows),
        "vpi_convert_backend": args.vpi_convert_backend if args.backend.startswith("vpi_") else "",
        "avg_total_process_ms": f"{mean(total_values):.3f}",
        "median_total_process_ms": f"{median(total_values):.3f}",
        "p90_total_process_ms": f"{percentile(total_values, 0.90):.3f}",
        "p99_total_process_ms": f"{percentile(total_values, 0.99):.3f}",
        "effective_fps_from_avg": f"{(1000.0 / mean(total_values)) if mean(total_values) > 0 else 0.0:.3f}",
        "total_wall_time_s": f"{total_time_s:.3f}",
        "write_video": int(args.write_video),
        "output_path": output_path,
        "note": (
            "OpenCV row measures warpPerspective only. VPI row breaks down host-observed BGR wrap, "
            "BGR/RGB->NV12 conversion, perspwarp, RGB conversion, and CPU readback; stage values may include "
            "backend synchronization effects, so total_process_ms is the primary end-to-end number."
        ),
    }
    for field in STAGE_FIELDS:
        values = [row[field] for row in rows]
        summary[f"avg_{field}"] = f"{mean(values):.3f}"
        summary[f"p90_{field}"] = f"{percentile(values, 0.90):.3f}"
    return summary, frame_rows


def write_per_frame(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["frame_index", "backend"] + STAGE_FIELDS
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: f"{value:.3f}" if isinstance(value, float) else value for key, value in row.items()})


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
    if args.per_frame is None:
        args.per_frame = args.out_dir / f"per_frame_{args.backend}.csv"

    if args.backend == "opencv_cpu":
        summary, frame_rows = benchmark_opencv_cpu(args)
    else:
        summary, frame_rows = benchmark_vpi(args)

    append_summary(args.summary, summary)
    write_per_frame(args.per_frame, frame_rows)

    print("VPI dataflow benchmark finished")
    for key, value in summary.items():
        print(f"{key}: {value}")
    print(f"summary: {args.summary}")
    print(f"per_frame: {args.per_frame}")


if __name__ == "__main__":
    main()
