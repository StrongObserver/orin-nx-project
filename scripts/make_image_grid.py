from __future__ import annotations

import argparse
from pathlib import Path

import cv2


def parse_item(text: str) -> tuple[str, Path]:
    if "|" not in text:
        raise ValueError("--item must use label|path")
    label, path = text.split("|", 1)
    return label, Path(path)


def draw_label(image, label: str):
    out = image.copy()
    cv2.putText(out, label, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(out, label, (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a simple labeled image grid.")
    parser.add_argument("--item", action="append", required=True, help="label|path")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--cell-width", type=int, default=320)
    parser.add_argument("--cell-height", type=int, default=180)
    args = parser.parse_args()

    images = []
    for label, path in [parse_item(item) for item in args.item]:
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            raise RuntimeError(f"Cannot read image: {path}")
        image = cv2.resize(image, (args.cell_width, args.cell_height), interpolation=cv2.INTER_AREA)
        images.append(draw_label(image, label))

    blank = images[0].copy()
    blank[:] = 0
    while len(images) % args.columns:
        images.append(blank.copy())
    rows = []
    for start in range(0, len(images), args.columns):
        rows.append(cv2.hconcat(images[start : start + args.columns]))
    grid = cv2.vconcat(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(args.output), grid)
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
