from __future__ import annotations

import argparse
import csv
from pathlib import Path

import cv2
import numpy as np


def read_cell_vector(path: Path, gx: int, gy: int, strength: float) -> tuple[float, float]:
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if int(row["gx"]) == gx and int(row["gy"]) == gy:
                # Remap map stores source coordinates for each output pixel.
                # To move visible content toward residual direction, sample from the opposite direction.
                return -float(row["mean_dx"]) * strength, -float(row["mean_dy"]) * strength
    raise RuntimeError(f"cell not found: gx={gx} gy={gy}")


def build_maps(width: int, height: int, gx: int, gy: int, cols: int, rows: int, dx: float, dy: float, sigma_scale: float):
    xx, yy = np.meshgrid(np.arange(width, dtype=np.float32), np.arange(height, dtype=np.float32))
    cx = (gx + 0.5) * width / cols
    cy = (gy + 0.5) * height / rows
    sigma_x = max(8.0, width / cols * sigma_scale)
    sigma_y = max(8.0, height / rows * sigma_scale)
    weight = np.exp(-0.5 * (((xx - cx) / sigma_x) ** 2 + ((yy - cy) / sigma_y) ** 2)).astype(np.float32)
    map_x = xx + dx * weight
    map_y = yy + dy * weight
    map_x = np.clip(map_x, 0, width - 1).astype(np.float32)
    map_y = np.clip(map_y, 0, height - 1).astype(np.float32)
    return map_x, map_y, weight


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply a constrained local remap correction to a diagnostic video.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--cell-summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--weight-preview", type=Path)
    parser.add_argument("--gx", type=int, required=True)
    parser.add_argument("--gy", type=int, required=True)
    parser.add_argument("--grid-cols", type=int, default=4)
    parser.add_argument("--grid-rows", type=int, default=4)
    parser.add_argument("--strength", type=float, default=1.0)
    parser.add_argument("--sigma-scale", type=float, default=0.9)
    parser.add_argument("--max-frames", type=int, default=0)
    args = parser.parse_args()

    cap = cv2.VideoCapture(str(args.input))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open input: {args.input}")
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    dx, dy = read_cell_vector(args.cell_summary, args.gx, args.gy, args.strength)
    map_x, map_y, weight = build_maps(
        width, height, args.gx, args.gy, args.grid_cols, args.grid_rows, dx, dy, args.sigma_scale
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(args.output), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"Cannot open output: {args.output}")
    if args.weight_preview:
        args.weight_preview.parent.mkdir(parents=True, exist_ok=True)
        preview = (np.clip(weight, 0, 1) * 255).astype(np.uint8)
        preview = cv2.applyColorMap(preview, cv2.COLORMAP_TURBO)
        cv2.imwrite(str(args.weight_preview), preview)

    frames = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        corrected = cv2.remap(frame, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        writer.write(corrected)
        frames += 1
        if args.max_frames and frames >= args.max_frames:
            break

    cap.release()
    writer.release()
    print(f"input={args.input}")
    print(f"output={args.output}")
    print(f"frames={frames}")
    print(f"dx={dx:.6f}")
    print(f"dy={dy:.6f}")
    print(f"target_cell={args.gx},{args.gy}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
