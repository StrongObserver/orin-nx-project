from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np


MATRIX_FIELDS = ["m00", "m01", "m02", "m10", "m11", "m12", "m20", "m21", "m22"]


def center_scale(width: int, height: int, scale: float) -> np.ndarray:
    cx = width * 0.5
    cy = height * 0.5
    return np.array(
        [
            [scale, 0.0, (1.0 - scale) * cx],
            [0.0, scale, (1.0 - scale) * cy],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )


def compose_scaled_matrix(mat: np.ndarray, scale_mat: np.ndarray, mode: str) -> np.ndarray:
    if mode == "pre":
        return scale_mat @ mat
    if mode == "post":
        return mat @ scale_mat
    inv_scale = np.linalg.inv(scale_mat)
    if mode == "pre_inverse":
        return inv_scale @ mat
    if mode == "post_inverse":
        return mat @ inv_scale
    raise ValueError(f"unsupported compose mode: {mode}")


def read_matrix_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def read_scale_rows(path: Path) -> dict[int, float]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    return {int(row["frame_index"]): float(row["planned_extra_scale"]) for row in rows}


def row_to_matrix(row: dict[str, str]) -> np.ndarray:
    values = [float(row[field]) for field in MATRIX_FIELDS]
    return np.array(values, dtype=np.float64).reshape(3, 3)


def matrix_to_cells(mat: np.ndarray) -> dict[str, str]:
    return {field: f"{float(value):.9f}" for field, value in zip(MATRIX_FIELDS, mat.reshape(-1))}


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply inclusion extra scale to a device-ready matrix CSV.")
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--scale-csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--width", type=int, required=True)
    parser.add_argument("--height", type=int, required=True)
    parser.add_argument(
        "--compose",
        choices=["pre", "post", "pre_inverse", "post_inverse"],
        default="pre",
        help="How to compose center scale with the input matrix. Default preserves the original S @ H behavior.",
    )
    args = parser.parse_args()

    rows = read_matrix_rows(args.matrix)
    scales = read_scale_rows(args.scale_csv)
    out_rows = []
    for row in rows:
        frame = int(row["frame_index"])
        scale = scales.get(frame, 1.0)
        mat = compose_scaled_matrix(row_to_matrix(row), center_scale(args.width, args.height, scale), args.compose)
        out_row = {"frame_index": row["frame_index"]}
        out_row.update(matrix_to_cells(mat))
        out_rows.append(out_row)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["frame_index", *MATRIX_FIELDS])
        writer.writeheader()
        writer.writerows(out_rows)
    print(f"rows: {len(out_rows)}")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
