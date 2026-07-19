from __future__ import annotations

import argparse
from pathlib import Path

import cv2


def crop_resize(frame, crop_ratio: float):
    if crop_ratio >= 1.0:
        return frame
    h, w = frame.shape[:2]
    crop_w = max(2, int(round(w * crop_ratio)))
    crop_h = max(2, int(round(h * crop_ratio)))
    x0 = (w - crop_w) // 2
    y0 = (h - crop_h) // 2
    cropped = frame[y0 : y0 + crop_h, x0 : x0 + crop_w]
    return cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LANCZOS4)


def main() -> int:
    parser = argparse.ArgumentParser(description="Post-process a stabilized video with reflect padding and optional fixed crop.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--crop-ratio", type=float, default=1.0)
    parser.add_argument("--reflect-pad", type=int, default=0)
    parser.add_argument("--max-frames", type=int, default=0)
    args = parser.parse_args()

    cap = cv2.VideoCapture(str(args.input))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open input: {args.input}")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    ok, first = cap.read()
    if not ok:
        raise RuntimeError("Cannot read first frame")
    h, w = first.shape[:2]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(args.output), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    if not writer.isOpened():
        raise RuntimeError(f"Cannot open output: {args.output}")

    def process(frame):
        out = frame
        if args.reflect_pad > 0:
            pad = int(args.reflect_pad)
            out = cv2.copyMakeBorder(out, pad, pad, pad, pad, cv2.BORDER_REFLECT_101)
            out = cv2.resize(out, (w, h), interpolation=cv2.INTER_LANCZOS4)
        out = crop_resize(out, args.crop_ratio)
        return out

    frames_written = 0
    writer.write(process(first))
    frames_written += 1
    while True:
        if args.max_frames and frames_written >= args.max_frames:
            break
        ok, frame = cap.read()
        if not ok:
            break
        writer.write(process(frame))
        frames_written += 1

    cap.release()
    writer.release()
    print(f"output: {args.output}")
    print(f"frames_written: {frames_written}")
    print(f"fps: {fps}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
