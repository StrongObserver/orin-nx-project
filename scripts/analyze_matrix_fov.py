from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np


MATRIX_FIELDS = ["m00", "m01", "m02", "m10", "m11", "m12", "m20", "m21", "m22"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze source coverage/FOV risk for device-side inverse matrices.")
    parser.add_argument("--matrix", type=Path, required=True, help="Device matrix CSV, usually inverse matrices consumed by VPI.")
    parser.add_argument("--width", type=int, required=True)
    parser.add_argument("--height", type=int, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    return parser.parse_args()


def row_to_matrix(row: dict[str, str]) -> np.ndarray:
    return np.array([float(row[field]) for field in MATRIX_FIELDS], dtype=np.float64).reshape(3, 3)


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    with args.matrix.open("r", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    corners = np.array(
        [
            [0.0, 0.0, 1.0],
            [args.width - 1.0, 0.0, 1.0],
            [args.width - 1.0, args.height - 1.0, 1.0],
            [0.0, args.height - 1.0, 1.0],
        ],
        dtype=np.float64,
    )
    center = np.array([args.width * 0.5, args.height * 0.5], dtype=np.float64)
    half_w = args.width * 0.5
    half_h = args.height * 0.5

    out_rows = []
    for row in rows:
        frame = int(row["frame_index"])
        mat = row_to_matrix(row)
        mapped = (mat @ corners.T).T
        mapped_xy = mapped[:, :2] / mapped[:, 2:3]
        min_x = float(mapped_xy[:, 0].min())
        max_x = float(mapped_xy[:, 0].max())
        min_y = float(mapped_xy[:, 1].min())
        max_y = float(mapped_xy[:, 1].max())
        out_left = max(0.0, -min_x)
        out_right = max(0.0, max_x - (args.width - 1.0))
        out_top = max(0.0, -min_y)
        out_bottom = max(0.0, max_y - (args.height - 1.0))
        # How much larger than the source frame the sampled output footprint is,
        # expressed as a center-scale zoom needed to pull it inside.
        rel = np.abs(mapped_xy - center)
        required_zoom_x = float(np.max(rel[:, 0]) / max(1e-6, half_w))
        required_zoom_y = float(np.max(rel[:, 1]) / max(1e-6, half_h))
        required_zoom = max(1.0, required_zoom_x, required_zoom_y)
        out_rows.append(
            {
                "frame": frame,
                "min_x": f"{min_x:.6f}",
                "max_x": f"{max_x:.6f}",
                "min_y": f"{min_y:.6f}",
                "max_y": f"{max_y:.6f}",
                "out_left_px": f"{out_left:.6f}",
                "out_right_px": f"{out_right:.6f}",
                "out_top_px": f"{out_top:.6f}",
                "out_bottom_px": f"{out_bottom:.6f}",
                "max_out_px": f"{max(out_left, out_right, out_top, out_bottom):.6f}",
                "required_extra_zoom": f"{required_zoom:.6f}",
            }
        )

    csv_path = args.out_dir / "matrix_fov.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        writer.writeheader()
        writer.writerows(out_rows)

    max_out = np.array([float(row["max_out_px"]) for row in out_rows], dtype=np.float64)
    zooms = np.array([float(row["required_extra_zoom"]) for row in out_rows], dtype=np.float64)
    summary = {
        "matrix": str(args.matrix),
        "frames": len(out_rows),
        "max_out_px_mean": f"{float(max_out.mean()):.6f}",
        "max_out_px_p95": f"{float(np.percentile(max_out, 95)):.6f}",
        "max_out_px_max": f"{float(max_out.max()):.6f}",
        "required_extra_zoom_mean": f"{float(zooms.mean()):.6f}",
        "required_extra_zoom_p95": f"{float(np.percentile(zooms, 95)):.6f}",
        "required_extra_zoom_max": f"{float(zooms.max()):.6f}",
    }
    summary_path = args.out_dir / "summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary.keys()))
        writer.writeheader()
        writer.writerow(summary)

    print(f"matrix_fov: {csv_path}")
    print(f"summary: {summary_path}")
    for key, value in summary.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
