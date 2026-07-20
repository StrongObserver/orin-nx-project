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
    return np.array([float(row[field]) for field in MATRIX_FIELDS], dtype=np.float64).reshape(3, 3)


def matrix_to_cells(mat: np.ndarray) -> dict[str, str]:
    return {field: f"{float(value):.9f}" for field, value in zip(MATRIX_FIELDS, mat.reshape(-1))}


def decompose_similarity(mat: np.ndarray) -> tuple[float, float, float, float]:
    scale = math.hypot(float(mat[0, 0]), float(mat[1, 0]))
    angle = math.atan2(float(mat[1, 0]), float(mat[0, 0]))
    return scale, angle, float(mat[0, 2]), float(mat[1, 2])


def compose_similarity(scale: float, angle: float, tx: float, ty: float) -> np.ndarray:
    c = math.cos(angle) * scale
    s = math.sin(angle) * scale
    return np.array([[c, -s, tx], [s, c, ty], [0.0, 0.0, 1.0]], dtype=np.float64)


def derivative_matrix(n: int, order: int) -> np.ndarray:
    if order == 1:
        mat = np.zeros((max(0, n - 1), n), dtype=np.float64)
        for i in range(n - 1):
            mat[i, i] = -1.0
            mat[i, i + 1] = 1.0
        return mat
    if order == 2:
        mat = np.zeros((max(0, n - 2), n), dtype=np.float64)
        for i in range(n - 2):
            mat[i, i] = 1.0
            mat[i, i + 1] = -2.0
            mat[i, i + 2] = 1.0
        return mat
    if order == 3:
        mat = np.zeros((max(0, n - 3), n), dtype=np.float64)
        for i in range(n - 3):
            mat[i, i] = -1.0
            mat[i, i + 1] = 3.0
            mat[i, i + 2] = -3.0
            mat[i, i + 3] = 1.0
        return mat
    raise ValueError(f"unsupported derivative order: {order}")


def solve_qp_1d(values: np.ndarray, lambdas: np.ndarray, w2: float, w3: float, anchor_weight: float) -> np.ndarray:
    n = len(values)
    if n <= 3:
        return values.copy()
    diag = np.diag(np.maximum(lambdas, 1e-9))
    rhs = lambdas * values
    d2 = derivative_matrix(n, 2)
    d3 = derivative_matrix(n, 3)
    system = diag + float(w2) * (d2.T @ d2) + float(w3) * (d3.T @ d3)
    if anchor_weight > 0:
        system[0, 0] += anchor_weight
        rhs[0] += anchor_weight * values[0]
        system[-1, -1] += anchor_weight
        rhs[-1] += anchor_weight * values[-1]
    return np.linalg.solve(system, rhs)


def read_confidence(log_path: Path | None, n: int) -> np.ndarray:
    if log_path is None or not log_path.exists():
        return np.ones(n, dtype=np.float64)
    confidence = np.ones(n, dtype=np.float64)
    with log_path.open("r", newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            frame = int(row.get("frame_index", 0))
            if frame < 0 or frame >= n:
                continue
            fallback = row.get("fallback_reason", "")
            inliers = float(row.get("inliers", 0) or 0)
            ratio = float(row.get("inlier_ratio", 0) or 0)
            if fallback:
                confidence[frame] = 0.05
            else:
                confidence[frame] = max(0.05, min(1.0, ratio)) if inliers >= 12 else 0.1
    return confidence


def speed_adapted_lambdas(tx: np.ndarray, ty: np.ndarray, base: np.ndarray, lambda0: float, sigma_px: float) -> np.ndarray:
    if sigma_px <= 0:
        return lambda0 * base
    dx = np.diff(tx, prepend=tx[0])
    dy = np.diff(ty, prepend=ty[0])
    speed = np.hypot(dx, dy)
    adapt = np.exp(-(speed * speed) / max(1e-9, sigma_px * sigma_px))
    return lambda0 * base * adapt


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline full-sequence QP smoothing for device matrix camera path probes.")
    parser.add_argument("--input", type=Path, required=True, help="Input matrix CSV, usually source_to_dest or fixed-scale device matrix.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--log", type=Path, default=None, help="Optional producer log for confidence weighting.")
    parser.add_argument("--lambda0", type=float, default=1.0)
    parser.add_argument("--sigma-px", type=float, default=0.0)
    parser.add_argument("--w2", type=float, default=4.0)
    parser.add_argument("--w3", type=float, default=40.0)
    parser.add_argument("--anchor-weight", type=float, default=1000.0)
    parser.add_argument("--fixed-scale", choices=["input", "median", "absolute"], default="input")
    parser.add_argument("--absolute-scale", type=float, default=1.03)
    parser.add_argument("--first-frame-copy-next", action="store_true")
    args = parser.parse_args()

    rows = read_rows(args.input)
    mats = [row_to_matrix(row) for row in rows]
    params = np.array([decompose_similarity(mat) for mat in mats], dtype=np.float64)
    scales = params[:, 0]
    angles = np.unwrap(params[:, 1])
    tx = params[:, 2]
    ty = params[:, 3]

    confidence = read_confidence(args.log, len(rows))
    lambdas = speed_adapted_lambdas(tx, ty, confidence, args.lambda0, args.sigma_px)
    tx_out = solve_qp_1d(tx, lambdas, args.w2, args.w3, args.anchor_weight)
    ty_out = solve_qp_1d(ty, lambdas, args.w2, args.w3, args.anchor_weight)
    angle_out = solve_qp_1d(angles, lambdas, args.w2, args.w3, args.anchor_weight)
    if args.fixed_scale == "absolute":
        scale_out = np.full_like(scales, float(args.absolute_scale))
    elif args.fixed_scale == "median":
        scale_out = np.full_like(scales, float(np.median(scales)))
    else:
        scale_out = scales.copy()

    if args.first_frame_copy_next and len(rows) > 1:
        scale_out[0] = scale_out[1]
        tx_out[0] = tx_out[1]
        ty_out[0] = ty_out[1]
        angle_out[0] = angle_out[1]

    out_rows = []
    for row, scale, angle, cur_tx, cur_ty in zip(rows, scale_out, angle_out, tx_out, ty_out):
        mat = compose_similarity(float(scale), float(angle), float(cur_tx), float(cur_ty))
        out_row = {"frame_index": row["frame_index"]}
        out_row.update(matrix_to_cells(mat))
        out_rows.append(out_row)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["frame_index", *MATRIX_FIELDS])
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"rows: {len(out_rows)}")
    print(f"lambda_min: {float(np.min(lambdas)):.9f}")
    print(f"lambda_max: {float(np.max(lambdas)):.9f}")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
