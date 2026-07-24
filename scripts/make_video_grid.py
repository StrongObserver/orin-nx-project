from __future__ import annotations

import argparse
import math
from pathlib import Path

import cv2


def parse_item(text: str) -> tuple[str, Path]:
    if "|" not in text:
        raise ValueError("--item must use label|path")
    label, path = text.split("|", 1)
    return label, Path(path)


def draw_label(frame, text: str) -> None:
    cv2.putText(frame, text, (18, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(frame, text, (16, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (255, 255, 255), 2, cv2.LINE_AA)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a labeled grid video from multiple synchronized inputs.")
    parser.add_argument("--item", action="append", required=True, help="label|path")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--columns", type=int, default=2)
    parser.add_argument("--max-frames", type=int, default=0)
    parser.add_argument("--cell-width", type=int, default=640)
    parser.add_argument("--cell-height", type=int, default=360)
    args = parser.parse_args()

    items = [parse_item(item) for item in args.item]
    if args.columns <= 0:
        raise ValueError("--columns must be positive")
    caps = []
    for label, path in items:
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video for {label}: {path}")
        caps.append(cap)

    fps = float(caps[0].get(cv2.CAP_PROP_FPS) or 30.0)
    rows = int(math.ceil(len(items) / args.columns))
    output_size = (args.columns * args.cell_width, rows * args.cell_height)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(args.output), cv2.VideoWriter_fourcc(*"mp4v"), fps, output_size)
    if not writer.isOpened():
        raise RuntimeError(f"Cannot open output video: {args.output}")

    frames_written = 0
    while True:
        frames = []
        for (label, _), cap in zip(items, caps):
            ok, frame = cap.read()
            if not ok:
                frames = []
                break
            frame = cv2.resize(frame, (args.cell_width, args.cell_height), interpolation=cv2.INTER_AREA)
            draw_label(frame, label)
            frames.append(frame)
        if not frames:
            break
        if args.max_frames and frames_written >= args.max_frames:
            break
        blank = frames[0].copy()
        blank[:] = 0
        while len(frames) < rows * args.columns:
            frames.append(blank.copy())
        row_images = []
        for row_index in range(rows):
            start = row_index * args.columns
            row_images.append(cv2.hconcat(frames[start : start + args.columns]))
        writer.write(cv2.vconcat(row_images))
        frames_written += 1

    for cap in caps:
        cap.release()
    writer.release()
    print(f"output: {args.output}")
    print(f"frames_written: {frames_written}")
    print(f"output_size: {output_size[0]}x{output_size[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
