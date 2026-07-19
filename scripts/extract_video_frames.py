from __future__ import annotations

import argparse
from pathlib import Path

import cv2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract selected frames from one video.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--frames", required=True, help="Comma-separated 0-based frame indices")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    frame_ids = [int(item.strip()) for item in args.frames.split(",") if item.strip()]
    wanted = set(frame_ids)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(args.input))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open input video: {args.input}")

    frame_index = 0
    saved = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if frame_index in wanted:
            output = args.out_dir / f"{args.label}_{frame_index:04d}.png"
            cv2.imwrite(str(output), frame)
            print(f"saved: {output}")
            saved += 1
        frame_index += 1
        if saved >= len(wanted):
            break
    cap.release()
    print(f"frames_seen: {frame_index}")
    print(f"frames_saved: {saved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
