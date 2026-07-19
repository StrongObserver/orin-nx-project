from __future__ import annotations

import argparse
from pathlib import Path

import cv2


def parse_item(text: str) -> tuple[str, Path]:
    if "|" not in text:
        raise ValueError("--item must use label|path")
    label, path = text.split("|", 1)
    return label, Path(path)


def read_frame_at(path: Path, fraction: float):
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {path}")
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    index = max(0, min(max(0, count - 1), int(round((count - 1) * fraction)))) if count else 0
    cap.set(cv2.CAP_PROP_POS_FRAMES, index)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise RuntimeError(f"Cannot read frame {index}: {path}")
    return frame, index


def draw_label(frame, text: str):
    out = frame.copy()
    cv2.putText(out, text, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(out, text, (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a contact sheet from sampled video frames.")
    parser.add_argument("--item", action="append", required=True, help="label|path")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fractions", default="0.1,0.3,0.5,0.7,0.9")
    parser.add_argument("--thumb-width", type=int, default=320)
    parser.add_argument("--thumb-height", type=int, default=180)
    args = parser.parse_args()

    items = [parse_item(item) for item in args.item]
    fractions = [float(item.strip()) for item in args.fractions.split(",") if item.strip()]
    rows = []
    for label, path in items:
        thumbs = []
        for fraction in fractions:
            frame, idx = read_frame_at(path, fraction)
            thumb = cv2.resize(frame, (args.thumb_width, args.thumb_height), interpolation=cv2.INTER_AREA)
            thumbs.append(draw_label(thumb, f"{label} f{idx}"))
        rows.append(cv2.hconcat(thumbs))
    sheet = cv2.vconcat(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(args.output), sheet)
    print(f"output: {args.output}")
    print(f"rows: {len(rows)}")
    print(f"cols: {len(fractions)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
