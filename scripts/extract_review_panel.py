from __future__ import annotations

import argparse
from pathlib import Path

import cv2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract one equal-width panel from a review video.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--columns", type=int, default=3)
    parser.add_argument("--index", type=int, required=True, help="0-based panel index")
    parser.add_argument("--max-frames", type=int, default=0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.columns <= 0:
        raise ValueError("--columns must be positive")
    if args.index < 0 or args.index >= args.columns:
        raise ValueError(f"--index must be in [0, {args.columns - 1}]")

    cap = cv2.VideoCapture(str(args.input))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open input video: {args.input}")

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    panel_width = width // args.columns
    x0 = panel_width * args.index
    x1 = panel_width * (args.index + 1) if args.index < args.columns - 1 else width
    output_size = (x1 - x0, height)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(args.output), cv2.VideoWriter_fourcc(*"mp4v"), fps, output_size)
    if not writer.isOpened():
        raise RuntimeError(f"Cannot open output video: {args.output}")

    frames_written = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if args.max_frames and frames_written >= args.max_frames:
            break
        writer.write(frame[:, x0:x1])
        frames_written += 1

    cap.release()
    writer.release()
    print(f"input: {args.input}")
    print(f"output: {args.output}")
    print(f"panel_index: {args.index}")
    print(f"panel_size: {output_size[0]}x{output_size[1]}")
    print(f"fps: {fps:.6f}")
    print(f"frames_written: {frames_written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
