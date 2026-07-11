import argparse
import time
from pathlib import Path

import cv2


def draw_label(frame, text, origin):
    x, y = origin
    cv2.putText(frame, text, (x + 2, y + 2), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)


def draw_reference(frame):
    h, w = frame.shape[:2]
    color = (0, 255, 255)
    cv2.line(frame, (w // 2, 0), (w // 2, h), color, 1, cv2.LINE_AA)
    cv2.line(frame, (0, h // 2), (w, h // 2), color, 1, cv2.LINE_AA)
    cv2.rectangle(frame, (8, 8), (w - 9, h - 9), color, 1, cv2.LINE_AA)


def make_comparison(original_path: Path, stabilized_path: Path, output_path: Path, draw_guides: bool):
    cap_left = cv2.VideoCapture(str(original_path))
    cap_right = cv2.VideoCapture(str(stabilized_path))
    if not cap_left.isOpened():
        raise RuntimeError(f"Cannot open original video: {original_path}")
    if not cap_right.isOpened():
        raise RuntimeError(f"Cannot open stabilized video: {stabilized_path}")

    width = int(cap_left.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap_left.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap_left.get(cv2.CAP_PROP_FPS) or 30.0
    left_frames = int(cap_left.get(cv2.CAP_PROP_FRAME_COUNT))
    right_frames = int(cap_right.get(cv2.CAP_PROP_FRAME_COUNT))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(output_path), fourcc, fps, (width * 2, height))
    if not writer.isOpened():
        raise RuntimeError(f"Cannot open output video: {output_path}")

    frames_written = 0
    t0 = time.perf_counter()
    while True:
        ok_left, left = cap_left.read()
        ok_right, right = cap_right.read()
        if not ok_left or not ok_right:
            break

        if right.shape[1] != width or right.shape[0] != height:
            right = cv2.resize(right, (width, height), interpolation=cv2.INTER_LINEAR)

        if draw_guides:
            draw_reference(left)
            draw_reference(right)

        draw_label(left, "Original shaky input", (20, 36))
        draw_label(right, "CPU stabilized baseline", (20, 36))

        combined = cv2.hconcat([left, right])
        writer.write(combined)
        frames_written += 1

    total_s = time.perf_counter() - t0
    cap_left.release()
    cap_right.release()
    writer.release()

    print("Side-by-side comparison finished")
    print(f"original: {original_path}")
    print(f"stabilized: {stabilized_path}")
    print(f"output: {output_path}")
    print(f"width: {width}")
    print(f"height: {height}")
    print(f"fps: {fps}")
    print(f"original_frame_count: {left_frames}")
    print(f"stabilized_frame_count: {right_frames}")
    print(f"frames_written: {frames_written}")
    print(f"total_wall_time_s: {total_s:.3f}")


def main():
    parser = argparse.ArgumentParser(description="Create side-by-side comparison video.")
    parser.add_argument("--original", required=True, type=Path, help="Original shaky input video")
    parser.add_argument("--stabilized", required=True, type=Path, help="Stabilized output video")
    parser.add_argument("--output", required=True, type=Path, help="Side-by-side output video")
    parser.add_argument("--no-guides", action="store_true", help="Do not draw center crosshair and border guide")
    args = parser.parse_args()

    make_comparison(args.original, args.stabilized, args.output, draw_guides=not args.no_guides)


if __name__ == "__main__":
    main()
