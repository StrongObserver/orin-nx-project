from __future__ import annotations

import argparse
import csv
import statistics
from pathlib import Path

import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare two planar YUV420 raw streams per plane.")
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--width", type=int, required=True)
    parser.add_argument("--height", type=int, required=True)
    parser.add_argument("--frames", type=int, default=0)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def percentile(values: list[float], pct: float) -> float:
    return float(np.percentile(np.asarray(values, dtype=np.float64), pct)) if values else 0.0


def main() -> int:
    args = parse_args()
    frame_bytes = args.width * args.height * 3 // 2
    ref_frames = args.reference.stat().st_size // frame_bytes
    cand_frames = args.candidate.stat().st_size // frame_bytes
    frame_count = min(ref_frames, cand_frames)
    if args.frames > 0:
        frame_count = min(frame_count, args.frames)
    if frame_count <= 0:
        raise RuntimeError("no complete comparable YUV420 frames")
    y_size = args.width * args.height
    c_size = y_size // 4
    values: dict[str, list[float]] = {"y": [], "u": [], "v": []}
    with args.reference.open("rb") as ref, args.candidate.open("rb") as cand:
        for _ in range(frame_count):
            ref_raw = ref.read(frame_bytes)
            cand_raw = cand.read(frame_bytes)
            offsets = [(0, y_size), (y_size, y_size + c_size), (y_size + c_size, frame_bytes)]
            for plane, (start, end) in zip(("y", "u", "v"), offsets):
                a = np.frombuffer(ref_raw[start:end], dtype=np.uint8).astype(np.int16)
                b = np.frombuffer(cand_raw[start:end], dtype=np.uint8).astype(np.int16)
                values[plane].append(float(np.mean(np.abs(a - b))))
    row: dict[str, object] = {
        "reference": str(args.reference),
        "candidate": str(args.candidate),
        "reference_frames": ref_frames,
        "candidate_frames": cand_frames,
        "frames_compared": frame_count,
    }
    for plane in ("y", "u", "v"):
        row[f"{plane}_mae_mean"] = f"{statistics.mean(values[plane]):.6f}"
        row[f"{plane}_mae_p95"] = f"{percentile(values[plane], 95):.6f}"
        row[f"{plane}_mae_max"] = f"{max(values[plane]):.6f}"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(row.keys()))
        writer.writeheader()
        writer.writerow(row)
    print(row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
