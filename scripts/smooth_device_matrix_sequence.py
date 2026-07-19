from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import numpy as np


MATRIX_FIELDS = ["m00", "m01", "m02", "m10", "m11", "m12", "m20", "m21", "m22"]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def row_to_matrix(row: dict[str, str]) -> np.ndarray:
    values = [float(row[field]) for field in MATRIX_FIELDS]
    return np.array(values, dtype=np.float64).reshape(3, 3)


def matrix_to_cells(mat: np.ndarray) -> dict[str, str]:
    return {field: f"{float(value):.9f}" for field, value in zip(MATRIX_FIELDS, mat.reshape(-1))}


def moving_average(values: np.ndarray, radius: int) -> np.ndarray:
    if radius <= 0:
        return values.copy()
    window = 2 * radius + 1
    kernel = np.ones(window, dtype=np.float64) / float(window)
    padded = np.pad(values, (radius, radius), mode="edge")
    return np.convolve(padded, kernel, mode="valid")


def decompose_similarity(mat: np.ndarray) -> tuple[float, float, float, float]:
    a = float(mat[0, 0])
    c = float(mat[1, 0])
    scale = math.hypot(a, c)
    angle = math.atan2(c, a)
    return scale, angle, float(mat[0, 2]), float(mat[1, 2])


def compose_similarity(scale: float, angle: float, tx: float, ty: float) -> np.ndarray:
    cos_v = math.cos(angle) * scale
    sin_v = math.sin(angle) * scale
    return np.array(
        [
            [cos_v, -sin_v, tx],
            [sin_v, cos_v, ty],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Smooth device-ready similarity matrices to reduce abrupt viewport changes.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--smooth-translation-radius", type=int, default=0)
    parser.add_argument("--smooth-angle-radius", type=int, default=0)
    parser.add_argument("--fixed-scale", choices=["none", "median", "mean"], default="median")
    parser.add_argument("--scale-multiplier", type=float, default=1.0)
    parser.add_argument("--first-frame-copy-next", action="store_true")
    parser.add_argument("--fade-in-frames", type=int, default=0, help="Blend the first N frames from identity to the original/smoothed matrix.")
    args = parser.parse_args()

    rows = read_rows(args.input)
    mats = [row_to_matrix(row) for row in rows]
    params = np.array([decompose_similarity(mat) for mat in mats], dtype=np.float64)
    scales = params[:, 0]
    angles = np.unwrap(params[:, 1])
    tx = params[:, 2]
    ty = params[:, 3]

    if args.fixed_scale == "median":
        scales_out = np.full_like(scales, float(np.median(scales)) * args.scale_multiplier)
    elif args.fixed_scale == "mean":
        scales_out = np.full_like(scales, float(np.mean(scales)) * args.scale_multiplier)
    else:
        scales_out = scales * args.scale_multiplier
    angles_out = moving_average(angles, args.smooth_angle_radius)
    tx_out = moving_average(tx, args.smooth_translation_radius)
    ty_out = moving_average(ty, args.smooth_translation_radius)
    if args.first_frame_copy_next and len(scales_out) > 1:
        scales_out[0] = scales_out[1]
        angles_out[0] = angles_out[1]
        tx_out[0] = tx_out[1]
        ty_out[0] = ty_out[1]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    out_rows = []
    fade_frames = max(0, int(args.fade_in_frames))
    for idx, (row, scale, angle, cur_tx, cur_ty) in enumerate(zip(rows, scales_out, angles_out, tx_out, ty_out)):
        mat = compose_similarity(float(scale), float(angle), float(cur_tx), float(cur_ty))
        if fade_frames > 0 and idx < fade_frames:
            alpha = float(idx + 1) / float(fade_frames)
            identity = np.eye(3, dtype=np.float64)
            mat = identity + alpha * (mat - identity)
        out_row = {"frame_index": row["frame_index"]}
        out_row.update(matrix_to_cells(mat))
        out_rows.append(out_row)
    with args.output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["frame_index", *MATRIX_FIELDS])
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"rows: {len(out_rows)}")
    print(f"scale_input_min: {float(scales.min()):.9f}")
    print(f"scale_input_max: {float(scales.max()):.9f}")
    print(f"scale_output_min: {float(scales_out.min()):.9f}")
    print(f"scale_output_max: {float(scales_out.max()):.9f}")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
