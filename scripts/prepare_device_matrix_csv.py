from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np


MATRIX_FIELDS = ["m00", "m01", "m02", "m10", "m11", "m12", "m20", "m21", "m22"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare cpu_stabilize.py matrix CSVs for the MMAPI/VPI device path. "
            "It can prepend the first-frame transform, compose CPU geometric post-processing, "
            "and output inverse matrices for VPI."
        )
    )
    parser.add_argument("--matrix-input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--metrics", type=Path, default=None, help="Optional cpu_stabilize.py metrics CSV with dynamic_zoom.")
    parser.add_argument("--width", type=int, required=True)
    parser.add_argument("--height", type=int, required=True)
    parser.add_argument("--crop-ratio", type=float, default=1.0)
    parser.add_argument("--border-scale", type=float, default=1.0)
    parser.add_argument("--compose-post-geometry", action="store_true")
    parser.add_argument(
        "--prepend-first-frame",
        choices=["none", "identity", "post_geometry"],
        default="identity",
        help="cpu_stabilize.py matrix rows start after the first frame; device video usually starts at frame 1.",
    )
    parser.add_argument(
        "--first-frame-ignores-post-geometry",
        action="store_true",
        help="Use identity for the prepended first frame even when later rows compose post geometry.",
    )
    parser.add_argument("--output-convention", choices=["source_to_dest", "inverse"], default="inverse")
    return parser.parse_args()


def center_scale_3x3(width: int, height: int, scale: float) -> np.ndarray:
    center_x = float(width) * 0.5
    center_y = float(height) * 0.5
    return np.array(
        [
            [float(scale), 0.0, (1.0 - float(scale)) * center_x],
            [0.0, float(scale), (1.0 - float(scale)) * center_y],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )


def row_to_matrix(row: dict[str, str]) -> np.ndarray:
    missing = [field for field in MATRIX_FIELDS if field not in row]
    if missing:
        raise ValueError(f"missing matrix fields: {', '.join(missing)}")
    values = [float(row[field]) for field in MATRIX_FIELDS]
    return np.array(values, dtype=np.float64).reshape(3, 3)


def matrix_to_cells(mat: np.ndarray) -> dict[str, str]:
    return {field: f"{float(value):.9f}" for field, value in zip(MATRIX_FIELDS, mat.reshape(-1))}


def read_metrics_zoom(path: Path | None) -> dict[int, float]:
    if path is None:
        return {}
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    zoom_by_frame: dict[int, float] = {}
    for row in rows:
        if not row.get("frame_index"):
            continue
        frame_index = int(row["frame_index"])
        zoom_by_frame[frame_index] = float(row.get("dynamic_zoom") or 1.0)
    return zoom_by_frame


def post_geometry_matrix(width: int, height: int, border_scale: float, crop_ratio: float, zoom: float) -> np.ndarray:
    zoom_mat = center_scale_3x3(width, height, float(border_scale) * float(zoom))
    crop_mat = center_scale_3x3(width, height, 1.0 / float(crop_ratio))
    return crop_mat @ zoom_mat


def prepare_output_matrix(mat: np.ndarray, output_convention: str) -> np.ndarray:
    if output_convention == "source_to_dest":
        return mat
    return np.linalg.inv(mat)


def main() -> int:
    args = parse_args()
    if args.crop_ratio <= 0 or args.crop_ratio > 1:
        raise ValueError("--crop-ratio must be in (0, 1]")

    with args.matrix_input.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise RuntimeError(f"empty CSV: {args.matrix_input}")
        input_fieldnames = list(reader.fieldnames)
        rows = list(reader)
    if "frame_index" not in input_fieldnames:
        raise ValueError("matrix CSV must contain frame_index")

    zoom_by_frame = read_metrics_zoom(args.metrics)
    output_rows: list[dict[str, str]] = []

    if args.prepend_first_frame != "none":
        if args.first_frame_ignores_post_geometry:
            first_mat = np.eye(3, dtype=np.float64)
        elif args.prepend_first_frame == "post_geometry":
            first_zoom = zoom_by_frame.get(1, 1.0)
            first_mat = post_geometry_matrix(args.width, args.height, args.border_scale, args.crop_ratio, first_zoom)
        else:
            first_mat = np.eye(3, dtype=np.float64)
        out_mat = prepare_output_matrix(first_mat, args.output_convention)
        out_row = {"frame_index": "0"}
        out_row.update(matrix_to_cells(out_mat))
        output_rows.append(out_row)

    for row in rows:
        frame_index = int(row["frame_index"])
        mat = row_to_matrix(row)
        if args.compose_post_geometry:
            zoom = zoom_by_frame.get(frame_index, 1.0)
            mat = post_geometry_matrix(args.width, args.height, args.border_scale, args.crop_ratio, zoom) @ mat
        out_mat = prepare_output_matrix(mat, args.output_convention)
        out_row = {"frame_index": str(frame_index)}
        out_row.update(matrix_to_cells(out_mat))
        output_rows.append(out_row)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["frame_index", *MATRIX_FIELDS])
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"matrix_input_rows: {len(rows)}")
    print(f"output_rows: {len(output_rows)}")
    print(f"prepend_first_frame: {args.prepend_first_frame}")
    print(f"compose_post_geometry: {args.compose_post_geometry}")
    print(f"output_convention: {args.output_convention}")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
