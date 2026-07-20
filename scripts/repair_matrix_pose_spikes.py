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


def pose_d2_magnitude(pose: np.ndarray, angle_scale: float) -> np.ndarray:
    if len(pose) < 3:
        return np.array([], dtype=np.float64)
    d2 = pose[2:] - 2.0 * pose[1:-1] + pose[:-2]
    return np.sqrt(d2[:, 0] * d2[:, 0] + d2[:, 1] * d2[:, 1] + (d2[:, 2] * angle_scale) * (d2[:, 2] * angle_scale))


def repair_spikes(
    pose: np.ndarray,
    angle_scale: float,
    threshold_px: float,
    top_percent: float,
    blend: float,
    radius: int,
    iterations: int,
) -> tuple[np.ndarray, list[dict[str, object]]]:
    out = pose.copy()
    log_rows: list[dict[str, object]] = []
    n = len(out)
    if n < 3:
        return out, log_rows
    blend = float(np.clip(blend, 0.0, 1.0))
    radius = max(1, int(radius))
    for iteration in range(max(1, int(iterations))):
        mag = pose_d2_magnitude(out, angle_scale)
        if len(mag) == 0:
            break
        active = np.zeros(n, dtype=bool)
        if threshold_px > 0:
            for idx in np.flatnonzero(mag > threshold_px):
                active[idx + 1] = True
        if top_percent > 0:
            top_n = max(1, int(math.ceil(len(mag) * float(top_percent) * 0.01)))
            for idx in np.argsort(mag)[-top_n:]:
                active[idx + 1] = True
        active[:radius] = False
        active[n - radius :] = False
        indices = np.flatnonzero(active)
        if len(indices) == 0:
            break
        before = out.copy()
        for frame in indices:
            lo = max(0, frame - radius)
            hi = min(n, frame + radius + 1)
            neighbors = np.concatenate([before[lo:frame], before[frame + 1 : hi]], axis=0)
            if len(neighbors) == 0:
                continue
            target = np.mean(neighbors, axis=0)
            out[frame] = (1.0 - blend) * before[frame] + blend * target
            log_rows.append(
                {
                    "iteration": iteration,
                    "frame": int(frame),
                    "pre_d2_mag": f"{float(mag[frame - 1]):.9f}",
                }
            )
    return out, log_rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Local D2/D3-oriented matrix pose spike repair for diagnostic EIS candidates.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repair-log", type=Path, default=None)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=360)
    parser.add_argument("--threshold-px", type=float, default=6.0)
    parser.add_argument("--top-percent", type=float, default=0.0)
    parser.add_argument("--blend", type=float, default=0.7)
    parser.add_argument("--radius", type=int, default=2)
    parser.add_argument("--iterations", type=int, default=2)
    parser.add_argument("--preserve-scale", action="store_true")
    parser.add_argument("--first-frame-copy-next", action="store_true")
    args = parser.parse_args()

    rows = read_rows(args.input)
    mats = [row_to_matrix(row) for row in rows]
    params = np.array([decompose_similarity(mat) for mat in mats], dtype=np.float64)
    scales = params[:, 0]
    angles = np.unwrap(params[:, 1])
    pose = np.stack([params[:, 2], params[:, 3], angles], axis=1)
    half_diag = max(1.0, 0.5 * math.hypot(float(args.width), float(args.height)))
    repaired, log_rows = repair_spikes(
        pose,
        half_diag,
        args.threshold_px,
        args.top_percent,
        args.blend,
        args.radius,
        args.iterations,
    )

    if args.first_frame_copy_next and len(repaired) > 1:
        repaired[0] = repaired[1]
        scales[0] = scales[1]
    out_rows = []
    for row, scale, cur in zip(rows, scales, repaired):
        mat = compose_similarity(float(scale), float(cur[2]), float(cur[0]), float(cur[1]))
        out_row = {"frame_index": row["frame_index"]}
        out_row.update(matrix_to_cells(mat))
        out_rows.append(out_row)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["frame_index", *MATRIX_FIELDS])
        writer.writeheader()
        writer.writerows(out_rows)
    if args.repair_log is not None:
        args.repair_log.parent.mkdir(parents=True, exist_ok=True)
        with args.repair_log.open("w", newline="", encoding="utf-8") as f:
            fieldnames = ["iteration", "frame", "pre_d2_mag"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(log_rows)
    print(f"rows: {len(out_rows)}")
    print(f"repairs: {len(log_rows)}")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
