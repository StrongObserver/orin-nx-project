from __future__ import annotations

import argparse
import csv
from pathlib import Path

import cv2
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Measure edge-connected near-black border area per video frame.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--threshold", type=int, default=8)
    parser.add_argument("--max-frames", type=int, default=0)
    parser.add_argument("--sample-worst", type=int, default=8)
    return parser.parse_args()


def edge_connected_black_ratio(frame: np.ndarray, threshold: int) -> tuple[float, np.ndarray]:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mask = (gray <= threshold).astype(np.uint8)
    h, w = mask.shape
    flood = np.zeros((h + 2, w + 2), dtype=np.uint8)
    connected = np.zeros_like(mask)
    work = mask.copy()
    seeds = []
    for x in range(w):
        if work[0, x]:
            seeds.append((x, 0))
        if work[h - 1, x]:
            seeds.append((x, h - 1))
    for y in range(h):
        if work[y, 0]:
            seeds.append((0, y))
        if work[y, w - 1]:
            seeds.append((w - 1, y))
    for seed in seeds:
        x, y = seed
        if work[y, x] == 0:
            continue
        before = work.copy()
        cv2.floodFill(work, flood, seedPoint=seed, newVal=0)
        connected[(before == 1) & (work == 0)] = 1
    return float(connected.mean()), connected


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(args.input))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open input video: {args.input}")

    rows = []
    sample_frames: list[tuple[int, float, np.ndarray, np.ndarray]] = []
    frame_index = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if args.max_frames and frame_index >= args.max_frames:
            break
        ratio, connected = edge_connected_black_ratio(frame, args.threshold)
        rows.append({"frame": frame_index, "black_border_ratio": f"{ratio:.9f}"})
        if args.sample_worst > 0:
            sample_frames.append((frame_index, ratio, frame.copy(), connected.copy()))
        frame_index += 1
    cap.release()

    frame_csv = args.out_dir / "black_border_frames.csv"
    with frame_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["frame", "black_border_ratio"])
        writer.writeheader()
        writer.writerows(rows)

    values = np.array([float(row["black_border_ratio"]) for row in rows], dtype=np.float64)
    summary = {
        "input": str(args.input),
        "frames": len(rows),
        "threshold": args.threshold,
        "mean_black_border_ratio": f"{float(values.mean()) if len(values) else 0.0:.9f}",
        "p95_black_border_ratio": f"{float(np.percentile(values, 95)) if len(values) else 0.0:.9f}",
        "max_black_border_ratio": f"{float(values.max()) if len(values) else 0.0:.9f}",
        "frames_gt_0p001": int(np.sum(values > 0.001)) if len(values) else 0,
        "frames_gt_0p01": int(np.sum(values > 0.01)) if len(values) else 0,
    }
    summary_csv = args.out_dir / "summary.csv"
    with summary_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary.keys()))
        writer.writeheader()
        writer.writerow(summary)

    sample_frames.sort(key=lambda item: item[1], reverse=True)
    for frame_idx, ratio, frame, connected in sample_frames[: args.sample_worst]:
        overlay = frame.copy()
        overlay[connected.astype(bool)] = (0, 0, 255)
        cv2.putText(
            overlay,
            f"f={frame_idx} black={ratio:.5f}",
            (12, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        cv2.imwrite(str(args.out_dir / f"worst_{frame_idx:04d}.jpg"), overlay)

    print(f"frames: {frame_csv}")
    print(f"summary: {summary_csv}")
    for key, value in summary.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
