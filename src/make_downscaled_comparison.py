import argparse
import time
from pathlib import Path

import cv2


def draw_label(frame, text, origin=(20, 40)):
    x, y = origin
    cv2.putText(frame, text, (x + 2, y + 2), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 2, cv2.LINE_AA)


def draw_reference(frame):
    h, w = frame.shape[:2]
    color = (0, 255, 255)
    cv2.line(frame, (w // 2, 0), (w // 2, h), color, 1, cv2.LINE_AA)
    cv2.line(frame, (0, h // 2), (w, h // 2), color, 1, cv2.LINE_AA)
    cv2.rectangle(frame, (12, 12), (w - 13, h - 13), color, 1, cv2.LINE_AA)


def main():
    parser = argparse.ArgumentParser(description="Create side-by-side comparison from a high-res original and a stabilized clip.")
    parser.add_argument("--original-highres", required=True, type=Path, help="Original source video, optionally higher resolution")
    parser.add_argument("--stabilized", required=True, type=Path, help="Stabilized video")
    parser.add_argument("--output", required=True, type=Path, help="Side-by-side comparison output")
    parser.add_argument("--width", type=int, default=1920, help="Comparison pane width")
    parser.add_argument("--height", type=int, default=1080, help="Comparison pane height")
    parser.add_argument("--left-label", default="Original input", help="Left label")
    parser.add_argument("--right-label", default="Stabilized output", help="Right label")
    parser.add_argument("--no-guides", action="store_true", help="Disable center/border guides")
    args = parser.parse_args()

    cap_left = cv2.VideoCapture(str(args.original_highres))
    cap_right = cv2.VideoCapture(str(args.stabilized))
    if not cap_left.isOpened():
        raise RuntimeError(f"Cannot open original video: {args.original_highres}")
    if not cap_right.isOpened():
        raise RuntimeError(f"Cannot open stabilized video: {args.stabilized}")

    fps = cap_right.get(cv2.CAP_PROP_FPS) or cap_left.get(cv2.CAP_PROP_FPS) or 30.0
    left_frames = int(cap_left.get(cv2.CAP_PROP_FRAME_COUNT))
    right_frames = int(cap_right.get(cv2.CAP_PROP_FRAME_COUNT))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(args.output), fourcc, fps, (args.width * 2, args.height))
    if not writer.isOpened():
        raise RuntimeError(f"Cannot open output video: {args.output}")

    frames_written = 0
    t0 = time.perf_counter()
    while True:
        ok_left, left = cap_left.read()
        ok_right, right = cap_right.read()
        if not ok_left or not ok_right:
            break

        if left.shape[1] != args.width or left.shape[0] != args.height:
            left = cv2.resize(left, (args.width, args.height), interpolation=cv2.INTER_AREA)
        if right.shape[1] != args.width or right.shape[0] != args.height:
            right = cv2.resize(right, (args.width, args.height), interpolation=cv2.INTER_LINEAR)

        if not args.no_guides:
            draw_reference(left)
            draw_reference(right)
        draw_label(left, args.left_label)
        draw_label(right, args.right_label)

        writer.write(cv2.hconcat([left, right]))
        frames_written += 1

    total_s = time.perf_counter() - t0
    cap_left.release()
    cap_right.release()
    writer.release()

    print("Downscaled side-by-side comparison finished")
    print(f"original_highres: {args.original_highres}")
    print(f"stabilized: {args.stabilized}")
    print(f"output: {args.output}")
    print(f"width: {args.width}")
    print(f"height: {args.height}")
    print(f"fps: {fps}")
    print(f"original_frame_count: {left_frames}")
    print(f"stabilized_frame_count: {right_frames}")
    print(f"frames_written: {frames_written}")
    print(f"total_wall_time_s: {total_s:.3f}")


if __name__ == "__main__":
    main()
