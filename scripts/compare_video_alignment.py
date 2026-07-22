from __future__ import annotations

import argparse
import csv
from pathlib import Path

import cv2
import numpy as np


def read_gray_frames(path: Path, max_frames: int) -> list[np.ndarray]:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {path}")
    frames: list[np.ndarray] = []
    while True:
        if max_frames and len(frames) >= max_frames:
            break
        ok, frame = cap.read()
        if not ok:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frames.append(gray.astype(np.float32))
    cap.release()
    return frames


def mean_abs_for_offset(a_frames: list[np.ndarray], b_frames: list[np.ndarray], offset: int) -> tuple[int, float]:
    values: list[float] = []
    for a_index, a in enumerate(a_frames):
        b_index = a_index + offset
        if b_index < 0 or b_index >= len(b_frames):
            continue
        b = b_frames[b_index]
        if a.shape != b.shape:
            raise RuntimeError(f"Frame shape differs: {a.shape} vs {b.shape}")
        values.append(float(np.mean(np.abs(a - b))))
    return len(values), float(np.mean(values)) if values else 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Check temporal and spatial alignment between two videos.")
    parser.add_argument("--a", type=Path, required=True)
    parser.add_argument("--b", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--max-frames", type=int, default=180)
    parser.add_argument("--max-offset", type=int, default=5)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    a_frames = read_gray_frames(args.a, args.max_frames)
    b_frames = read_gray_frames(args.b, args.max_frames)
    if not a_frames or not b_frames:
        raise RuntimeError("No frames read")

    offset_rows = []
    for offset in range(-args.max_offset, args.max_offset + 1):
        compared, mean_abs_gray = mean_abs_for_offset(a_frames, b_frames, offset)
        offset_rows.append(
            {
                "offset_b_minus_a": offset,
                "frames_compared": compared,
                "mean_abs_gray": f"{mean_abs_gray:.6f}",
            }
        )

    best_offset = min(offset_rows, key=lambda row: float(row["mean_abs_gray"]))
    with (args.out_dir / "temporal_offset_scan.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(offset_rows[0].keys()))
        writer.writeheader()
        writer.writerows(offset_rows)

    phase_rows = []
    n = min(len(a_frames), len(b_frames))
    hann = cv2.createHanningWindow((a_frames[0].shape[1], a_frames[0].shape[0]), cv2.CV_32F)
    for idx in range(n):
        shift, response = cv2.phaseCorrelate(a_frames[idx] * hann, b_frames[idx] * hann)
        phase_rows.append(
            {
                "frame": idx,
                "shift_x_b_to_a": f"{float(shift[0]):.6f}",
                "shift_y_b_to_a": f"{float(shift[1]):.6f}",
                "response": f"{float(response):.6f}",
            }
        )

    with (args.out_dir / "phase_correlation.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(phase_rows[0].keys()))
        writer.writeheader()
        writer.writerows(phase_rows)

    shifts_x = np.array([float(row["shift_x_b_to_a"]) for row in phase_rows], dtype=np.float64)
    shifts_y = np.array([float(row["shift_y_b_to_a"]) for row in phase_rows], dtype=np.float64)
    responses = np.array([float(row["response"]) for row in phase_rows], dtype=np.float64)
    summary = {
        "a": str(args.a),
        "b": str(args.b),
        "a_frames": len(a_frames),
        "b_frames": len(b_frames),
        "best_offset_b_minus_a": int(best_offset["offset_b_minus_a"]),
        "best_offset_mean_abs_gray": best_offset["mean_abs_gray"],
        "shift_x_abs_mean": f"{float(np.mean(np.abs(shifts_x))):.6f}",
        "shift_x_abs_p95": f"{float(np.percentile(np.abs(shifts_x), 95)):.6f}",
        "shift_y_abs_mean": f"{float(np.mean(np.abs(shifts_y))):.6f}",
        "shift_y_abs_p95": f"{float(np.percentile(np.abs(shifts_y), 95)):.6f}",
        "phase_response_mean": f"{float(np.mean(responses)):.6f}",
        "phase_response_p05": f"{float(np.percentile(responses, 5)):.6f}",
    }
    with (args.out_dir / "summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary.keys()))
        writer.writeheader()
        writer.writerow(summary)

    for key, value in summary.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
