import argparse
import csv
import math
import time
from pathlib import Path

import cv2
import numpy as np


def moving_average(curve: np.ndarray, radius: int) -> np.ndarray:
    if radius <= 0:
        return np.array(curve, copy=True)
    window_size = 2 * radius + 1
    filt = np.ones(window_size, dtype=np.float32) / window_size
    curve_pad = np.pad(curve, (radius, radius), mode="edge")
    return np.convolve(curve_pad, filt, mode="same")[radius:-radius]


def gaussian_average(curve: np.ndarray, radius: int, stdev: float) -> np.ndarray:
    if radius <= 0:
        return np.array(curve, copy=True)
    if stdev <= 0:
        stdev = max(1.0, float(radius) / 3.0)
    offsets = np.arange(-radius, radius + 1, dtype=np.float32)
    weights = np.exp(-0.5 * (offsets / stdev) * (offsets / stdev)).astype(np.float32)
    weights /= np.sum(weights)
    curve_pad = np.pad(curve, (radius, radius), mode="edge")
    return np.convolve(curve_pad, weights, mode="same")[radius:-radius]


def smooth_trajectory(trajectory: np.ndarray, radius: int, method: str, gaussian_stdev: float) -> np.ndarray:
    smoothed = np.copy(trajectory)
    for i in range(trajectory.shape[1]):
        if method == "gaussian":
            smoothed[:, i] = gaussian_average(trajectory[:, i], radius, gaussian_stdev)
        else:
            smoothed[:, i] = moving_average(trajectory[:, i], radius)
    return smoothed


def trajectory_margin_limits(width: int, height: int, crop_ratio: float, margin_scale: float) -> np.ndarray:
    """Conservative per-axis correction budget implied by fixed center crop."""
    side_margin_x = max(0.0, (1.0 - float(crop_ratio)) * 0.5 * float(width) * float(margin_scale))
    side_margin_y = max(0.0, (1.0 - float(crop_ratio)) * 0.5 * float(height) * float(margin_scale))
    half_diag = max(1.0, 0.5 * math.hypot(float(width), float(height)))
    angle_margin = min(side_margin_x, side_margin_y) / half_diag
    return np.array([side_margin_x, side_margin_y, angle_margin], dtype=np.float32)


def acceleration_limits(accel_limit_px: float, accel_limit_deg: float) -> np.ndarray:
    return np.array(
        [
            accel_limit_px if accel_limit_px > 0 else np.inf,
            accel_limit_px if accel_limit_px > 0 else np.inf,
            math.radians(accel_limit_deg) if accel_limit_deg > 0 else np.inf,
        ],
        dtype=np.float32,
    )


def project_trajectory_box_and_accel(
    raw_trajectory: np.ndarray,
    candidate_trajectory: np.ndarray,
    margins: np.ndarray,
    accel_lims: np.ndarray,
    iterations: int,
) -> tuple[np.ndarray, int, int]:
    """Lightweight NumPy fallback for crop-constrained trajectory smoothing.

    This is not a full LpMotionStabilizer replacement. It is a first local
    approximation of the same principle: keep the smoothed trajectory inside the
    crop/FOV correction budget and, when requested, cap pose acceleration before
    per-frame inclusion rollback is needed.
    """
    projected = np.array(candidate_trajectory, copy=True, dtype=np.float32)
    raw = np.asarray(raw_trajectory, dtype=np.float32)
    if len(projected) == 0:
        return projected, 0, 0

    margins = np.asarray(margins, dtype=np.float32)
    accel_lims = np.asarray(accel_lims, dtype=np.float32)
    lo = raw - margins
    hi = raw + margins
    box_clamps = 0
    accel_clamps = 0
    iters = max(1, int(iterations))

    for _ in range(iters):
        before = projected.copy()
        projected = np.minimum(np.maximum(projected, lo), hi)
        box_clamps += int(np.sum(np.abs(before - projected) > 1e-6))

        if len(projected) >= 3 and np.any(np.isfinite(accel_lims)):
            for i in range(2, len(projected)):
                predicted = 2.0 * projected[i - 1] - projected[i - 2]
                accel = projected[i] - predicted
                clamped = np.clip(accel, -accel_lims, accel_lims)
                if np.any(np.abs(accel - clamped) > 1e-6):
                    projected[i] = predicted + clamped
                    accel_clamps += int(np.sum(np.abs(accel - clamped) > 1e-6))
                projected[i] = np.minimum(np.maximum(projected[i], lo[i]), hi[i])

            for i in range(len(projected) - 3, -1, -1):
                predicted = 2.0 * projected[i + 1] - projected[i + 2]
                accel = projected[i] - predicted
                clamped = np.clip(accel, -accel_lims, accel_lims)
                if np.any(np.abs(accel - clamped) > 1e-6):
                    projected[i] = predicted + clamped
                    accel_clamps += int(np.sum(np.abs(accel - clamped) > 1e-6))
                projected[i] = np.minimum(np.maximum(projected[i], lo[i]), hi[i])

    return projected.astype(np.float32), box_clamps, accel_clamps


def constrained_qp_smooth_1d(
    raw_path: np.ndarray,
    crop_margin: float,
    accel_limit: float,
    w1: float,
    w2: float,
    w3: float,
    use_l1: bool,
) -> np.ndarray:
    """Small offline constrained trajectory smoother using cvxpy when available."""
    try:
        import cvxpy as cp
    except ImportError as exc:
        raise RuntimeError("constrained_qp smoothing requires cvxpy; install with `py -m pip install cvxpy`") from exc

    raw = np.asarray(raw_path, dtype=np.float64)
    n = len(raw)
    if n <= 2:
        return raw.astype(np.float32)

    p = cp.Variable(n)
    d1 = p[1:] - p[:-1]
    d2 = p[2:] - 2.0 * p[1:-1] + p[:-2]
    terms = []
    if use_l1:
        terms.append(w1 * cp.norm1(d1))
        terms.append(w2 * cp.norm1(d2))
        if n >= 4:
            terms.append(w3 * cp.norm1(d2[1:] - d2[:-1]))
    else:
        terms.append(w1 * cp.sum_squares(d1))
        terms.append(w2 * cp.sum_squares(d2))
        if n >= 4:
            terms.append(w3 * cp.sum_squares(d2[1:] - d2[:-1]))

    constraints = [p - raw <= float(crop_margin), raw - p <= float(crop_margin)]
    if accel_limit > 0 and n >= 3:
        constraints.extend([d2 <= float(accel_limit), -d2 <= float(accel_limit)])

    problem = cp.Problem(cp.Minimize(sum(terms)), constraints)
    solvers = ["CLARABEL", "OSQP", "SCS"] if use_l1 else ["OSQP", "CLARABEL", "SCS"]
    last_error = None
    for solver in solvers:
        try:
            problem.solve(solver=solver, verbose=False)
        except Exception as exc:  # pragma: no cover - solver availability differs by env
            last_error = exc
            continue
        if p.value is not None and problem.status in {"optimal", "optimal_inaccurate"}:
            return np.asarray(p.value, dtype=np.float32)
    if last_error is not None:
        raise RuntimeError(f"constrained_qp solver failed: {last_error}") from last_error
    raise RuntimeError(f"constrained_qp solver failed with status: {problem.status}")


def constrained_qp_smooth_trajectory(
    trajectory: np.ndarray,
    width: int,
    height: int,
    crop_ratio: float,
    margin_scale: float,
    constrained_accel_limit_px: float,
    constrained_accel_limit_deg: float,
    use_l1: bool,
) -> np.ndarray:
    margins = trajectory_margin_limits(width, height, crop_ratio, margin_scale)
    accel_lims = acceleration_limits(constrained_accel_limit_px, constrained_accel_limit_deg)
    out = np.array(trajectory, copy=True, dtype=np.float32)
    for dim in range(trajectory.shape[1]):
        acc_limit = 0.0 if not np.isfinite(accel_lims[dim]) else float(accel_lims[dim])
        out[:, dim] = constrained_qp_smooth_1d(
            trajectory[:, dim],
            float(margins[dim]),
            acc_limit,
            w1=1.0,
            w2=10.0,
            w3=100.0,
            use_l1=use_l1,
        )
    return out


def rigid_params_from_mat(mat: np.ndarray) -> np.ndarray:
    return np.array([float(mat[0, 0]), float(mat[0, 1]), float(mat[0, 2]), float(mat[1, 2])], dtype=np.float32)


def mat_from_rigid_params(params: np.ndarray) -> np.ndarray:
    a, b, dx, dy = [float(v) for v in params]
    return np.array([[a, b, dx], [-b, a, dy], [0.0, 0.0, 1.0]], dtype=np.float32)


def solve_lp_motion_stabilizer_rigid(
    motions: np.ndarray,
    width: int,
    height: int,
    trim_ratio: float,
    w1: float = 1.0,
    w2: float = 10.0,
    w3: float = 100.0,
    w4: float = 100.0,
    anchor_first: bool = False,
) -> list[np.ndarray]:
    """Python port of OpenCV/video-stab LpMotionStabilizer rigid LP.

    The solved S[t] are per-frame stabilization warp matrices parameterized as
    [[a,b,dx],[-b,a,dy],[0,0,1]].  ``motions`` are inter-frame matrices M[t].
    This intentionally mirrors the source in motion_stabilizing.cpp rather than
    the earlier 1D trajectory approximation.
    """
    try:
        from scipy.optimize import linprog
        from scipy.sparse import coo_matrix
    except ImportError as exc:
        raise RuntimeError("lp_rigid smoothing requires scipy; install with `py -m pip install scipy`") from exc

    num_frames = len(motions) + 1
    if num_frames <= 1:
        return [np.eye(3, dtype=np.float32)]

    n1 = max(0, num_frames - 1)
    n2 = max(0, num_frames - 2)
    n3 = max(0, num_frames - 3)
    ncols = 4 * num_frames + 6 * n1 + 6 * n2 + 6 * n3
    nrows = 8 * num_frames + 2 * 6 * n1 + 2 * 6 * n2 + 2 * 6 * n3
    inf = np.inf

    obj = np.zeros(ncols, dtype=np.float64)
    bounds: list[tuple[float | None, float | None]] = [(None, None)] * ncols
    if anchor_first:
        # Optional gauge fixing.  The LP objective only penalizes temporal
        # derivatives, so without this anchor any constant in-crop similarity
        # transform is equally optimal.  Keep it optional because some clips get
        # better FOV/metric behavior from the unanchored OpenCV-style solution.
        bounds[0:4] = [(1.0, 1.0), (0.0, 0.0), (0.0, 0.0), (0.0, 0.0)]
    c = 4 * num_frames
    for count, weight in ((n1, w1), (n2, w2), (n3, w3)):
        for _ in range(count):
            obj[c : c + 6] = [w4 * weight, w4 * weight, weight, w4 * weight, w4 * weight, weight]
            for j in range(6):
                bounds[c + j] = (0.0, None)
            c += 6

    rows: list[int] = []
    cols: list[int] = []
    vals: list[float] = []
    rowlb = np.full(nrows, -inf, dtype=np.float64)
    rowub = np.full(nrows, inf, dtype=np.float64)

    def setv(row: int, col: int, value: float):
        if abs(value) > 1e-12:
            rows.append(row)
            cols.append(col)
            vals.append(float(value))

    r = 0
    w = float(width)
    h = float(height)
    tw = w * float(trim_ratio)
    th = h * float(trim_ratio)
    corners = [(0.0, 0.0), (w, 0.0), (w, h), (0.0, h)]

    for t in range(num_frames):
        c = 4 * t
        for x, y in corners:
            setv(r, c, x)
            setv(r, c + 1, y)
            setv(r, c + 2, 1.0)
            setv(r + 1, c, y)
            setv(r + 1, c + 1, -x)
            setv(r + 1, c + 3, 1.0)
            rowlb[r] = x - tw
            rowub[r] = x + tw
            rowlb[r + 1] = y - th
            rowub[r + 1] = y + th
            r += 2

    rigid_motions = [mat_from_rigid_params(rigid_params_from_mat(transform_to_affine_3x3(m))) for m in motions]

    def add_d1(row: int, t: int, slack_sign: float):
        m0 = rigid_motions[t]
        c0 = 4 * t
        setv(row, c0, -1.0)
        setv(row + 1, c0 + 1, -1.0)
        setv(row + 2, c0 + 2, -1.0)
        setv(row + 3, c0 + 1, 1.0)
        setv(row + 4, c0, -1.0)
        setv(row + 5, c0 + 3, -1.0)
        c1 = 4 * (t + 1)
        setv(row, c1, m0[0, 0]); setv(row, c1 + 1, m0[1, 0])
        setv(row + 1, c1, m0[0, 1]); setv(row + 1, c1 + 1, m0[1, 1])
        setv(row + 2, c1, m0[0, 2]); setv(row + 2, c1 + 1, m0[1, 2]); setv(row + 2, c1 + 2, 1.0)
        setv(row + 3, c1, m0[1, 0]); setv(row + 3, c1 + 1, -m0[0, 0])
        setv(row + 4, c1, m0[1, 1]); setv(row + 4, c1 + 1, -m0[0, 1])
        setv(row + 5, c1, m0[1, 2]); setv(row + 5, c1 + 1, -m0[0, 2]); setv(row + 5, c1 + 3, 1.0)
        cs = 4 * num_frames + 6 * t
        for i in range(6):
            setv(row + i, cs + i, slack_sign)

    for sign, upper in [(-1.0, True), (1.0, False)]:
        for t in range(n1):
            add_d1(r, t, sign)
            if upper:
                rowub[r : r + 6] = 0.0
            else:
                rowlb[r : r + 6] = 0.0
            r += 6

    def add_d2(row: int, t: int, slack_sign: float):
        m0 = rigid_motions[t]
        m1 = rigid_motions[t + 1]
        c0 = 4 * t
        setv(row, c0, 1.0); setv(row + 1, c0 + 1, 1.0); setv(row + 2, c0 + 2, 1.0)
        setv(row + 3, c0 + 1, -1.0); setv(row + 4, c0, 1.0); setv(row + 5, c0 + 3, 1.0)
        c1 = 4 * (t + 1)
        setv(row, c1, -m0[0, 0] - 1.0); setv(row, c1 + 1, -m0[1, 0])
        setv(row + 1, c1, -m0[0, 1]); setv(row + 1, c1 + 1, -m0[1, 1] - 1.0)
        setv(row + 2, c1, -m0[0, 2]); setv(row + 2, c1 + 1, -m0[1, 2]); setv(row + 2, c1 + 2, -2.0)
        setv(row + 3, c1, -m0[1, 0]); setv(row + 3, c1 + 1, m0[0, 0] + 1.0)
        setv(row + 4, c1, -m0[1, 1] - 1.0); setv(row + 4, c1 + 1, m0[0, 1])
        setv(row + 5, c1, -m0[1, 2]); setv(row + 5, c1 + 1, m0[0, 2]); setv(row + 5, c1 + 3, -2.0)
        c2 = 4 * (t + 2)
        setv(row, c2, m1[0, 0]); setv(row, c2 + 1, m1[1, 0])
        setv(row + 1, c2, m1[0, 1]); setv(row + 1, c2 + 1, m1[1, 1])
        setv(row + 2, c2, m1[0, 2]); setv(row + 2, c2 + 1, m1[1, 2]); setv(row + 2, c2 + 2, 1.0)
        setv(row + 3, c2, m1[1, 0]); setv(row + 3, c2 + 1, -m1[0, 0])
        setv(row + 4, c2, m1[1, 1]); setv(row + 4, c2 + 1, -m1[0, 1])
        setv(row + 5, c2, m1[1, 2]); setv(row + 5, c2 + 1, -m1[0, 2]); setv(row + 5, c2 + 3, 1.0)
        cs = 4 * num_frames + 6 * n1 + 6 * t
        for i in range(6):
            setv(row + i, cs + i, slack_sign)

    for sign, upper in [(-1.0, True), (1.0, False)]:
        for t in range(n2):
            add_d2(r, t, sign)
            if upper:
                rowub[r : r + 6] = 0.0
            else:
                rowlb[r : r + 6] = 0.0
            r += 6

    def add_d3(row: int, t: int, slack_sign: float):
        m0 = rigid_motions[t]
        m1 = rigid_motions[t + 1]
        m2 = rigid_motions[t + 2]
        c0 = 4 * t
        setv(row, c0, -1.0); setv(row + 1, c0 + 1, -1.0); setv(row + 2, c0 + 2, -1.0)
        setv(row + 3, c0 + 1, 1.0); setv(row + 4, c0, -1.0); setv(row + 5, c0 + 3, -1.0)
        c1 = 4 * (t + 1)
        setv(row, c1, m0[0, 0] + 2.0); setv(row, c1 + 1, m0[1, 0])
        setv(row + 1, c1, m0[0, 1]); setv(row + 1, c1 + 1, m0[1, 1] + 2.0)
        setv(row + 2, c1, m0[0, 2]); setv(row + 2, c1 + 1, m0[1, 2]); setv(row + 2, c1 + 2, 3.0)
        setv(row + 3, c1, m0[1, 0]); setv(row + 3, c1 + 1, -m0[0, 0] - 2.0)
        setv(row + 4, c1, m0[1, 1] + 2.0); setv(row + 4, c1 + 1, -m0[0, 1])
        setv(row + 5, c1, m0[1, 2]); setv(row + 5, c1 + 1, -m0[0, 2]); setv(row + 5, c1 + 3, 3.0)
        c2 = 4 * (t + 2)
        setv(row, c2, -2.0 * m1[0, 0] - 1.0); setv(row, c2 + 1, -2.0 * m1[1, 0])
        setv(row + 1, c2, -2.0 * m1[0, 1]); setv(row + 1, c2 + 1, -2.0 * m1[1, 1] - 1.0)
        setv(row + 2, c2, -2.0 * m1[0, 2]); setv(row + 2, c2 + 1, -2.0 * m1[1, 2]); setv(row + 2, c2 + 2, -3.0)
        setv(row + 3, c2, -2.0 * m1[1, 0]); setv(row + 3, c2 + 1, 2.0 * m1[0, 0] + 1.0)
        setv(row + 4, c2, -2.0 * m1[1, 1] - 1.0); setv(row + 4, c2 + 1, 2.0 * m1[0, 1])
        setv(row + 5, c2, -2.0 * m1[1, 2]); setv(row + 5, c2 + 1, 2.0 * m1[0, 2]); setv(row + 5, c2 + 3, -3.0)
        c3 = 4 * (t + 3)
        setv(row, c3, m2[0, 0]); setv(row, c3 + 1, m2[1, 0])
        setv(row + 1, c3, m2[0, 1]); setv(row + 1, c3 + 1, m2[1, 1])
        setv(row + 2, c3, m2[0, 2]); setv(row + 2, c3 + 1, m2[1, 2]); setv(row + 2, c3 + 2, 1.0)
        setv(row + 3, c3, m2[1, 0]); setv(row + 3, c3 + 1, -m2[0, 0])
        setv(row + 4, c3, m2[1, 1]); setv(row + 4, c3 + 1, -m2[0, 1])
        setv(row + 5, c3, m2[1, 2]); setv(row + 5, c3 + 1, -m2[0, 2]); setv(row + 5, c3 + 3, 1.0)
        cs = 4 * num_frames + 6 * n1 + 6 * n2 + 6 * t
        for i in range(6):
            setv(row + i, cs + i, slack_sign)

    for sign, upper in [(-1.0, True), (1.0, False)]:
        for t in range(n3):
            add_d3(r, t, sign)
            if upper:
                rowub[r : r + 6] = 0.0
            else:
                rowlb[r : r + 6] = 0.0
            r += 6

    if r != nrows:
        raise RuntimeError(f"LP row construction mismatch: got {r}, expected {nrows}")

    a = coo_matrix((vals, (rows, cols)), shape=(nrows, ncols)).tocsr()
    ub_mask = np.isfinite(rowub)
    lb_mask = np.isfinite(rowlb)
    aub = [a[ub_mask]]
    bub = [rowub[ub_mask]]
    if np.any(lb_mask):
        aub.append(-a[lb_mask])
        bub.append(-rowlb[lb_mask])
    # Avoid densifying: scipy sparse vstack is imported lazily here.
    from scipy.sparse import vstack

    a_ub = vstack(aub, format="csr")
    b_ub = np.concatenate(bub)
    result = linprog(obj, A_ub=a_ub, b_ub=b_ub, bounds=bounds, method="highs")
    if not result.success:
        raise RuntimeError(f"LP rigid smoother failed: {result.message}")

    sol = result.x
    return [mat_from_rigid_params(sol[4 * t : 4 * t + 4]) for t in range(num_frames)]


def solve_lp_motion_stabilizer_affine(
    motions: np.ndarray,
    width: int,
    height: int,
    trim_ratio: float,
    w1: float = 1.0,
    w2: float = 10.0,
    w3: float = 100.0,
    w4: float = 100.0,
    anchor_first: bool = False,
) -> list[np.ndarray]:
    """Experimental 6-DOF affine variant of the video-stab LP smoother."""
    try:
        from scipy.optimize import linprog
        from scipy.sparse import coo_matrix, vstack
    except ImportError as exc:
        raise RuntimeError("lp_affine smoothing requires scipy; install with `py -m pip install scipy`") from exc

    num_frames = len(motions) + 1
    if num_frames <= 1:
        return [np.eye(3, dtype=np.float32)]

    var_per = 6
    n1 = max(0, num_frames - 1)
    n2 = max(0, num_frames - 2)
    n3 = max(0, num_frames - 3)
    ncols = var_per * num_frames + 6 * n1 + 6 * n2 + 6 * n3
    nrows = 8 * num_frames + 2 * 6 * n1 + 2 * 6 * n2 + 2 * 6 * n3
    inf = np.inf

    obj = np.zeros(ncols, dtype=np.float64)
    bounds: list[tuple[float | None, float | None]] = [(None, None)] * ncols
    if anchor_first:
        # Optional gauge fixing.  Otherwise the derivative-only LP has a gauge
        # freedom: adding the same affine transform to every frame costs nothing
        # as long as the corners remain within the crop/FOV box.
        bounds[0:6] = [(1.0, 1.0), (0.0, 0.0), (0.0, 0.0), (0.0, 0.0), (1.0, 1.0), (0.0, 0.0)]
    c = var_per * num_frames
    for count, weight in ((n1, w1), (n2, w2), (n3, w3)):
        for _ in range(count):
            obj[c : c + 6] = [w4 * weight, w4 * weight, weight, w4 * weight, w4 * weight, weight]
            for j in range(6):
                bounds[c + j] = (0.0, None)
            c += 6

    rows: list[int] = []
    cols: list[int] = []
    vals: list[float] = []
    rowlb = np.full(nrows, -inf, dtype=np.float64)
    rowub = np.full(nrows, inf, dtype=np.float64)

    def setv(row: int, col: int, value: float):
        if abs(value) > 1e-12:
            rows.append(row)
            cols.append(col)
            vals.append(float(value))

    def add_product(row: int, frame_idx: int, right_mat: np.ndarray, coeff: float):
        base = var_per * frame_idx
        a = right_mat.astype(np.float64)
        for out_row in range(2):
            for out_col in range(3):
                rr = row + out_row * 3 + out_col
                vv = base + out_row * 3
                setv(rr, vv, coeff * a[0, out_col])
                setv(rr, vv + 1, coeff * a[1, out_col])
                setv(rr, vv + 2, coeff * a[2, out_col])

    r = 0
    w = float(width)
    h = float(height)
    tw = w * float(trim_ratio)
    th = h * float(trim_ratio)
    corners = [(0.0, 0.0), (w, 0.0), (w, h), (0.0, h)]
    for t in range(num_frames):
        c = var_per * t
        for x, y in corners:
            setv(r, c, x); setv(r, c + 1, y); setv(r, c + 2, 1.0)
            setv(r + 1, c + 3, x); setv(r + 1, c + 4, y); setv(r + 1, c + 5, 1.0)
            rowlb[r] = x - tw; rowub[r] = x + tw
            rowlb[r + 1] = y - th; rowub[r + 1] = y + th
            r += 2

    affine_motions = [transform_to_affine_3x3(m) for m in motions]
    identity = np.eye(3, dtype=np.float32)

    def add_diff_block(row: int, terms: list[tuple[int, np.ndarray, float]], slack_offset: int, slack_sign: float):
        for frame_idx, right_mat, coeff in terms:
            add_product(row, frame_idx, right_mat, coeff)
        for i in range(6):
            setv(row + i, slack_offset + i, slack_sign)

    for sign, upper in [(-1.0, True), (1.0, False)]:
        for t in range(n1):
            add_diff_block(r, [(t + 1, affine_motions[t], 1.0), (t, identity, -1.0)], var_per * num_frames + 6 * t, sign)
            if upper:
                rowub[r : r + 6] = 0.0
            else:
                rowlb[r : r + 6] = 0.0
            r += 6

    for sign, upper in [(-1.0, True), (1.0, False)]:
        for t in range(n2):
            add_diff_block(
                r,
                [(t + 2, affine_motions[t + 1], 1.0), (t + 1, identity + affine_motions[t], -1.0), (t, identity, 1.0)],
                var_per * num_frames + 6 * n1 + 6 * t,
                sign,
            )
            if upper:
                rowub[r : r + 6] = 0.0
            else:
                rowlb[r : r + 6] = 0.0
            r += 6

    for sign, upper in [(-1.0, True), (1.0, False)]:
        for t in range(n3):
            add_diff_block(
                r,
                [
                    (t + 3, affine_motions[t + 2], 1.0),
                    (t + 2, identity + 2.0 * affine_motions[t + 1], -1.0),
                    (t + 1, 2.0 * identity + affine_motions[t], 1.0),
                    (t, identity, -1.0),
                ],
                var_per * num_frames + 6 * n1 + 6 * n2 + 6 * t,
                sign,
            )
            if upper:
                rowub[r : r + 6] = 0.0
            else:
                rowlb[r : r + 6] = 0.0
            r += 6

    if r != nrows:
        raise RuntimeError(f"Affine LP row construction mismatch: got {r}, expected {nrows}")

    a = coo_matrix((vals, (rows, cols)), shape=(nrows, ncols)).tocsr()
    ub_mask = np.isfinite(rowub)
    lb_mask = np.isfinite(rowlb)
    aub = [a[ub_mask]]
    bub = [rowub[ub_mask]]
    if np.any(lb_mask):
        aub.append(-a[lb_mask])
        bub.append(-rowlb[lb_mask])
    result = linprog(obj, A_ub=vstack(aub, format="csr"), b_ub=np.concatenate(bub), bounds=bounds, method="highs")
    if not result.success:
        raise RuntimeError(f"Affine LP smoother failed: {result.message}")

    sol = result.x
    mats = []
    for t in range(num_frames):
        s = sol[var_per * t : var_per * t + var_per]
        mats.append(np.array([[s[0], s[1], s[2]], [s[3], s[4], s[5]], [0.0, 0.0, 1.0]], dtype=np.float32))
    return mats


def smooth_trajectory_with_constraints(
    trajectory: np.ndarray,
    radius: int,
    method: str,
    gaussian_stdev: float,
    width: int,
    height: int,
    crop_ratio: float,
    margin_scale: float,
    constrained_accel_limit_px: float,
    constrained_accel_limit_deg: float,
    constrained_projection_iters: int,
) -> tuple[np.ndarray, int, int]:
    if method in {"lp_rigid", "lp_affine"}:
        transforms = np.empty_like(trajectory, dtype=np.float32)
        transforms[0] = trajectory[0]
        if len(trajectory) > 1:
            transforms[1:] = trajectory[1:] - trajectory[:-1]
        lp_solver = solve_lp_motion_stabilizer_affine if method == "lp_affine" else solve_lp_motion_stabilizer_rigid
        stabilization_mats = lp_solver(transforms, width, height, trim_ratio=(1.0 - float(crop_ratio)) * 0.5 * float(margin_scale))
        stabilization_transforms = np.array([affine_3x3_to_transform(mat) for mat in stabilization_mats[1:]], dtype=np.float32)
        return trajectory + stabilization_transforms - transforms, 0, 0

    if method in {"constrained_qp", "constrained_qp_l1"}:
        smoothed = constrained_qp_smooth_trajectory(
            trajectory,
            width,
            height,
            crop_ratio,
            margin_scale,
            constrained_accel_limit_px,
            constrained_accel_limit_deg,
            use_l1=(method == "constrained_qp_l1"),
        )
        return smoothed, 0, 0

    base_method = "gaussian" if method == "constrained_gaussian" else "moving_average"
    smoothed = smooth_trajectory(trajectory, radius, base_method, gaussian_stdev)
    if method not in {"constrained_box", "constrained_gaussian"}:
        return smoothed, 0, 0

    margins = trajectory_margin_limits(width, height, crop_ratio, margin_scale)
    accel_lims = acceleration_limits(constrained_accel_limit_px, constrained_accel_limit_deg)
    return project_trajectory_box_and_accel(trajectory, smoothed, margins, accel_lims, constrained_projection_iters)


def interpolate_invalid_transforms(transforms: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
    """Fill invalid frame-to-frame transforms by linear interpolation instead of last-good copy."""
    filled = np.array(transforms, copy=True, dtype=np.float32)
    n = len(filled)
    if n == 0 or bool(np.all(valid_mask)):
        return filled

    valid_indices = np.flatnonzero(valid_mask)
    if len(valid_indices) == 0:
        return np.zeros_like(filled)

    first_valid = int(valid_indices[0])
    last_valid = int(valid_indices[-1])
    filled[:first_valid] = filled[first_valid]
    filled[last_valid + 1 :] = filled[last_valid]

    i = first_valid
    while i <= last_valid:
        if valid_mask[i]:
            i += 1
            continue
        start = i - 1
        end = i
        while end <= last_valid and not valid_mask[end]:
            end += 1
        # Fill (start, end) with a smooth linear bridge between surrounding valid transforms.
        span = end - start
        for j in range(1, span):
            alpha = j / float(span)
            filled[start + j] = (1.0 - alpha) * filled[start] + alpha * filled[end]
        i = end + 1
    return filled


def confidence_repair_valid_mask(
    transforms: np.ndarray,
    valid_mask: np.ndarray,
    after_reject_counts: list[int],
    inlier_counts: list[int],
    inlier_ratios: list[float],
    width: int,
    height: int,
    min_after_reject: int,
    min_inliers_conf: int,
    min_inlier_ratio_conf: float,
    jump_limit_px: float,
    jump_limit_deg: float,
    dilate_frames: int,
) -> tuple[np.ndarray, int, int]:
    """Promote low-confidence-but-formally-valid motion estimates to interpolation gaps.

    This is a foreground/confidence-aware repair hook: when feature support,
    RANSAC confidence, or a raw transform jump says the estimate is unreliable,
    we let the smoother see it as missing data instead of trusting a foreground-
    dominated affine estimate.
    """
    repaired = np.array(valid_mask, copy=True, dtype=bool)
    n = len(repaired)
    if n == 0:
        return repaired, 0, 0

    suspicious = np.zeros(n, dtype=bool)
    if min_after_reject > 0:
        counts = np.asarray(after_reject_counts, dtype=np.int32)
        suspicious |= counts[:n] < int(min_after_reject)
    if min_inliers_conf > 0:
        counts = np.asarray(inlier_counts, dtype=np.int32)
        suspicious |= counts[:n] < int(min_inliers_conf)
    if min_inlier_ratio_conf > 0:
        ratios = np.asarray(inlier_ratios, dtype=np.float32)
        suspicious |= ratios[:n] < float(min_inlier_ratio_conf)

    if len(transforms) >= 2 and (jump_limit_px > 0 or jump_limit_deg > 0):
        half_diag = max(1.0, 0.5 * math.hypot(float(width), float(height)))
        angle_limit_px = half_diag * math.radians(jump_limit_deg) if jump_limit_deg > 0 else 0.0
        threshold = max(float(jump_limit_px), float(angle_limit_px), 0.0)
        if threshold > 0:
            diff = transforms[1:] - transforms[:-1]
            mag = np.sqrt(diff[:, 0] * diff[:, 0] + diff[:, 1] * diff[:, 1] + (diff[:, 2] * half_diag) * (diff[:, 2] * half_diag))
            for k in np.flatnonzero(mag > threshold):
                suspicious[k] = True
                suspicious[k + 1] = True

    suspicious &= repaired
    if dilate_frames > 0 and np.any(suspicious):
        dilated = suspicious.copy()
        radius = int(dilate_frames)
        for idx in np.flatnonzero(suspicious):
            lo = max(0, int(idx) - radius)
            hi = min(n, int(idx) + radius + 1)
            dilated[lo:hi] = True
        suspicious = dilated & repaired

    before_valid = int(np.sum(repaired))
    repaired[suspicious] = False
    after_valid = int(np.sum(repaired))
    repaired_frames = int(np.sum(suspicious))
    return repaired, repaired_frames, before_valid - after_valid


def limit_transform_sequence(
    transforms: np.ndarray,
    width: int,
    max_translation_ratio: float,
    max_rotation_deg: float,
    accel_limit_px: float,
    accel_limit_deg: float,
) -> tuple[np.ndarray, int, int]:
    """Clamp raw transform and its second difference to suppress spikes/rollback."""
    limited = np.array(transforms, copy=True, dtype=np.float32)
    if len(limited) == 0:
        return limited, 0, 0

    first_order_clamps = 0
    accel_clamps = 0

    if max_translation_ratio > 0:
        max_translation = float(width) * max_translation_ratio
        before = limited[:, :2].copy()
        limited[:, 0] = np.clip(limited[:, 0], -max_translation, max_translation)
        limited[:, 1] = np.clip(limited[:, 1], -max_translation, max_translation)
        first_order_clamps += int(np.sum(np.abs(before - limited[:, :2]) > 1e-6))

    if max_rotation_deg > 0:
        max_rotation = math.radians(max_rotation_deg)
        before_da = limited[:, 2].copy()
        limited[:, 2] = np.clip(limited[:, 2], -max_rotation, max_rotation)
        first_order_clamps += int(np.sum(np.abs(before_da - limited[:, 2]) > 1e-8))

    if len(limited) >= 3:
        limits = np.array(
            [
                accel_limit_px if accel_limit_px > 0 else np.inf,
                accel_limit_px if accel_limit_px > 0 else np.inf,
                math.radians(accel_limit_deg) if accel_limit_deg > 0 else np.inf,
            ],
            dtype=np.float32,
        )
        for i in range(2, len(limited)):
            predicted = 2.0 * limited[i - 1] - limited[i - 2]
            accel = limited[i] - predicted
            clamped_accel = np.clip(accel, -limits, limits)
            if np.any(np.abs(accel - clamped_accel) > 1e-6):
                accel_clamps += int(np.sum(np.abs(accel - clamped_accel) > 1e-6))
                limited[i] = predicted + clamped_accel

    return limited, first_order_clamps, accel_clamps


def limit_final_derivatives(
    transforms: np.ndarray,
    accel_limit_px: float,
    accel_limit_deg: float,
    jerk_limit_px: float,
    jerk_limit_deg: float,
    accel_blend: float,
    jerk_blend: float,
) -> tuple[np.ndarray, int, int]:
    """Causal final-warp derivative limiter, inspired by LP 2nd/3rd derivative constraints."""
    limited = np.array(transforms, copy=True, dtype=np.float32)
    if len(limited) == 0:
        return limited, 0, 0

    accel_blend = float(np.clip(accel_blend, 0.0, 1.0))
    jerk_blend = float(np.clip(jerk_blend, 0.0, 1.0))

    accel_clamps = 0
    jerk_clamps = 0
    accel_limits = np.array(
        [
            accel_limit_px if accel_limit_px > 0 else np.inf,
            accel_limit_px if accel_limit_px > 0 else np.inf,
            math.radians(accel_limit_deg) if accel_limit_deg > 0 else np.inf,
        ],
        dtype=np.float32,
    )
    jerk_limits = np.array(
        [
            jerk_limit_px if jerk_limit_px > 0 else np.inf,
            jerk_limit_px if jerk_limit_px > 0 else np.inf,
            math.radians(jerk_limit_deg) if jerk_limit_deg > 0 else np.inf,
        ],
        dtype=np.float32,
    )

    for i in range(len(limited)):
        if i >= 3 and np.any(np.isfinite(jerk_limits)):
            predicted = 3.0 * limited[i - 1] - 3.0 * limited[i - 2] + limited[i - 3]
            jerk = limited[i] - predicted
            clamped_jerk = np.clip(jerk, -jerk_limits, jerk_limits)
            if np.any(np.abs(jerk - clamped_jerk) > 1e-6):
                jerk_clamps += int(np.sum(np.abs(jerk - clamped_jerk) > 1e-6))
                projected = predicted + clamped_jerk
                limited[i] = (1.0 - jerk_blend) * limited[i] + jerk_blend * projected

        if i >= 2 and np.any(np.isfinite(accel_limits)):
            predicted = 2.0 * limited[i - 1] - limited[i - 2]
            accel = limited[i] - predicted
            clamped_accel = np.clip(accel, -accel_limits, accel_limits)
            if np.any(np.abs(accel - clamped_accel) > 1e-6):
                accel_clamps += int(np.sum(np.abs(accel - clamped_accel) > 1e-6))
                projected = predicted + clamped_accel
                limited[i] = (1.0 - accel_blend) * limited[i] + accel_blend * projected

    return limited, accel_clamps, jerk_clamps


def repair_local_transform_spikes(
    transforms: np.ndarray,
    width: int,
    height: int,
    limit_px: float,
    limit_deg: float,
    top_percent: float,
    blend: float,
    iterations: int,
) -> tuple[np.ndarray, int, float]:
    """Localized non-causal diagnostic/repair pass for residual-safe spike cleanup.

    This intentionally edits only frames whose final warp sequence has unusually
    large second differences.  It is meant for the current CPU-quality baseline
    investigation, not for the later real-time causal path.
    """
    repaired = np.array(transforms, copy=True, dtype=np.float32)
    n = len(repaired)
    if n < 3 or iterations <= 0 or blend <= 0:
        return repaired, 0, 0.0

    blend = float(np.clip(blend, 0.0, 1.0))
    half_diag = max(1.0, 0.5 * math.hypot(float(width), float(height)))
    angle_scale = half_diag
    limit_angle_px = angle_scale * math.radians(limit_deg) if limit_deg > 0 else 0.0
    threshold = max(float(limit_px), float(limit_angle_px), 0.0)

    total_repairs = 0
    max_seen = 0.0
    for _ in range(max(1, int(iterations))):
        second = repaired[1:] - repaired[:-1]
        mag = np.sqrt(second[:, 0] * second[:, 0] + second[:, 1] * second[:, 1] + (second[:, 2] * angle_scale) * (second[:, 2] * angle_scale))
        if len(mag) == 0:
            break
        max_seen = max(max_seen, float(np.max(mag)))

        active = np.zeros(n, dtype=bool)
        if threshold > 0:
            # mag[k] is the jump between transform k and k+1; smooth both sides
            # of the discontinuity so a one-frame pull does not just move the spike.
            for k in np.flatnonzero(mag > threshold):
                active[k] = True
                active[k + 1] = True
        if top_percent > 0:
            top_n = max(1, int(math.ceil(len(mag) * float(top_percent) * 0.01)))
            for k in np.argsort(mag)[-top_n:]:
                active[k] = True
                active[k + 1] = True

        active[0] = False
        active[-1] = False
        indices = np.flatnonzero(active)
        if len(indices) == 0:
            break

        before = repaired.copy()
        for i in indices:
            local_mid = 0.5 * (before[i - 1] + before[i + 1])
            repaired[i] = (1.0 - blend) * before[i] + blend * local_mid
        total_repairs += int(len(indices))

    return repaired.astype(np.float32), total_repairs, max_seen


def relax_correction_after_invalid(
    correction: np.ndarray,
    valid_mask: np.ndarray,
    alpha: float,
    recovery_frames: int,
) -> np.ndarray:
    """After an invalid segment, fade correction back in to avoid snap-back."""
    relaxed = np.array(correction, copy=True, dtype=np.float32)
    if len(relaxed) == 0 or recovery_frames <= 0 or alpha <= 0 or alpha >= 1:
        return relaxed

    for i in range(1, len(relaxed)):
        if valid_mask[i] and not valid_mask[i - 1]:
            prev = relaxed[i - 1].copy()
            end = min(len(relaxed), i + recovery_frames)
            for j in range(i, end):
                prev = (1.0 - alpha) * prev + alpha * relaxed[j]
                relaxed[j] = prev
    return relaxed


def clamp_correction_to_crop_margin(correction: np.ndarray, width: int, height: int, crop_ratio: float, limit_ratio: float) -> tuple[np.ndarray, int]:
    """Limit correction amplitude so stabilization does not exceed the reserved crop margin."""
    if limit_ratio <= 0 or crop_ratio <= 0 or crop_ratio >= 1 or len(correction) == 0:
        return correction, 0
    limited = np.array(correction, copy=True, dtype=np.float32)
    margin_x = max(0.0, (1.0 - crop_ratio) * 0.5 * width * limit_ratio)
    margin_y = max(0.0, (1.0 - crop_ratio) * 0.5 * height * limit_ratio)
    before = limited[:, :2].copy()
    limited[:, 0] = np.clip(limited[:, 0], -margin_x, margin_x)
    limited[:, 1] = np.clip(limited[:, 1], -margin_y, margin_y)
    clamps = int(np.sum(np.abs(before - limited[:, :2]) > 1e-6))
    return limited, clamps


def transform_to_affine_3x3(transform: np.ndarray) -> np.ndarray:
    dx, dy, da = transform
    mat = np.array(
        [
            [math.cos(float(da)), -math.sin(float(da)), float(dx)],
            [math.sin(float(da)), math.cos(float(da)), float(dy)],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float32,
    )
    return mat


def affine_3x3_to_transform(mat: np.ndarray) -> np.ndarray:
    dx = float(mat[0, 2])
    dy = float(mat[1, 2])
    da = math.atan2(float(mat[1, 0]), float(mat[0, 0]))
    return np.array([dx, dy, da], dtype=np.float32)


def apply_intent_proximity_to_mats(
    lp_mats: list[np.ndarray],
    raw_transforms: np.ndarray,
    trajectory: np.ndarray,
    width: int,
    height: int,
    radius: int,
    stdev: float,
    band_px: float,
    blend: float,
    strength: float,
) -> tuple[list[np.ndarray], int, float, float]:
    """Pull LP correction toward a low-pass intent correction when it drifts too far.

    First principles: raw trajectory = low-frequency operator intent + high-frequency
    shake.  The LP smoother removes shake, but on high-motion clips it can fight the
    FOV/mask constraint and then get rolled back, creating residual/acc spikes.  This
    post-pass keeps the final correction near a low-pass intent path instead of near
    an over-smoothed global lock.

    It is intentionally disabled unless ``blend > 0``.  ``band_px`` is measured in a
    translation-equivalent norm: dx/dy plus rotation converted by half image diagonal.
    """
    blend = float(np.clip(blend, 0.0, 1.0))
    if blend <= 0.0 or not lp_mats or len(raw_transforms) == 0:
        return lp_mats, 0, 0.0, 0.0

    n = min(len(lp_mats), len(raw_transforms), len(trajectory))
    if n <= 0:
        return lp_mats, 0, 0.0, 0.0

    intent_trajectory = smooth_trajectory(trajectory, max(1, int(radius)), "gaussian", stdev)
    intent_delta = (intent_trajectory - trajectory) * float(np.clip(strength, 0.0, 1.0))
    intent_transforms = raw_transforms + intent_delta
    half_diag = max(1.0, 0.5 * math.hypot(float(width), float(height)))
    band = max(0.0, float(band_px))

    out: list[np.ndarray] = []
    applied = 0
    gaps: list[float] = []
    for i, mat in enumerate(lp_mats):
        cur = mat.astype(np.float32)
        if i >= n:
            out.append(cur)
            continue
        lp_pose = affine_3x3_to_transform(cur)
        intent_pose = intent_transforms[i]
        diff = lp_pose - intent_pose
        gap = float(math.hypot(float(diff[0]), float(diff[1])) + abs(float(diff[2])) * half_diag)
        gaps.append(gap)
        if gap <= band:
            out.append(cur)
            continue

        # Soft gate: only pull the excess beyond the intent band.  This prevents
        # unnecessary weakening on frames where LP already follows the intended path.
        excess_ratio = (gap - band) / max(gap, 1e-6)
        alpha = blend * excess_ratio
        intent_mat = transform_to_affine_3x3(intent_pose)
        out.append(((1.0 - alpha) * cur + alpha * intent_mat).astype(np.float32))
        applied += 1

    return out, applied, float(np.mean(gaps)) if gaps else 0.0, float(np.max(gaps)) if gaps else 0.0


def _transformed_corners(mat: np.ndarray, width: int, height: int) -> np.ndarray:
    corners = np.array(
        [
            [0.0, 0.0, 1.0],
            [float(width), 0.0, 1.0],
            [float(width), float(height), 1.0],
            [0.0, float(height), 1.0],
        ],
        dtype=np.float32,
    )
    transformed = (mat.astype(np.float32) @ corners.T).T
    z = transformed[:, 2:3]
    z[np.abs(z) < 1e-6] = 1.0
    return transformed[:, :2] / z


def is_good_motion(mat: np.ndarray, width: int, height: int, trim_ratio: float) -> bool:
    """OpenCV videostab-style inclusion check: transformed corners must cover the center safe rect."""
    if trim_ratio < 0 or trim_ratio >= 0.5:
        return False
    transformed = _transformed_corners(mat, width, height)
    dx = math.floor(float(width) * trim_ratio)
    dy = math.floor(float(height) * trim_ratio)
    safe_corners = [
        (float(dx), float(dy)),
        (float(width - dx), float(dy)),
        (float(width - dx), float(height - dy)),
        (float(dx), float(height - dy)),
    ]
    polygon = transformed.astype(np.float32)
    return all(cv2.pointPolygonTest(polygon, point, False) >= -1e-4 for point in safe_corners)


def relax_motion_to_identity(mat: np.ndarray, alpha: float) -> np.ndarray:
    """Linear relaxation toward identity, matching OpenCV videostab relaxMotion()."""
    identity = np.eye(3, dtype=np.float32)
    return (1.0 - float(alpha)) * mat.astype(np.float32) + float(alpha) * identity


def center_scale_3x3(width: int, height: int, scale: float) -> np.ndarray:
    center_x = float(width) * 0.5
    center_y = float(height) * 0.5
    return np.array(
        [
            [float(scale), 0.0, (1.0 - float(scale)) * center_x],
            [0.0, float(scale), (1.0 - float(scale)) * center_y],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float32,
    )


def ensure_inclusion_constraint(mat: np.ndarray, width: int, height: int, trim_ratio: float, zoom_scale: float = 1.0) -> tuple[np.ndarray, float]:
    """Relax a smoothed stabilization/correction matrix toward identity until it covers the safe rect."""
    zoom_mat = center_scale_3x3(width, height, zoom_scale)

    def good(candidate: np.ndarray) -> bool:
        return is_good_motion(zoom_mat @ candidate, width, height, trim_ratio)

    if trim_ratio <= 0 or trim_ratio >= 0.5 or good(mat):
        return mat.astype(np.float32), 0.0

    left = 0.0
    right = 1.0
    relaxed = np.eye(3, dtype=np.float32)
    for _ in range(16):
        mid = (left + right) * 0.5
        cur = relax_motion_to_identity(mat, mid)
        if good(cur):
            right = mid
            relaxed = cur
        else:
            left = mid
    return relaxed.astype(np.float32), float(right)


def smooth_relaxation_alpha(
    required_alpha: np.ndarray,
    release_tau_frames: float,
    release_rate_limit: float,
    attack_rate_limit: float,
) -> np.ndarray:
    """Smooth inclusion relaxation alpha in both directions to reduce correction spikes.

    Alpha means how much the smoothed correction is relaxed toward identity. A larger
    alpha is safer for field-of-view inclusion, but an instantaneous rise can create
    visible acceleration spikes. ``attack_rate_limit`` limits this upward movement;
    the later valid-mask safety rollback remains the hard black-border guard.
    """
    if len(required_alpha) == 0:
        return np.array(required_alpha, copy=True, dtype=np.float32)
    if release_tau_frames <= 0 and release_rate_limit <= 0 and attack_rate_limit <= 0:
        return np.array(required_alpha, copy=True, dtype=np.float32)

    smoothed = np.array(required_alpha, copy=True, dtype=np.float32)
    release_iir = 1.0 if release_tau_frames <= 0 else 1.0 / (release_tau_frames + 1.0)
    prev = float(smoothed[0])
    for i in range(1, len(smoothed)):
        req = float(required_alpha[i])
        if req >= prev:
            cur = req
            if attack_rate_limit > 0:
                # Increasing alpha means less correction and is needed for inclusion
                # safety, but a one-frame jump is a major source of second-diff spikes.
                cur = min(cur, prev + attack_rate_limit)
        else:
            cur = (1.0 - release_iir) * prev + release_iir * req
            if release_rate_limit > 0:
                cur = max(cur, prev - release_rate_limit)
            cur = max(cur, req)
        smoothed[i] = np.float32(np.clip(cur, 0.0, 1.0))
        prev = float(smoothed[i])
    return smoothed


def apply_inclusion_relaxation(
    transforms: np.ndarray,
    width: int,
    height: int,
    trim_ratio: float,
    zoom_curve: np.ndarray | None = None,
) -> tuple[np.ndarray, int, float, np.ndarray, np.ndarray]:
    if trim_ratio <= 0 or len(transforms) == 0:
        zeros = np.zeros(len(transforms), dtype=np.float32)
        return transforms, 0, 0.0, zeros, zeros
    relaxed = np.array(transforms, copy=True, dtype=np.float32)
    required_alpha = np.zeros(len(transforms), dtype=np.float32)
    relax_count = 0
    max_alpha = 0.0
    for i, transform in enumerate(relaxed):
        mat = transform_to_affine_3x3(transform)
        zoom_scale = 1.0 if zoom_curve is None or i >= len(zoom_curve) else float(zoom_curve[i])
        relaxed_mat, alpha = ensure_inclusion_constraint(mat, width, height, trim_ratio, zoom_scale)
        required_alpha[i] = np.float32(alpha)
        if alpha > 1e-6:
            relax_count += 1
            max_alpha = max(max_alpha, alpha)
            relaxed[i] = affine_3x3_to_transform(relaxed_mat)
    return relaxed, relax_count, max_alpha, required_alpha, required_alpha.copy()


def apply_smoothed_inclusion_relaxation(
    transforms: np.ndarray,
    width: int,
    height: int,
    trim_ratio: float,
    zoom_curve: np.ndarray | None,
    release_tau_frames: float,
    release_rate_limit: float,
    attack_rate_limit: float,
) -> tuple[np.ndarray, int, float, np.ndarray, np.ndarray]:
    if trim_ratio <= 0 or len(transforms) == 0:
        zeros = np.zeros(len(transforms), dtype=np.float32)
        return transforms, 0, 0.0, zeros, zeros

    mats = [transform_to_affine_3x3(transform) for transform in transforms]
    required_alpha = np.zeros(len(transforms), dtype=np.float32)
    for i, mat in enumerate(mats):
        zoom_scale = 1.0 if zoom_curve is None or i >= len(zoom_curve) else float(zoom_curve[i])
        _, alpha = ensure_inclusion_constraint(mat, width, height, trim_ratio, zoom_scale)
        required_alpha[i] = np.float32(alpha)

    applied_alpha = smooth_relaxation_alpha(required_alpha, release_tau_frames, release_rate_limit, attack_rate_limit)
    relaxed = np.array(transforms, copy=True, dtype=np.float32)
    relax_count = 0
    max_alpha = 0.0
    for i, alpha in enumerate(applied_alpha):
        alpha_f = float(alpha)
        if alpha_f > 1e-6:
            relax_count += 1
            max_alpha = max(max_alpha, alpha_f)
            relaxed[i] = affine_3x3_to_transform(relax_motion_to_identity(mats[i], alpha_f))
    return relaxed, relax_count, max_alpha, required_alpha, applied_alpha


def estimate_required_trim_ratio(mat: np.ndarray, width: int, height: int) -> float:
    """Estimate minimum center crop ratio required by the current correction matrix."""
    if is_good_motion(mat, width, height, 0.0):
        return 0.0
    left = 0.0
    right = 0.49
    if not is_good_motion(mat, width, height, right):
        return right
    for _ in range(16):
        mid = (left + right) * 0.5
        if is_good_motion(mat, width, height, mid):
            right = mid
        else:
            left = mid
    return float(right)


def rolling_max_causal(values: np.ndarray, window: int) -> np.ndarray:
    if window <= 1 or len(values) == 0:
        return np.array(values, copy=True, dtype=np.float32)
    out = np.empty_like(values, dtype=np.float32)
    for i in range(len(values)):
        start = max(0, i - window + 1)
        out[i] = float(np.max(values[start : i + 1]))
    return out


def gaussian_average_causal(values: np.ndarray, radius: int, stdev: float) -> np.ndarray:
    if radius <= 0 or len(values) == 0:
        return np.array(values, copy=True, dtype=np.float32)
    if stdev <= 0:
        stdev = max(1.0, float(radius) / 3.0)
    offsets = np.arange(0, radius + 1, dtype=np.float32)
    weights = np.exp(-0.5 * (offsets / stdev) * (offsets / stdev)).astype(np.float32)
    weights /= np.sum(weights)
    out = np.empty_like(values, dtype=np.float32)
    for i in range(len(values)):
        acc = 0.0
        norm = 0.0
        for k, weight in enumerate(weights):
            idx = i - k
            if idx < 0:
                idx = 0
            acc += float(values[idx]) * float(weight)
            norm += float(weight)
        out[i] = acc / max(norm, 1e-6)
    return out


def rate_limit_sequence(values: np.ndarray, max_step: float) -> np.ndarray:
    if max_step <= 0 or len(values) == 0:
        return np.array(values, copy=True, dtype=np.float32)
    out = np.array(values, copy=True, dtype=np.float32)
    for i in range(1, len(out)):
        delta = float(out[i] - out[i - 1])
        if delta > max_step:
            out[i] = out[i - 1] + max_step
        elif delta < -max_step:
            out[i] = out[i - 1] - max_step
    return out


def apply_hysteresis(values: np.ndarray, deadband: float) -> np.ndarray:
    if deadband <= 0 or len(values) == 0:
        return np.array(values, copy=True, dtype=np.float32)
    out = np.array(values, copy=True, dtype=np.float32)
    prev = float(out[0])
    for i in range(1, len(out)):
        if abs(float(out[i]) - prev) < deadband:
            out[i] = prev
        else:
            prev = float(out[i])
    return out


def compute_dynamic_zoom_curve(
    transforms: np.ndarray,
    width: int,
    height: int,
    enabled: bool,
    rolling_window: int,
    gaussian_radius: int,
    gaussian_stdev: float,
    rate_limit: float,
    min_zoom: float,
    max_zoom: float,
    hysteresis: float,
) -> tuple[np.ndarray, np.ndarray]:
    if not enabled or len(transforms) == 0:
        zoom = np.ones(len(transforms), dtype=np.float32)
        return zoom, zoom.copy()

    required_trim = np.array(
        [estimate_required_trim_ratio(transform_to_affine_3x3(transform), width, height) for transform in transforms],
        dtype=np.float32,
    )
    required_zoom = 1.0 / np.maximum(1e-3, 1.0 - 2.0 * required_trim)
    zoom = rolling_max_causal(required_zoom.astype(np.float32), rolling_window)
    zoom = gaussian_average_causal(zoom, gaussian_radius, gaussian_stdev).astype(np.float32)
    zoom = rate_limit_sequence(zoom, rate_limit)
    zoom = np.clip(zoom, min_zoom, max_zoom).astype(np.float32)
    zoom = apply_hysteresis(zoom, hysteresis)
    zoom = np.clip(zoom, min_zoom, max_zoom).astype(np.float32)
    return zoom, required_zoom.astype(np.float32)


def fix_border(frame: np.ndarray, scale: float) -> np.ndarray:
    h, w = frame.shape[:2]
    mat = cv2.getRotationMatrix2D((w / 2, h / 2), 0, scale)
    return cv2.warpAffine(frame, mat, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def scale_mask(mask: np.ndarray, scale: float) -> np.ndarray:
    h, w = mask.shape[:2]
    mat = cv2.getRotationMatrix2D((w / 2, h / 2), 0, scale)
    return cv2.warpAffine(mask, mat, (w, h), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0)


def interpolation_from_name(name: str) -> int:
    mapping = {
        "linear": cv2.INTER_LINEAR,
        "cubic": cv2.INTER_CUBIC,
        "lanczos": cv2.INTER_LANCZOS4,
        "area": cv2.INTER_AREA,
    }
    if name not in mapping:
        raise ValueError(f"Unsupported interpolation: {name}")
    return mapping[name]


def apply_unsharp_mask(frame: np.ndarray, strength: float, sigma: float) -> np.ndarray:
    if strength <= 0:
        return frame
    blurred = cv2.GaussianBlur(frame, (0, 0), max(0.1, sigma))
    return cv2.addWeighted(frame, 1.0 + strength, blurred, -strength, 0)


def fixed_center_crop_and_resize(frame: np.ndarray, crop_ratio: float, interpolation: int = cv2.INTER_LINEAR) -> np.ndarray:
    if crop_ratio <= 0 or crop_ratio > 1:
        raise ValueError("crop_ratio must be in (0, 1]")
    if crop_ratio == 1:
        return frame

    h, w = frame.shape[:2]
    crop_w = int(w * crop_ratio)
    crop_h = int(h * crop_ratio)
    x0 = (w - crop_w) // 2
    y0 = (h - crop_h) // 2
    cropped = frame[y0 : y0 + crop_h, x0 : x0 + crop_w]
    return cv2.resize(cropped, (w, h), interpolation=interpolation)


def black_pixel_ratio(frame: np.ndarray, threshold: int = 8) -> float:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return float(np.mean(gray <= threshold))


def invalid_mask_ratio(mask: np.ndarray, threshold: int = 127) -> float:
    return float(np.mean(mask <= threshold))


def invalid_ratio_for_transform(
    transform: np.ndarray,
    width: int,
    height: int,
    crop_ratio: float,
    border_scale: float,
    zoom_scale: float,
) -> float:
    mask = np.full((height, width), 255, dtype=np.uint8)
    mat = transform_to_affine_3x3(transform)[:2, :]
    mask = cv2.warpAffine(mask, mat, (width, height), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    mask = scale_mask(mask, border_scale * float(zoom_scale))
    mask = fixed_center_crop_and_resize(mask, crop_ratio)
    return invalid_mask_ratio(mask)


def invalid_ratio_for_affine_mat(
    mat: np.ndarray,
    width: int,
    height: int,
    crop_ratio: float,
    border_scale: float,
    zoom_scale: float,
) -> float:
    mask = np.full((height, width), 255, dtype=np.uint8)
    warp = np.asarray(mat, dtype=np.float32)[:2, :]
    mask = cv2.warpAffine(mask, warp, (width, height), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    mask = scale_mask(mask, border_scale * float(zoom_scale))
    mask = fixed_center_crop_and_resize(mask, crop_ratio)
    return invalid_mask_ratio(mask)


def apply_mask_safety_rollback_mats(
    candidate_mats: list[np.ndarray],
    width: int,
    height: int,
    crop_ratio: float,
    border_scale: float,
    zoom_curve: np.ndarray,
    max_invalid_ratio: float,
) -> tuple[list[np.ndarray], int, float, float, float]:
    """Blend arbitrary affine warp matrices toward identity until the valid-mask FOV gate passes."""
    if max_invalid_ratio <= 0 or not candidate_mats:
        return candidate_mats, 0, 1.0, 1.0, 0.0

    identity = np.eye(3, dtype=np.float32)
    safe: list[np.ndarray] = []
    rollback_frames = 0
    betas = []
    worst_invalid = 0.0
    for i, mat in enumerate(candidate_mats):
        cand = np.asarray(mat, dtype=np.float32)
        if cand.shape == (2, 3):
            cand3 = np.vstack([cand, np.array([0.0, 0.0, 1.0], dtype=np.float32)])
        else:
            cand3 = cand.copy()
        zoom_scale = 1.0 if i >= len(zoom_curve) else float(zoom_curve[i])
        candidate_invalid = invalid_ratio_for_affine_mat(cand3, width, height, crop_ratio, border_scale, zoom_scale)
        worst_invalid = max(worst_invalid, candidate_invalid)
        if candidate_invalid <= max_invalid_ratio:
            safe.append(cand3)
            betas.append(1.0)
            continue

        rollback_frames += 1
        low = 0.0
        high = 1.0
        best = 0.0
        for _ in range(10):
            mid = (low + high) * 0.5
            cur = identity + mid * (cand3 - identity)
            cur_invalid = invalid_ratio_for_affine_mat(cur, width, height, crop_ratio, border_scale, zoom_scale)
            worst_invalid = max(worst_invalid, cur_invalid)
            if cur_invalid <= max_invalid_ratio:
                best = mid
                low = mid
            else:
                high = mid
        safe.append(identity + best * (cand3 - identity))
        betas.append(best)

    beta_arr = np.array(betas, dtype=np.float32) if betas else np.ones(1, dtype=np.float32)
    return safe, rollback_frames, float(np.mean(beta_arr)), float(np.min(beta_arr)), float(worst_invalid)


def apply_mask_safety_rollback(
    reference_transforms: np.ndarray,
    candidate_transforms: np.ndarray,
    width: int,
    height: int,
    crop_ratio: float,
    border_scale: float,
    zoom_curve: np.ndarray,
    max_invalid_ratio: float,
) -> tuple[np.ndarray, int, float, float, float]:
    """Blend final-smoothed transforms back to the pre-smoothed reference when valid-mask FOV would fail."""
    if max_invalid_ratio <= 0 or len(candidate_transforms) == 0:
        return candidate_transforms, 0, 1.0, 1.0, 0.0

    safe = np.array(candidate_transforms, copy=True, dtype=np.float32)
    rollback_frames = 0
    betas = []
    worst_invalid = 0.0
    for i in range(len(safe)):
        zoom_scale = 1.0 if i >= len(zoom_curve) else float(zoom_curve[i])
        candidate_invalid = invalid_ratio_for_transform(safe[i], width, height, crop_ratio, border_scale, zoom_scale)
        worst_invalid = max(worst_invalid, candidate_invalid)
        if candidate_invalid <= max_invalid_ratio:
            betas.append(1.0)
            continue

        rollback_frames += 1
        ref = reference_transforms[i]
        cand = candidate_transforms[i]
        ref_invalid = invalid_ratio_for_transform(ref, width, height, crop_ratio, border_scale, zoom_scale)
        worst_invalid = max(worst_invalid, ref_invalid)
        if ref_invalid > max_invalid_ratio:
            # The reference can already be unsafe when an earlier smoother deliberately
            # kept more correction for temporal smoothness. In that case, fall back to
            # the closest safe transform along the path toward identity so the valid-mask
            # gate remains a real hard guard instead of preserving an unsafe reference.
            identity = np.zeros(3, dtype=np.float32)
            low = 0.0
            high = 1.0
            best = 0.0
            for _ in range(10):
                mid = (low + high) * 0.5
                cur = identity + mid * (ref - identity)
                cur_invalid = invalid_ratio_for_transform(cur, width, height, crop_ratio, border_scale, zoom_scale)
                worst_invalid = max(worst_invalid, cur_invalid)
                if cur_invalid <= max_invalid_ratio:
                    best = mid
                    low = mid
                else:
                    high = mid
            safe[i] = identity + best * (ref - identity)
            betas.append(0.0)
            continue

        low = 0.0
        high = 1.0
        best = 0.0
        for _ in range(10):
            mid = (low + high) * 0.5
            cur = ref + mid * (cand - ref)
            cur_invalid = invalid_ratio_for_transform(cur, width, height, crop_ratio, border_scale, zoom_scale)
            worst_invalid = max(worst_invalid, cur_invalid)
            if cur_invalid <= max_invalid_ratio:
                best = mid
                low = mid
            else:
                high = mid
        safe[i] = ref + best * (cand - ref)
        betas.append(best)

    beta_arr = np.array(betas, dtype=np.float32) if betas else np.ones(1, dtype=np.float32)
    return safe, rollback_frames, float(np.mean(beta_arr)), float(np.min(beta_arr)), float(worst_invalid)


class VPIWarpPerspective:
    def __init__(self, backend_name: str):
        import vpi

        backend_map = {
            "vpi_cpu": vpi.Backend.CPU,
            "vpi_cuda": vpi.Backend.CUDA,
            "vpi_vic": vpi.Backend.VIC,
        }
        if backend_name not in backend_map:
            raise ValueError(f"Unsupported VPI warp backend: {backend_name}")
        self.vpi = vpi
        self.backend = backend_map[backend_name]

    def warp_affine(self, frame_bgr: np.ndarray, mat_2x3: np.ndarray) -> np.ndarray:
        mat_3x3 = np.eye(3, dtype=np.float64)
        mat_3x3[:2, :] = mat_2x3.astype(np.float64)
        with self.vpi.Backend.CUDA:
            frame_vpi = self.vpi.asimage(frame_bgr).convert(self.vpi.Format.NV12_ER)
        with self.backend:
            warped = frame_vpi.perspwarp(mat_3x3)
        with self.vpi.Backend.CUDA:
            warped = warped.convert(self.vpi.Format.RGB8)
        with warped.rlock_cpu() as data_rgb:
            rgb = np.array(data_rgb, copy=True)
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def resize_for_estimation(frame_gray: np.ndarray, estimate_scale: float) -> np.ndarray:
    if estimate_scale <= 0 or estimate_scale > 1:
        raise ValueError("estimate_scale must be in (0, 1]")
    if estimate_scale == 1:
        return frame_gray
    h, w = frame_gray.shape[:2]
    scaled_w = max(16, int(round(w * estimate_scale)))
    scaled_h = max(16, int(round(h * estimate_scale)))
    return cv2.resize(frame_gray, (scaled_w, scaled_h), interpolation=cv2.INTER_AREA)


def select_grid_points(points: np.ndarray, image_shape, grid_size: int) -> np.ndarray:
    """Keep spatially distributed points, inspired by lab-cv/video-stab grid selection."""
    if points is None or len(points) == 0 or grid_size <= 1:
        return points

    h, w = image_shape[:2]
    flat = points.reshape(-1, 2)
    selected = []
    occupied = set()
    for point in flat:
        x, y = float(point[0]), float(point[1])
        gx = min(grid_size - 1, max(0, int(x * grid_size / max(1, w))))
        gy = min(grid_size - 1, max(0, int(y * grid_size / max(1, h))))
        cell = (gx, gy)
        if cell in occupied:
            continue
        occupied.add(cell)
        selected.append(point)
    if len(selected) < 8:
        return points
    return np.asarray(selected, dtype=np.float32).reshape(-1, 1, 2)


def reject_foreground_motion(prev_pts: np.ndarray, curr_pts: np.ndarray, threshold: float):
    """Reject points whose dx/dy deviates far from the dominant integer motion mode."""
    if len(prev_pts) < 8 or threshold <= 0:
        return prev_pts, curr_pts, 0, None, None

    prev_flat = prev_pts.reshape(-1, 2)
    curr_flat = curr_pts.reshape(-1, 2)
    disp = curr_flat - prev_flat
    dx_int = np.rint(disp[:, 0]).astype(np.int32)
    dy_int = np.rint(disp[:, 1]).astype(np.int32)

    mode_dx = int(np.bincount(dx_int - dx_int.min()).argmax() + dx_int.min())
    mode_dy = int(np.bincount(dy_int - dy_int.min()).argmax() + dy_int.min())
    keep = (np.abs(disp[:, 0] - mode_dx) <= threshold) & (np.abs(disp[:, 1] - mode_dy) <= threshold)

    if int(np.sum(keep)) < 8:
        return prev_pts, curr_pts, 0, mode_dx, mode_dy
    rejected = int(len(prev_flat) - np.sum(keep))
    return prev_flat[keep].reshape(-1, 1, 2), curr_flat[keep].reshape(-1, 1, 2), rejected, mode_dx, mode_dy


def estimate_transform(
    prev_gray: np.ndarray,
    curr_gray: np.ndarray,
    estimate_scale: float,
    feature_grid_size: int,
    foreground_reject_threshold: float,
    min_inliers: int,
    min_inlier_ratio: float,
    ransac_reproj_threshold: float,
):
    prev_est = resize_for_estimation(prev_gray, estimate_scale)
    curr_est = resize_for_estimation(curr_gray, estimate_scale)
    min_distance = max(5, int(round(30 * estimate_scale)))

    prev_pts = cv2.goodFeaturesToTrack(
        prev_est,
        maxCorners=500,
        qualityLevel=0.01,
        minDistance=min_distance,
        blockSize=3,
    )
    details = {
        "detected_features": 0 if prev_pts is None else int(len(prev_pts)),
        "tracked_features": 0,
        "after_foreground_reject": 0,
        "foreground_rejected": 0,
        "inliers": 0,
        "inlier_ratio": 0.0,
        "fallback_reason": "",
        "dominant_dx": "",
        "dominant_dy": "",
    }
    if prev_pts is None or len(prev_pts) < 8:
        details["fallback_reason"] = "too_few_detected_features"
        return None, details
    prev_pts = select_grid_points(prev_pts, prev_est.shape, feature_grid_size)

    curr_pts, status, _ = cv2.calcOpticalFlowPyrLK(prev_est, curr_est, prev_pts, None)
    if curr_pts is None or status is None:
        details["fallback_reason"] = "lk_failed"
        return None, details

    valid = status.reshape(-1) == 1
    prev_good = prev_pts[valid]
    curr_good = curr_pts[valid]
    details["tracked_features"] = int(len(prev_good))
    if len(prev_good) < 8:
        details["fallback_reason"] = "too_few_tracked_features"
        return None, details

    scaled_reject_threshold = max(1.0, foreground_reject_threshold * estimate_scale)
    prev_good, curr_good, rejected, mode_dx, mode_dy = reject_foreground_motion(prev_good, curr_good, scaled_reject_threshold)
    details["foreground_rejected"] = rejected
    details["after_foreground_reject"] = int(len(prev_good))
    details["dominant_dx"] = "" if mode_dx is None else mode_dx
    details["dominant_dy"] = "" if mode_dy is None else mode_dy
    if len(prev_good) < 8:
        details["fallback_reason"] = "too_few_features_after_foreground_reject"
        return None, details

    mat, inliers = cv2.estimateAffinePartial2D(
        prev_good,
        curr_good,
        method=cv2.RANSAC,
        ransacReprojThreshold=ransac_reproj_threshold,
        maxIters=2000,
        confidence=0.99,
    )
    if mat is None:
        details["fallback_reason"] = "ransac_failed"
        return None, details

    inlier_count = int(np.sum(inliers)) if inliers is not None else int(len(prev_good))
    inlier_ratio = float(inlier_count / max(1, len(prev_good)))
    details["inliers"] = inlier_count
    details["inlier_ratio"] = inlier_ratio
    if inlier_count < min_inliers or inlier_ratio < min_inlier_ratio:
        details["fallback_reason"] = "low_inlier_confidence"
        return None, details

    dx = mat[0, 2] / estimate_scale
    dy = mat[1, 2] / estimate_scale
    da = math.atan2(mat[1, 0], mat[0, 0])
    return np.array([dx, dy, da], dtype=np.float32), details


def stabilize_video(
    input_path: Path,
    output_path: Path,
    metrics_path: Path,
    smoothing_radius: int,
    smoothing_method: str,
    gaussian_stdev: float,
    border_scale: float,
    crop_ratio: float,
    crop_interpolation: str,
    sharpen_strength: float,
    sharpen_sigma: float,
    warp_backend: str,
    estimate_scale: float,
    feature_grid_size: int,
    foreground_reject_threshold: float,
    min_inliers: int,
    min_inlier_ratio: float,
    ransac_reproj_threshold: float,
    fallback_mode: str,
    max_translation_ratio: float,
    max_rotation_deg: float,
    accel_limit_px: float,
    accel_limit_deg: float,
    fallback_recovery_alpha: float,
    fallback_recovery_frames: int,
    correction_limit_ratio: float,
    inclusion_trim_ratio: float,
    dynamic_zoom: bool,
    zoom_rolling_window: int,
    zoom_gaussian_radius: int,
    zoom_gaussian_stdev: float,
    zoom_rate_limit: float,
    min_zoom: float,
    max_zoom: float,
    zoom_hysteresis: float,
    constrained_margin_scale: float,
    lp_trim_ratio: float,
    constrained_accel_limit_px: float,
    constrained_accel_limit_deg: float,
    constrained_projection_iters: int,
    inclusion_alpha_release_tau: float,
    inclusion_alpha_release_rate: float,
    inclusion_alpha_attack_rate: float,
    final_accel_limit_px: float,
    final_accel_limit_deg: float,
    final_jerk_limit_px: float,
    final_jerk_limit_deg: float,
    final_accel_blend: float,
    final_jerk_blend: float,
    mask_safety_max_invalid: float,
    confidence_min_after_reject: int,
    confidence_min_inliers: int,
    confidence_min_inlier_ratio: float,
    confidence_jump_limit_px: float,
    confidence_jump_limit_deg: float,
    confidence_dilate_frames: int,
    spike_repair_limit_px: float,
    spike_repair_limit_deg: float,
    spike_repair_top_percent: float,
    spike_repair_blend: float,
    spike_repair_iterations: int,
    intent_proximity_blend: float,
    intent_proximity_band_px: float,
    intent_proximity_radius: int,
    intent_proximity_stdev: float,
    stabilization_strength: float,
    lp_anchor_first: bool,
    lp_warp_inverse: bool,
    lp_w1: float,
    lp_w2: float,
    lp_w3: float,
    lp_w4: float,
):
    cap = cv2.VideoCapture(str(input_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open input video: {input_path}")

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    ok, prev = cap.read()
    if not ok:
        raise RuntimeError("Cannot read first frame")
    prev_gray = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)

    transforms = []
    feature_counts = []
    detected_counts = []
    after_reject_counts = []
    foreground_rejected_counts = []
    inlier_counts = []
    inlier_ratios = []
    fallback_reasons = []
    valid_mask = []
    estimate_times_ms = []
    last_good_transform = np.array([0.0, 0.0, 0.0], dtype=np.float32)

    while True:
        ok, curr = cap.read()
        if not ok:
            break
        curr_gray = cv2.cvtColor(curr, cv2.COLOR_BGR2GRAY)

        t0 = time.perf_counter()
        transform, details = estimate_transform(
            prev_gray,
            curr_gray,
            estimate_scale,
            feature_grid_size,
            foreground_reject_threshold,
            min_inliers,
            min_inlier_ratio,
            ransac_reproj_threshold,
        )
        t1 = time.perf_counter()

        fallback_reason = details["fallback_reason"]
        if transform is None:
            if fallback_mode == "last_good":
                transform = last_good_transform.copy()
            else:
                transform = np.array([0.0, 0.0, 0.0], dtype=np.float32)
            valid = False
        else:
            last_good_transform = transform.copy()
            valid = True

        transforms.append(transform)
        feature_counts.append(details["tracked_features"])
        detected_counts.append(details["detected_features"])
        after_reject_counts.append(details["after_foreground_reject"])
        foreground_rejected_counts.append(details["foreground_rejected"])
        inlier_counts.append(details["inliers"])
        inlier_ratios.append(details["inlier_ratio"])
        fallback_reasons.append(fallback_reason)
        valid_mask.append(valid)
        estimate_times_ms.append((t1 - t0) * 1000.0)

        prev_gray = curr_gray

    cap.release()

    if not transforms:
        raise RuntimeError("Input video has too few frames")

    transforms = np.array(transforms, dtype=np.float32)
    valid_mask_np = np.array(valid_mask, dtype=bool)

    confidence_valid_mask, confidence_repair_frames, confidence_repair_new_invalid = confidence_repair_valid_mask(
        transforms,
        valid_mask_np,
        after_reject_counts,
        inlier_counts,
        inlier_ratios,
        width,
        height,
        confidence_min_after_reject,
        confidence_min_inliers,
        confidence_min_inlier_ratio,
        confidence_jump_limit_px,
        confidence_jump_limit_deg,
        confidence_dilate_frames,
    )

    if fallback_mode == "interpolate":
        transforms_for_smoothing = interpolate_invalid_transforms(transforms, confidence_valid_mask)
    else:
        transforms_for_smoothing = transforms
    transforms_limited, first_order_clamps, accel_clamps = limit_transform_sequence(
        transforms_for_smoothing,
        width,
        max_translation_ratio,
        max_rotation_deg,
        accel_limit_px,
        accel_limit_deg,
    )

    trajectory = np.cumsum(transforms_limited, axis=0)
    smoothed_trajectory, constrained_box_clamps, constrained_accel_clamps = smooth_trajectory_with_constraints(
        trajectory,
        smoothing_radius,
        smoothing_method,
        gaussian_stdev,
        width,
        height,
        crop_ratio,
        constrained_margin_scale,
        constrained_accel_limit_px,
        constrained_accel_limit_deg,
        constrained_projection_iters,
    )
    strength = float(np.clip(stabilization_strength, 0.0, 1.0))
    difference = (smoothed_trajectory - trajectory) * strength
    difference = relax_correction_after_invalid(difference, valid_mask_np, fallback_recovery_alpha, fallback_recovery_frames)
    difference, correction_clamps = clamp_correction_to_crop_margin(difference, width, height, crop_ratio, correction_limit_ratio)
    transforms_smooth = transforms_limited + difference
    transforms_smooth, final_first_order_clamps, final_accel_clamps = limit_transform_sequence(
        transforms_smooth,
        width,
        max_translation_ratio,
        max_rotation_deg,
        accel_limit_px,
        accel_limit_deg,
    )
    zoom_curve, required_zoom_curve = compute_dynamic_zoom_curve(
        transforms_smooth,
        width,
        height,
        dynamic_zoom,
        zoom_rolling_window,
        zoom_gaussian_radius,
        zoom_gaussian_stdev,
        zoom_rate_limit,
        min_zoom,
        max_zoom,
        zoom_hysteresis,
    )
    transforms_smooth, inclusion_relaxed_frames, max_inclusion_relax_alpha, required_relax_alpha, applied_relax_alpha = apply_smoothed_inclusion_relaxation(
        transforms_smooth,
        width,
        height,
        inclusion_trim_ratio,
        zoom_curve,
        inclusion_alpha_release_tau,
        inclusion_alpha_release_rate,
        inclusion_alpha_attack_rate,
    )
    transforms_before_final_limit = np.array(transforms_smooth, copy=True, dtype=np.float32)
    transforms_smooth, final_only_accel_clamps, final_only_jerk_clamps = limit_final_derivatives(
        transforms_smooth,
        final_accel_limit_px,
        final_accel_limit_deg,
        final_jerk_limit_px,
        final_jerk_limit_deg,
        final_accel_blend,
        final_jerk_blend,
    )
    transforms_smooth, spike_repair_frames, spike_repair_max_second = repair_local_transform_spikes(
        transforms_smooth,
        width,
        height,
        spike_repair_limit_px,
        spike_repair_limit_deg,
        spike_repair_top_percent,
        spike_repair_blend,
        spike_repair_iterations,
    )
    transforms_smooth, mask_safety_rollback_frames, mask_safety_avg_beta, mask_safety_min_beta, mask_safety_worst_checked_invalid = apply_mask_safety_rollback(
        transforms_before_final_limit,
        transforms_smooth,
        width,
        height,
        crop_ratio,
        border_scale,
        zoom_curve,
        mask_safety_max_invalid,
    )

    intent_proximity_frames = 0
    intent_proximity_avg_gap = 0.0
    intent_proximity_max_gap = 0.0
    warp_mats = None
    if smoothing_method in {"lp_rigid", "lp_affine"}:
        # The LP optimizer solves 4-DOF similarity matrices S[t]=[[a,b,dx],[-b,a,dy]].
        # Converting them to our legacy (dx,dy,angle) representation would discard
        # the scale encoded in a/b. Keep the original matrices for warp and mask
        # generation; transforms_smooth is kept only for CSV diagnostics.
        lp_input_transforms = np.empty_like(trajectory, dtype=np.float32)
        lp_input_transforms[0] = trajectory[0]
        if len(trajectory) > 1:
            lp_input_transforms[1:] = trajectory[1:] - trajectory[:-1]
        lp_solver = solve_lp_motion_stabilizer_affine if smoothing_method == "lp_affine" else solve_lp_motion_stabilizer_rigid
        lp_mats = lp_solver(
            lp_input_transforms,
            width,
            height,
            trim_ratio=(
                float(lp_trim_ratio)
                if float(lp_trim_ratio) > 0.0
                else (1.0 - float(crop_ratio)) * 0.5 * float(constrained_margin_scale)
            ),
            w1=lp_w1,
            w2=lp_w2,
            w3=lp_w3,
            w4=lp_w4,
            anchor_first=lp_anchor_first,
        )
        identity = np.eye(3, dtype=np.float32)
        lp_candidate_mats = [identity + strength * (mat.astype(np.float32) - identity) for mat in lp_mats[1:]]
        lp_candidate_mats, intent_proximity_frames, intent_proximity_avg_gap, intent_proximity_max_gap = apply_intent_proximity_to_mats(
            lp_candidate_mats,
            transforms_limited,
            trajectory,
            width,
            height,
            intent_proximity_radius if intent_proximity_radius > 0 else smoothing_radius,
            intent_proximity_stdev,
            intent_proximity_band_px,
            intent_proximity_blend,
            strength,
        )
        if lp_warp_inverse:
            lp_candidate_mats = [np.linalg.inv(mat).astype(np.float32) for mat in lp_candidate_mats]
        lp_output_mats, mask_safety_rollback_frames, mask_safety_avg_beta, mask_safety_min_beta, mask_safety_worst_checked_invalid = apply_mask_safety_rollback_mats(
            lp_candidate_mats,
            width,
            height,
            crop_ratio,
            border_scale,
            zoom_curve,
            mask_safety_max_invalid,
        )
        if final_accel_limit_px > 0 or final_accel_limit_deg > 0 or final_jerk_limit_px > 0 or final_jerk_limit_deg > 0:
            lp_output_poses = np.array([affine_3x3_to_transform(mat) for mat in lp_output_mats], dtype=np.float32)
            lp_limited_poses, lp_accel_clamps, lp_jerk_clamps = limit_final_derivatives(
                lp_output_poses,
                final_accel_limit_px,
                final_accel_limit_deg,
                final_jerk_limit_px,
                final_jerk_limit_deg,
                final_accel_blend,
                final_jerk_blend,
            )
            final_only_accel_clamps += lp_accel_clamps
            final_only_jerk_clamps += lp_jerk_clamps
            lp_limited_mats = [transform_to_affine_3x3(pose) for pose in lp_limited_poses]
            lp_output_mats, rb2, avg_beta2, min_beta2, worst_invalid2 = apply_mask_safety_rollback_mats(
                lp_limited_mats,
                width,
                height,
                crop_ratio,
                border_scale,
                zoom_curve,
                mask_safety_max_invalid,
            )
            mask_safety_rollback_frames += rb2
            mask_safety_avg_beta = min(mask_safety_avg_beta, avg_beta2)
            mask_safety_min_beta = min(mask_safety_min_beta, min_beta2)
            mask_safety_worst_checked_invalid = max(mask_safety_worst_checked_invalid, worst_invalid2)
        warp_mats = [mat[:2, :].astype(np.float32) for mat in lp_output_mats]
        transforms_smooth = np.array([affine_3x3_to_transform(mat) for mat in lp_output_mats], dtype=np.float32)

    crop_interp = interpolation_from_name(crop_interpolation)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"Cannot open output video: {output_path}")

    cap = cv2.VideoCapture(str(input_path))
    ok, frame = cap.read()
    if not ok:
        raise RuntimeError("Cannot re-read first frame")
    first_zoom = float(zoom_curve[0]) if len(zoom_curve) else 1.0
    first_frame = fix_border(frame, border_scale * first_zoom)
    valid_mask_frame = np.full((height, width), 255, dtype=np.uint8)
    first_valid_mask = scale_mask(valid_mask_frame, border_scale * first_zoom)
    first_output = fixed_center_crop_and_resize(first_frame, crop_ratio, crop_interp)
    writer.write(apply_unsharp_mask(first_output, sharpen_strength, sharpen_sigma))

    warp_times_ms = []
    black_ratios = []
    invalid_mask_ratios = []
    frames_written = 1
    black_ratios.append(black_pixel_ratio(fixed_center_crop_and_resize(first_frame, crop_ratio, crop_interp)))
    invalid_mask_ratios.append(invalid_mask_ratio(fixed_center_crop_and_resize(first_valid_mask, crop_ratio)))
    vpi_warper = None if warp_backend == "opencv_cpu" else VPIWarpPerspective(warp_backend)

    for i, transform in enumerate(transforms_smooth):
        ok, frame = cap.read()
        if not ok:
            break

        if warp_mats is not None and i < len(warp_mats):
            mat = warp_mats[i]
        else:
            dx, dy, da = transform
            mat = np.array(
                [
                    [math.cos(da), -math.sin(da), dx],
                    [math.sin(da), math.cos(da), dy],
                ],
                dtype=np.float32,
            )

        t0 = time.perf_counter()
        if vpi_warper is None:
            stabilized = cv2.warpAffine(frame, mat, (width, height), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        else:
            stabilized = vpi_warper.warp_affine(frame, mat)
        warped_valid_mask = cv2.warpAffine(valid_mask_frame, mat, (width, height), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        stabilized = fix_border(stabilized, border_scale * float(zoom_curve[i]))
        warped_valid_mask = scale_mask(warped_valid_mask, border_scale * float(zoom_curve[i]))
        stabilized = fixed_center_crop_and_resize(stabilized, crop_ratio, crop_interp)
        warped_valid_mask = fixed_center_crop_and_resize(warped_valid_mask, crop_ratio)
        output_frame = apply_unsharp_mask(stabilized, sharpen_strength, sharpen_sigma)
        t1 = time.perf_counter()

        writer.write(output_frame)
        warp_times_ms.append((t1 - t0) * 1000.0)
        black_ratios.append(black_pixel_ratio(stabilized))
        invalid_mask_ratios.append(invalid_mask_ratio(warped_valid_mask))
        frames_written += 1

    cap.release()
    writer.release()

    with metrics_path.open("w", newline="", encoding="utf-8") as f:
        csv_writer = csv.writer(f)
        csv_writer.writerow([
            "frame_index",
            "detected_features",
            "tracked_features",
            "after_foreground_reject",
            "foreground_rejected",
            "inliers",
            "inlier_ratio",
            "fallback_reason",
            "estimate_ms",
            "warp_ms",
            "dx",
            "dy",
            "da_rad",
            "raw_dx",
            "raw_dy",
            "raw_da_rad",
            "valid_transform",
            "confidence_repaired",
            "required_zoom",
            "dynamic_zoom",
            "required_relax_alpha",
            "applied_relax_alpha",
            "invalid_mask_ratio",
        ])
        for i, transform in enumerate(transforms_smooth):
            warp_ms = warp_times_ms[i] if i < len(warp_times_ms) else ""
            csv_writer.writerow([
                i + 1,
                detected_counts[i],
                feature_counts[i],
                after_reject_counts[i],
                foreground_rejected_counts[i],
                inlier_counts[i],
                f"{inlier_ratios[i]:.6f}",
                fallback_reasons[i],
                f"{estimate_times_ms[i]:.3f}",
                f"{warp_ms:.3f}" if warp_ms != "" else "",
                f"{transform[0]:.6f}",
                f"{transform[1]:.6f}",
                f"{transform[2]:.6f}",
                f"{transforms[i][0]:.6f}",
                f"{transforms[i][1]:.6f}",
                f"{transforms[i][2]:.6f}",
                int(valid_mask_np[i]),
                int(valid_mask_np[i] and not confidence_valid_mask[i]),
                f"{required_zoom_curve[i]:.6f}",
                f"{zoom_curve[i]:.6f}",
                f"{required_relax_alpha[i]:.6f}",
                f"{applied_relax_alpha[i]:.6f}",
                f"{invalid_mask_ratios[i + 1]:.6f}" if i + 1 < len(invalid_mask_ratios) else "",
            ])

    summary = {
        "input": str(input_path),
        "output": str(output_path),
        "metrics": str(metrics_path),
        "width": width,
        "height": height,
        "fps": fps,
        "input_frame_count": frame_count,
        "frames_written": frames_written,
        "avg_estimate_ms": float(np.mean(estimate_times_ms)),
        "avg_warp_ms": float(np.mean(warp_times_ms)) if warp_times_ms else 0.0,
        "avg_detected_features": float(np.mean(detected_counts)) if detected_counts else 0.0,
        "avg_tracked_features": float(np.mean(feature_counts)) if feature_counts else 0.0,
        "avg_after_foreground_reject": float(np.mean(after_reject_counts)) if after_reject_counts else 0.0,
        "avg_foreground_rejected": float(np.mean(foreground_rejected_counts)) if foreground_rejected_counts else 0.0,
        "avg_inliers": float(np.mean(inlier_counts)) if inlier_counts else 0.0,
        "avg_inlier_ratio": float(np.mean(inlier_ratios)) if inlier_ratios else 0.0,
        "fallback_frames": int(sum(1 for reason in fallback_reasons if reason)),
        "invalid_transform_frames": int(np.sum(~valid_mask_np)),
        "confidence_repair_frames": confidence_repair_frames,
        "confidence_repair_new_invalid": confidence_repair_new_invalid,
        "first_order_transform_clamps": first_order_clamps,
        "accel_transform_clamps": accel_clamps,
        "final_first_order_transform_clamps": final_first_order_clamps,
        "final_accel_transform_clamps": final_accel_clamps,
        "final_only_accel_clamps": final_only_accel_clamps,
        "final_only_jerk_clamps": final_only_jerk_clamps,
        "spike_repair_frames": spike_repair_frames,
        "spike_repair_max_second": spike_repair_max_second,
        "mask_safety_rollback_frames": mask_safety_rollback_frames,
        "mask_safety_avg_beta": mask_safety_avg_beta,
        "mask_safety_min_beta": mask_safety_min_beta,
        "mask_safety_worst_checked_invalid": mask_safety_worst_checked_invalid,
        "correction_clamps": correction_clamps,
        "inclusion_relaxed_frames": inclusion_relaxed_frames,
        "constrained_box_clamps": constrained_box_clamps,
        "constrained_accel_clamps": constrained_accel_clamps,
        "max_inclusion_relax_alpha": max_inclusion_relax_alpha,
        "max_required_relax_alpha": float(np.max(required_relax_alpha)) if len(required_relax_alpha) else 0.0,
        "avg_required_relax_alpha": float(np.mean(required_relax_alpha)) if len(required_relax_alpha) else 0.0,
        "max_applied_relax_alpha": float(np.max(applied_relax_alpha)) if len(applied_relax_alpha) else 0.0,
        "avg_applied_relax_alpha": float(np.mean(applied_relax_alpha)) if len(applied_relax_alpha) else 0.0,
        "max_required_zoom": float(np.max(required_zoom_curve)) if len(required_zoom_curve) else 1.0,
        "avg_required_zoom": float(np.mean(required_zoom_curve)) if len(required_zoom_curve) else 1.0,
        "max_dynamic_zoom": float(np.max(zoom_curve)) if len(zoom_curve) else 1.0,
        "avg_dynamic_zoom": float(np.mean(zoom_curve)) if len(zoom_curve) else 1.0,
        "max_black_pixel_ratio": float(np.max(black_ratios)) if black_ratios else 0.0,
        "avg_black_pixel_ratio": float(np.mean(black_ratios)) if black_ratios else 0.0,
        "p95_invalid_mask_ratio": float(np.percentile(invalid_mask_ratios, 95)) if invalid_mask_ratios else 0.0,
        "max_invalid_mask_ratio": float(np.max(invalid_mask_ratios)) if invalid_mask_ratios else 0.0,
        "avg_invalid_mask_ratio": float(np.mean(invalid_mask_ratios)) if invalid_mask_ratios else 0.0,
        "smoothing_radius": smoothing_radius,
        "smoothing_method": smoothing_method,
        "gaussian_stdev": gaussian_stdev,
        "border_scale": border_scale,
        "crop_ratio": crop_ratio,
        "crop_interpolation": crop_interpolation,
        "sharpen_strength": sharpen_strength,
        "sharpen_sigma": sharpen_sigma,
        "warp_backend": warp_backend,
        "estimate_scale": estimate_scale,
        "feature_grid_size": feature_grid_size,
        "foreground_reject_threshold": foreground_reject_threshold,
        "min_inliers": min_inliers,
        "min_inlier_ratio": min_inlier_ratio,
        "ransac_reproj_threshold": ransac_reproj_threshold,
        "fallback_mode": fallback_mode,
        "max_translation_ratio": max_translation_ratio,
        "max_rotation_deg": max_rotation_deg,
        "accel_limit_px": accel_limit_px,
        "accel_limit_deg": accel_limit_deg,
        "fallback_recovery_alpha": fallback_recovery_alpha,
        "fallback_recovery_frames": fallback_recovery_frames,
        "correction_limit_ratio": correction_limit_ratio,
        "inclusion_trim_ratio": inclusion_trim_ratio,
        "dynamic_zoom": dynamic_zoom,
        "zoom_rolling_window": zoom_rolling_window,
        "zoom_gaussian_radius": zoom_gaussian_radius,
        "zoom_gaussian_stdev": zoom_gaussian_stdev,
        "zoom_rate_limit": zoom_rate_limit,
        "min_zoom": min_zoom,
        "max_zoom": max_zoom,
        "zoom_hysteresis": zoom_hysteresis,
        "constrained_margin_scale": constrained_margin_scale,
        "lp_trim_ratio": lp_trim_ratio,
        "constrained_accel_limit_px": constrained_accel_limit_px,
        "constrained_accel_limit_deg": constrained_accel_limit_deg,
        "constrained_projection_iters": constrained_projection_iters,
        "inclusion_alpha_release_tau": inclusion_alpha_release_tau,
        "inclusion_alpha_release_rate": inclusion_alpha_release_rate,
        "inclusion_alpha_attack_rate": inclusion_alpha_attack_rate,
        "final_accel_limit_px": final_accel_limit_px,
        "final_accel_limit_deg": final_accel_limit_deg,
        "final_jerk_limit_px": final_jerk_limit_px,
        "final_jerk_limit_deg": final_jerk_limit_deg,
        "final_accel_blend": final_accel_blend,
        "final_jerk_blend": final_jerk_blend,
        "mask_safety_max_invalid": mask_safety_max_invalid,
        "confidence_min_after_reject": confidence_min_after_reject,
        "confidence_min_inliers": confidence_min_inliers,
        "confidence_min_inlier_ratio": confidence_min_inlier_ratio,
        "confidence_jump_limit_px": confidence_jump_limit_px,
        "confidence_jump_limit_deg": confidence_jump_limit_deg,
        "confidence_dilate_frames": confidence_dilate_frames,
        "spike_repair_limit_px": spike_repair_limit_px,
        "spike_repair_limit_deg": spike_repair_limit_deg,
        "spike_repair_top_percent": spike_repair_top_percent,
        "spike_repair_blend": spike_repair_blend,
        "spike_repair_iterations": spike_repair_iterations,
        "intent_proximity_blend": intent_proximity_blend,
        "intent_proximity_band_px": intent_proximity_band_px,
        "intent_proximity_radius": intent_proximity_radius,
        "intent_proximity_stdev": intent_proximity_stdev,
        "intent_proximity_frames": intent_proximity_frames,
        "intent_proximity_avg_gap": intent_proximity_avg_gap,
        "intent_proximity_max_gap": intent_proximity_max_gap,
        "stabilization_strength": strength,
        "lp_anchor_first": lp_anchor_first,
        "lp_warp_inverse": lp_warp_inverse,
        "lp_w1": lp_w1,
        "lp_w2": lp_w2,
        "lp_w3": lp_w3,
        "lp_w4": lp_w4,
    }
    return summary


def write_summary_csv(summary_path: Path, summary: dict, total_wall_time_s: float):
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    row = dict(summary)
    row["total_wall_time_s"] = f"{total_wall_time_s:.3f}"
    with summary_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        writer.writeheader()
        writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(description="CPU baseline video stabilization with OpenCV.")
    parser.add_argument("--input", required=True, type=Path, help="Input shaky video path")
    parser.add_argument("--output", required=True, type=Path, help="Output stabilized video path")
    parser.add_argument("--metrics", required=True, type=Path, help="Output per-frame CSV metrics path")
    parser.add_argument("--smoothing-radius", type=int, default=45, help="Trajectory smoothing radius")
    parser.add_argument("--smoothing-method", choices=["moving_average", "gaussian", "constrained_box", "constrained_gaussian", "constrained_qp", "constrained_qp_l1", "lp_rigid", "lp_affine"], default="gaussian", help="Trajectory smoothing method")
    parser.add_argument("--gaussian-stdev", type=float, default=0.0, help="Gaussian smoothing stdev; <=0 uses radius/3")
    parser.add_argument("--border-scale", type=float, default=1.00, help="Extra scale before final fixed crop")
    parser.add_argument("--crop-ratio", type=float, default=0.80, help="Fixed center crop ratio, then resize back to original size")
    parser.add_argument("--crop-interpolation", choices=["linear", "cubic", "lanczos", "area"], default="linear", help="Interpolation used when resizing the fixed crop back to output size")
    parser.add_argument("--sharpen-strength", type=float, default=0.0, help="Optional unsharp-mask strength applied to output frames; 0 disables")
    parser.add_argument("--sharpen-sigma", type=float, default=1.0, help="Gaussian sigma for optional output unsharp mask")
    parser.add_argument("--estimate-scale", type=float, default=1.0, help="Scale factor for motion estimation; final warp still runs at full resolution")
    parser.add_argument("--feature-grid-size", type=int, default=12, help="Grid size for spatially distributed feature selection; <=1 disables grid selection")
    parser.add_argument("--foreground-reject-threshold", type=float, default=10.0, help="Reject tracked points whose dx/dy deviates from dominant motion by more than this many original-resolution pixels")
    parser.add_argument("--min-inliers", type=int, default=12, help="Minimum RANSAC inlier count before accepting frame motion")
    parser.add_argument("--min-inlier-ratio", type=float, default=0.10, help="Minimum RANSAC inlier ratio before accepting frame motion")
    parser.add_argument("--ransac-reproj-threshold", type=float, default=3.0, help="RANSAC reprojection threshold in estimation-resolution pixels")
    parser.add_argument("--fallback-mode", choices=["interpolate", "last_good", "identity"], default="interpolate", help="Motion fallback when tracking/RANSAC confidence is low")
    parser.add_argument("--max-translation-ratio", type=float, default=0.05, help="Per-frame dx/dy clamp as a ratio of frame width; <=0 disables")
    parser.add_argument("--max-rotation-deg", type=float, default=2.0, help="Per-frame rotation clamp in degrees; <=0 disables")
    parser.add_argument("--accel-limit-px", type=float, default=10.0, help="Second-difference clamp for dx/dy in px/frame^2; <=0 disables")
    parser.add_argument("--accel-limit-deg", type=float, default=0.5, help="Second-difference clamp for da in deg/frame^2; <=0 disables")
    parser.add_argument("--fallback-recovery-alpha", type=float, default=0.3, help="Correction relaxation alpha after an invalid-transform segment; use 0 to disable")
    parser.add_argument("--fallback-recovery-frames", type=int, default=5, help="Number of frames to relax correction after fallback recovery")
    parser.add_argument("--correction-limit-ratio", type=float, default=0.0, help="Limit correction dx/dy to crop margin times this ratio; <=0 disables")
    parser.add_argument("--inclusion-trim-ratio", type=float, default=0.12, help="Relax smoothed correction toward identity until it covers this center safe-region margin; <=0 disables")
    parser.add_argument("--dynamic-zoom", action="store_true", help="Enable causal dynamic zoom based on per-frame required trim ratio")
    parser.add_argument("--zoom-rolling-window", type=int, default=15, help="Causal rolling-max window for dynamic zoom")
    parser.add_argument("--zoom-gaussian-radius", type=int, default=24, help="Gaussian smoothing radius for dynamic zoom curve")
    parser.add_argument("--zoom-gaussian-stdev", type=float, default=8.0, help="Gaussian stdev for dynamic zoom curve")
    parser.add_argument("--zoom-rate-limit", type=float, default=0.005, help="Maximum dynamic zoom change per frame")
    parser.add_argument("--min-zoom", type=float, default=1.05, help="Minimum dynamic zoom when enabled")
    parser.add_argument("--max-zoom", type=float, default=1.15, help="Maximum dynamic zoom when enabled")
    parser.add_argument("--zoom-hysteresis", type=float, default=0.03, help="Dynamic zoom deadband to reduce breathing; <=0 disables")
    parser.add_argument("--constrained-margin-scale", type=float, default=0.90, help="Scale of fixed-crop side margin used by constrained_* smoothers")
    parser.add_argument("--lp-trim-ratio", type=float, default=0.0, help="Override LP corner/FOV trim ratio; <=0 derives it from crop-ratio and constrained-margin-scale")
    parser.add_argument("--constrained-accel-limit-px", type=float, default=0.0, help="Pose acceleration cap in px/frame^2 for constrained_* smoothers; <=0 disables")
    parser.add_argument("--constrained-accel-limit-deg", type=float, default=0.0, help="Pose acceleration cap in deg/frame^2 for constrained_* smoothers; <=0 disables")
    parser.add_argument("--constrained-projection-iters", type=int, default=8, help="Projection passes for constrained_* smoothers")
    parser.add_argument("--inclusion-alpha-release-tau", type=float, default=0.0, help="Slowly release inclusion relaxation alpha over this many frames; <=0 disables")
    parser.add_argument("--inclusion-alpha-release-rate", type=float, default=0.0, help="Maximum per-frame decrease of inclusion relaxation alpha; <=0 disables")
    parser.add_argument("--inclusion-alpha-attack-rate", type=float, default=0.0, help="Maximum per-frame increase of inclusion relaxation alpha; <=0 disables")
    parser.add_argument("--final-accel-limit-px", type=float, default=0.0, help="Final-only second-difference limit for dx/dy after inclusion relaxation; <=0 disables")
    parser.add_argument("--final-accel-limit-deg", type=float, default=0.0, help="Final-only second-difference limit for rotation after inclusion relaxation; <=0 disables")
    parser.add_argument("--final-jerk-limit-px", type=float, default=0.0, help="Final-only third-difference limit for dx/dy after inclusion relaxation; <=0 disables")
    parser.add_argument("--final-jerk-limit-deg", type=float, default=0.0, help="Final-only third-difference limit for rotation after inclusion relaxation; <=0 disables")
    parser.add_argument("--final-accel-blend", type=float, default=1.0, help="Soft projection strength for final accel limiter in [0,1]; 1 means hard clamp")
    parser.add_argument("--final-jerk-blend", type=float, default=1.0, help="Soft projection strength for final jerk limiter in [0,1]; 1 means hard clamp")
    parser.add_argument("--mask-safety-max-invalid", type=float, default=0.0, help="Rollback final-smoothed frames if valid-mask invalid ratio exceeds this threshold; <=0 disables")
    parser.add_argument("--confidence-min-after-reject", type=int, default=0, help="Treat formally valid motion as missing if post-foreground feature count is below this; <=0 disables")
    parser.add_argument("--confidence-min-inliers", type=int, default=0, help="Treat formally valid motion as missing if RANSAC inliers are below this; <=0 disables")
    parser.add_argument("--confidence-min-inlier-ratio", type=float, default=0.0, help="Treat formally valid motion as missing if RANSAC inlier ratio is below this; <=0 disables")
    parser.add_argument("--confidence-jump-limit-px", type=float, default=0.0, help="Treat raw motion estimates around jumps above this normalized px magnitude as missing; <=0 disables")
    parser.add_argument("--confidence-jump-limit-deg", type=float, default=0.0, help="Treat raw motion estimates around rotation jumps above this degree threshold as missing; <=0 disables")
    parser.add_argument("--confidence-dilate-frames", type=int, default=0, help="Expand confidence-repair gaps by this many neighboring frames")
    parser.add_argument("--spike-repair-limit-px", type=float, default=0.0, help="Local final-warp spike repair threshold in normalized px; <=0 disables threshold mode")
    parser.add_argument("--spike-repair-limit-deg", type=float, default=0.0, help="Local final-warp spike repair rotation threshold in degrees; <=0 disables angle threshold")
    parser.add_argument("--spike-repair-top-percent", type=float, default=0.0, help="Additionally repair this top percent of final-warp second-difference jumps; <=0 disables")
    parser.add_argument("--spike-repair-blend", type=float, default=0.0, help="Local spike repair blend toward neighbor midpoint in [0,1]; <=0 disables repair")
    parser.add_argument("--spike-repair-iterations", type=int, default=0, help="Number of local spike repair iterations; <=0 disables repair")
    parser.add_argument("--intent-proximity-blend", type=float, default=0.0, help="Blend LP warp toward low-pass intent correction when it exceeds the intent band; <=0 disables")
    parser.add_argument("--intent-proximity-band-px", type=float, default=12.0, help="Translation-equivalent LP-vs-intent gap allowed before intent proximity is applied")
    parser.add_argument("--intent-proximity-radius", type=int, default=30, help="Gaussian radius for low-pass intent trajectory; <=0 reuses smoothing-radius")
    parser.add_argument("--intent-proximity-stdev", type=float, default=0.0, help="Gaussian stdev for low-pass intent; <=0 uses radius/3")
    parser.add_argument("--stabilization-strength", type=float, default=1.0, help="Blend final stabilization toward identity in [0,1]; lower values reduce over-correction")
    parser.add_argument("--lp-anchor-first", action="store_true", help="Anchor the first LP stabilization matrix to identity to remove gauge freedom")
    parser.add_argument("--lp-warp-inverse", action="store_true", help="Use inverse LP matrices for final warp; diagnostic for motion convention checks")
    parser.add_argument("--lp-w1", type=float, default=1.0, help="LP smoother weight for first-order stabilization-motion difference")
    parser.add_argument("--lp-w2", type=float, default=10.0, help="LP smoother weight for second-order stabilization-motion difference")
    parser.add_argument("--lp-w3", type=float, default=100.0, help="LP smoother weight for third-order stabilization-motion difference")
    parser.add_argument("--lp-w4", type=float, default=100.0, help="LP smoother extra weight for non-translation affine/similarity components")
    parser.add_argument("--summary", type=Path, default=None, help="Optional one-row summary CSV path")
    parser.add_argument(
        "--warp-backend",
        choices=["opencv_cpu", "vpi_cpu", "vpi_cuda", "vpi_vic"],
        default="opencv_cpu",
        help="Backend for the per-frame geometric warp stage",
    )
    args = parser.parse_args()

    total_t0 = time.perf_counter()
    summary = stabilize_video(
        args.input,
        args.output,
        args.metrics,
        args.smoothing_radius,
        args.smoothing_method,
        args.gaussian_stdev,
        args.border_scale,
        args.crop_ratio,
        args.crop_interpolation,
        args.sharpen_strength,
        args.sharpen_sigma,
        args.warp_backend,
        args.estimate_scale,
        args.feature_grid_size,
        args.foreground_reject_threshold,
        args.min_inliers,
        args.min_inlier_ratio,
        args.ransac_reproj_threshold,
        args.fallback_mode,
        args.max_translation_ratio,
        args.max_rotation_deg,
        args.accel_limit_px,
        args.accel_limit_deg,
        args.fallback_recovery_alpha,
        args.fallback_recovery_frames,
        args.correction_limit_ratio,
        args.inclusion_trim_ratio,
        args.dynamic_zoom,
        args.zoom_rolling_window,
        args.zoom_gaussian_radius,
        args.zoom_gaussian_stdev,
        args.zoom_rate_limit,
        args.min_zoom,
        args.max_zoom,
        args.zoom_hysteresis,
        args.constrained_margin_scale,
        args.lp_trim_ratio,
        args.constrained_accel_limit_px,
        args.constrained_accel_limit_deg,
        args.constrained_projection_iters,
        args.inclusion_alpha_release_tau,
        args.inclusion_alpha_release_rate,
        args.inclusion_alpha_attack_rate,
        args.final_accel_limit_px,
        args.final_accel_limit_deg,
        args.final_jerk_limit_px,
        args.final_jerk_limit_deg,
        args.final_accel_blend,
        args.final_jerk_blend,
        args.mask_safety_max_invalid,
        args.confidence_min_after_reject,
        args.confidence_min_inliers,
        args.confidence_min_inlier_ratio,
        args.confidence_jump_limit_px,
        args.confidence_jump_limit_deg,
        args.confidence_dilate_frames,
        args.spike_repair_limit_px,
        args.spike_repair_limit_deg,
        args.spike_repair_top_percent,
        args.spike_repair_blend,
        args.spike_repair_iterations,
        args.intent_proximity_blend,
        args.intent_proximity_band_px,
        args.intent_proximity_radius,
        args.intent_proximity_stdev,
        args.stabilization_strength,
        args.lp_anchor_first,
        args.lp_warp_inverse,
        args.lp_w1,
        args.lp_w2,
        args.lp_w3,
        args.lp_w4,
    )
    total_t1 = time.perf_counter()
    total_wall_time_s = total_t1 - total_t0

    if args.summary is not None:
        write_summary_csv(args.summary, summary, total_wall_time_s)

    print("CPU stabilization baseline finished")
    for key, value in summary.items():
        print(f"{key}: {value}")
    print(f"total_wall_time_s: {total_wall_time_s:.3f}")
    if args.summary is not None:
        print(f"summary: {args.summary}")


if __name__ == "__main__":
    main()
