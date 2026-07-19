from __future__ import annotations

import argparse
import csv
from pathlib import Path

import cv2
import numpy as np


MATRIX_FIELDS = ["m00", "m01", "m02", "m10", "m11", "m12", "m20", "m21", "m22"]


def read_matrices(path: Path) -> list[np.ndarray]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    mats = []
    for row in rows:
        values = [float(row[field]) for field in MATRIX_FIELDS]
        mats.append(np.array(values, dtype=np.float64).reshape(3, 3))
    return mats


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply per-frame 3x3 matrices to a video with OpenCV warpPerspective.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-frames", type=int, default=0)
    parser.add_argument("--border-mode", choices=["zero", "reflect"], default="zero")
    args = parser.parse_args()

    mats = read_matrices(args.matrix)
    cap = cv2.VideoCapture(str(args.input))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open input: {args.input}")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(args.output), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"Cannot open output: {args.output}")

    border_mode = cv2.BORDER_CONSTANT if args.border_mode == "zero" else cv2.BORDER_REFLECT_101
    frame_index = 0
    while True:
        if args.max_frames and frame_index >= args.max_frames:
            break
        ok, frame = cap.read()
        if not ok:
            break
        mat = mats[frame_index] if frame_index < len(mats) else np.eye(3, dtype=np.float64)
        warped = cv2.warpPerspective(
            frame,
            mat,
            (width, height),
            flags=cv2.INTER_LINEAR,
            borderMode=border_mode,
            borderValue=0,
        )
        writer.write(warped)
        frame_index += 1
    cap.release()
    writer.release()
    print(f"output: {args.output}")
    print(f"frames_written: {frame_index}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
