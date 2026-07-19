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


def robust_scale(mat: np.ndarray) -> tuple[float, float, float]:
    linear = mat[:2, :2]
    singular = np.linalg.svd(linear, compute_uv=False)
    sx, sy = float(singular[0]), float(singular[1])
    return math.sqrt(max(1e-12, sx * sy)), sx, sy


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose per-frame matrix scale, translation, jumps, and FOV footprint.")
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--width", type=int, required=True)
    parser.add_argument("--height", type=int, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    rows = read_rows(args.matrix)
    args.out_dir.mkdir(parents=True, exist_ok=True)

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
    prev_scale = None
    prev_tx = None
    prev_ty = None
    prev_angle = None
    prev_mat = None
    for row in rows:
        frame = int(row["frame_index"])
        mat = row_to_matrix(row)
        scale, sx, sy = robust_scale(mat)
        tx = float(mat[0, 2])
        ty = float(mat[1, 2])
        angle = math.atan2(float(mat[1, 0]), float(mat[0, 0]))

        mapped = (mat @ corners.T).T
        mapped_xy = mapped[:, :2] / mapped[:, 2:3]
        min_x = float(mapped_xy[:, 0].min())
        max_x = float(mapped_xy[:, 0].max())
        min_y = float(mapped_xy[:, 1].min())
        max_y = float(mapped_xy[:, 1].max())
        rel = np.abs(mapped_xy - center)
        required_zoom_x = float(np.max(rel[:, 0]) / max(1e-6, half_w))
        required_zoom_y = float(np.max(rel[:, 1]) / max(1e-6, half_h))
        required_zoom = max(1.0, required_zoom_x, required_zoom_y)

        scale_delta = 0.0 if prev_scale is None else scale - prev_scale
        trans_delta = 0.0 if prev_tx is None else math.hypot(tx - prev_tx, ty - prev_ty)
        angle_delta = 0.0 if prev_angle is None else angle - prev_angle
        mat_delta = 0.0 if prev_mat is None else float(np.linalg.norm(mat - prev_mat, ord="fro"))

        out_rows.append(
            {
                "frame": frame,
                "scale": f"{scale:.9f}",
                "sx": f"{sx:.9f}",
                "sy": f"{sy:.9f}",
                "anisotropy": f"{abs(sx - sy):.9f}",
                "tx": f"{tx:.9f}",
                "ty": f"{ty:.9f}",
                "angle_rad": f"{angle:.9f}",
                "scale_delta": f"{scale_delta:.9f}",
                "trans_delta": f"{trans_delta:.9f}",
                "angle_delta": f"{angle_delta:.9f}",
                "matrix_delta_fro": f"{mat_delta:.9f}",
                "min_x": f"{min_x:.6f}",
                "max_x": f"{max_x:.6f}",
                "min_y": f"{min_y:.6f}",
                "max_y": f"{max_y:.6f}",
                "required_extra_zoom": f"{required_zoom:.9f}",
            }
        )
        prev_scale = scale
        prev_tx = tx
        prev_ty = ty
        prev_angle = angle
        prev_mat = mat

    csv_path = args.out_dir / "matrix_stability.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        writer.writeheader()
        writer.writerows(out_rows)

    def values(key: str) -> np.ndarray:
        return np.array([float(row[key]) for row in out_rows], dtype=np.float64)

    summary = {
        "matrix": str(args.matrix),
        "frames": len(out_rows),
    }
    for key in ("scale", "scale_delta", "trans_delta", "angle_delta", "matrix_delta_fro", "required_extra_zoom"):
        vals = values(key)
        abs_vals = np.abs(vals)
        summary[f"{key}_mean"] = f"{float(vals.mean()):.9f}"
        summary[f"{key}_p95_abs"] = f"{float(np.percentile(abs_vals, 95)):.9f}"
        summary[f"{key}_max_abs"] = f"{float(abs_vals.max()):.9f}"

    summary_csv = args.out_dir / "summary.csv"
    with summary_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary.keys()))
        writer.writeheader()
        writer.writerow(summary)

    print(f"matrix_stability: {csv_path}")
    print(f"summary: {summary_csv}")
    for key, value in summary.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
