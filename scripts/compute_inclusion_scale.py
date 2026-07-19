from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np


MATRIX_FIELDS = ["m00", "m01", "m02", "m10", "m11", "m12", "m20", "m21", "m22"]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def row_to_matrix(row: dict[str, str]) -> np.ndarray:
    values = [float(row[field]) for field in MATRIX_FIELDS]
    return np.array(values, dtype=np.float64).reshape(3, 3)


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


def required_extra_scale(mat: np.ndarray, width: int, height: int, safety_px: float) -> float:
    # We choose extra center scale s applied after the matrix: H' = S(s) @ H.
    # To avoid black output pixels, every output-frame corner must sample from a
    # valid source coordinate under inv(H'). This matches OpenCV/VPI forward-warp
    # semantics better than checking whether transformed source corners are
    # inside the output frame.
    corners = np.array(
        [
            [0.0, 0.0, 1.0],
            [width - 1.0, 0.0, 1.0],
            [width - 1.0, height - 1.0, 1.0],
            [0.0, height - 1.0, 1.0],
        ],
        dtype=np.float64,
    )

    def ok(scale: float) -> bool:
        cur = center_scale(width, height, scale) @ mat
        try:
            inv = np.linalg.inv(cur)
        except np.linalg.LinAlgError:
            return False
        mapped = (inv @ corners.T).T
        xy = mapped[:, :2] / mapped[:, 2:3]
        return bool(
            np.all(xy[:, 0] >= safety_px)
            and np.all(xy[:, 0] <= width - 1.0 - safety_px)
            and np.all(xy[:, 1] >= safety_px)
            and np.all(xy[:, 1] <= height - 1.0 - safety_px)
        )

    if ok(1.0):
        return 1.0
    low = 1.0
    high = 1.05
    while not ok(high) and high < 4.0:
        high *= 1.25
    for _ in range(32):
        mid = (low + high) * 0.5
        if ok(mid):
            high = mid
        else:
            low = mid
    return high


def rolling_max_forward(values: np.ndarray, lookahead: int) -> np.ndarray:
    out = np.empty_like(values)
    n = len(values)
    for i in range(n):
        out[i] = float(np.max(values[i : min(n, i + lookahead + 1)]))
    return out


def rate_limit(values: np.ndarray, max_step: float) -> np.ndarray:
    if max_step <= 0:
        return values.copy()
    out = np.empty_like(values)
    out[0] = values[0]
    for i in range(1, len(values)):
        delta = float(values[i] - out[i - 1])
        delta = max(-max_step, min(max_step, delta))
        out[i] = out[i - 1] + delta
    return out


def apply_hysteresis(values: np.ndarray, threshold: float) -> np.ndarray:
    if threshold <= 0:
        return values.copy()
    out = np.empty_like(values)
    out[0] = values[0]
    for i in range(1, len(values)):
        if abs(float(values[i] - out[i - 1])) >= threshold:
            out[i] = values[i]
        else:
            out[i] = out[i - 1]
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute per-frame inclusion-safe extra scale for device matrices.")
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--width", type=int, required=True)
    parser.add_argument("--height", type=int, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--safety-px", type=float, default=1.0)
    parser.add_argument("--lookahead", type=int, default=0)
    parser.add_argument("--rate-limit", type=float, default=0.0)
    parser.add_argument("--hysteresis", type=float, default=0.0)
    args = parser.parse_args()

    rows = read_rows(args.matrix)
    raw = np.array([required_extra_scale(row_to_matrix(row), args.width, args.height, args.safety_px) for row in rows])
    planned = rolling_max_forward(raw, max(0, int(args.lookahead)))
    planned = apply_hysteresis(planned, args.hysteresis)
    planned = rate_limit(planned, args.rate_limit)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_rows = []
    for row, raw_scale, planned_scale in zip(rows, raw, planned):
        out_rows.append(
            {
                "frame_index": row["frame_index"],
                "required_extra_scale": f"{float(raw_scale):.9f}",
                "planned_extra_scale": f"{float(planned_scale):.9f}",
            }
        )
    csv_path = args.out_dir / "inclusion_scale.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        writer.writeheader()
        writer.writerows(out_rows)

    summary = {
        "matrix": str(args.matrix),
        "frames": len(rows),
        "raw_mean": f"{float(np.mean(raw)):.9f}",
        "raw_p95": f"{float(np.percentile(raw, 95)):.9f}",
        "raw_max": f"{float(np.max(raw)):.9f}",
        "planned_mean": f"{float(np.mean(planned)):.9f}",
        "planned_p95": f"{float(np.percentile(planned, 95)):.9f}",
        "planned_max": f"{float(np.max(planned)):.9f}",
        "lookahead": int(args.lookahead),
        "rate_limit": float(args.rate_limit),
        "hysteresis": float(args.hysteresis),
    }
    summary_path = args.out_dir / "summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary.keys()))
        writer.writeheader()
        writer.writerow(summary)
    for key, value in summary.items():
        print(f"{key}: {value}")
    print(f"scale_csv: {csv_path}")
    print(f"summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
