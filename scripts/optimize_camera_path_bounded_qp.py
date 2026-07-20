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


def solve_kkt(hessian: np.ndarray, rhs: np.ndarray, aeq: np.ndarray, beq: np.ndarray) -> np.ndarray:
    if aeq.size == 0:
        return np.linalg.solve(hessian, rhs)
    zeros = np.zeros((aeq.shape[0], aeq.shape[0]), dtype=np.float64)
    kkt = np.block([[hessian, aeq.T], [aeq, zeros]])
    krhs = np.concatenate([rhs, beq])
    sol = np.linalg.solve(kkt, krhs)
    return sol[: len(rhs)]


def solve_window_1d(
    values: np.ndarray,
    lambdas: np.ndarray,
    committed: np.ndarray,
    commit_start: int,
    lo: int,
    hi: int,
    w2: float,
    w3: float,
    anchor_weight: float,
) -> np.ndarray:
    segment = values[lo:hi]
    lam = np.maximum(lambdas[lo:hi], 1e-9)
    n = len(segment)
    d2 = derivative_matrix(n, 2)
    d3 = derivative_matrix(n, 3)
    hessian = np.diag(lam) + float(w2) * (d2.T @ d2) + float(w3) * (d3.T @ d3)
    rhs = lam * segment
    if anchor_weight > 0 and lo == 0:
        hessian[0, 0] += anchor_weight
        rhs[0] += anchor_weight * segment[0]
    if anchor_weight > 0 and hi == len(values):
        hessian[-1, -1] += anchor_weight
        rhs[-1] += anchor_weight * segment[-1]

    eq_rows: list[np.ndarray] = []
    eq_vals: list[float] = []

    for frame in range(lo, min(commit_start, hi)):
        if not np.isfinite(committed[frame]):
            continue
        row = np.zeros(n, dtype=np.float64)
        row[frame - lo] = 1.0
        eq_rows.append(row)
        eq_vals.append(float(committed[frame]))

    # C1 seam continuity: first uncommitted velocity equals last committed velocity.
    if commit_start >= 2 and lo <= commit_start - 1 and commit_start < hi:
        if np.isfinite(committed[commit_start - 1]) and np.isfinite(committed[commit_start - 2]):
            row = np.zeros(n, dtype=np.float64)
            row[commit_start - lo] = 1.0
            row[commit_start - 1 - lo] = -1.0
            eq_rows.append(row)
            eq_vals.append(float(committed[commit_start - 1] - committed[commit_start - 2]))

    # C2 seam continuity: first uncommitted acceleration equals last committed acceleration.
    if commit_start >= 3 and lo <= commit_start - 1 and commit_start + 1 < hi:
        if (
            np.isfinite(committed[commit_start - 1])
            and np.isfinite(committed[commit_start - 2])
            and np.isfinite(committed[commit_start - 3])
        ):
            row = np.zeros(n, dtype=np.float64)
            row[commit_start + 1 - lo] = 1.0
            row[commit_start - lo] = -2.0
            row[commit_start - 1 - lo] = 1.0
            eq_rows.append(row)
            eq_vals.append(float(committed[commit_start - 1] - 2.0 * committed[commit_start - 2] + committed[commit_start - 3]))

    aeq = np.vstack(eq_rows) if eq_rows else np.empty((0, n), dtype=np.float64)
    beq = np.array(eq_vals, dtype=np.float64) if eq_vals else np.empty((0,), dtype=np.float64)
    return solve_kkt(hessian, rhs, aeq, beq)


def bounded_qp(values: np.ndarray, tx: np.ndarray, ty: np.ndarray, lambdas: np.ndarray, window: int, commit_stride: int, w2: float, w3: float, anchor_weight: float) -> tuple[np.ndarray, list[dict[str, object]]]:
    n = len(values)
    out = np.full(n, np.nan, dtype=np.float64)
    commit_log: list[dict[str, object]] = []
    commit_start = 0
    while commit_start < n:
        lo = max(0, commit_start - 3)
        hi = min(n, commit_start + max(3, int(window)))
        sol = solve_window_1d(values, lambdas, out, commit_start, lo, hi, w2, w3, anchor_weight)
        commit_end = min(n, commit_start + max(1, int(commit_stride)))
        out[commit_start:commit_end] = sol[commit_start - lo : commit_end - lo]
        commit_log.append({"commit_start": commit_start, "commit_end": commit_end, "lo": lo, "hi": hi})
        commit_start = commit_end
    return out, commit_log


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounded-delay sliding-window QP smoothing with C0/C1/C2 seam constraints.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--log", type=Path, default=None)
    parser.add_argument("--commit-log", type=Path, default=None)
    parser.add_argument("--lambda0", type=float, default=1.0)
    parser.add_argument("--sigma-px", type=float, default=0.0)
    parser.add_argument("--w2", type=float, default=20.0)
    parser.add_argument("--w3", type=float, default=200.0)
    parser.add_argument("--anchor-weight", type=float, default=1000.0)
    parser.add_argument("--window", type=int, default=45)
    parser.add_argument("--commit-stride", type=int, default=4)
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

    tx_out, commit_log = bounded_qp(tx, tx, ty, lambdas, args.window, args.commit_stride, args.w2, args.w3, args.anchor_weight)
    ty_out, _ = bounded_qp(ty, tx, ty, lambdas, args.window, args.commit_stride, args.w2, args.w3, args.anchor_weight)
    angle_out, _ = bounded_qp(angles, tx, ty, lambdas, args.window, args.commit_stride, args.w2, args.w3, args.anchor_weight)

    if args.first_frame_copy_next and len(rows) > 1:
        tx_out[0] = tx_out[1]
        ty_out[0] = ty_out[1]
        angle_out[0] = angle_out[1]
        scales[0] = scales[1]

    out_rows = []
    for row, scale, angle, cur_tx, cur_ty in zip(rows, scales, angle_out, tx_out, ty_out):
        mat = compose_similarity(float(scale), float(angle), float(cur_tx), float(cur_ty))
        out_row = {"frame_index": row["frame_index"]}
        out_row.update(matrix_to_cells(mat))
        out_rows.append(out_row)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["frame_index", *MATRIX_FIELDS])
        writer.writeheader()
        writer.writerows(out_rows)

    if args.commit_log is not None:
        args.commit_log.parent.mkdir(parents=True, exist_ok=True)
        with args.commit_log.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(commit_log[0].keys()))
            writer.writeheader()
            writer.writerows(commit_log)

    print(f"rows: {len(out_rows)}")
    print(f"window: {args.window}")
    print(f"commit_stride: {args.commit_stride}")
    print(f"lambda_min: {float(np.min(lambdas)):.9f}")
    print(f"lambda_max: {float(np.max(lambdas)):.9f}")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
