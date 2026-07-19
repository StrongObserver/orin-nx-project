from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np


MATRIX_FIELDS = ["m00", "m01", "m02", "m10", "m11", "m12", "m20", "m21", "m22"]


def read_matrices(path: Path) -> dict[int, np.ndarray]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    out: dict[int, np.ndarray] = {}
    for row in rows:
        frame = int(row["frame_index"])
        values = [float(row[field]) for field in MATRIX_FIELDS]
        out[frame] = np.array(values, dtype=np.float64).reshape(3, 3)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two per-frame 3x3 matrix CSV files.")
    parser.add_argument("--a", type=Path, required=True)
    parser.add_argument("--b", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    mats_a = read_matrices(args.a)
    mats_b = read_matrices(args.b)
    common = sorted(set(mats_a) & set(mats_b))
    args.out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for frame in common:
        diff = mats_a[frame] - mats_b[frame]
        rows.append(
            {
                "frame": frame,
                "fro_abs": f"{float(np.linalg.norm(diff, ord='fro')):.9f}",
                "max_abs": f"{float(np.max(np.abs(diff))):.9f}",
                "translation_abs": f"{float(np.linalg.norm(diff[:2, 2])):.9f}",
                "linear_fro_abs": f"{float(np.linalg.norm(diff[:2, :2], ord='fro')):.9f}",
            }
        )

    frame_csv = args.out_dir / "matrix_diff.csv"
    with frame_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["frame", "fro_abs", "max_abs", "translation_abs", "linear_fro_abs"])
        writer.writeheader()
        writer.writerows(rows)

    def values(key: str) -> np.ndarray:
        return np.array([float(row[key]) for row in rows], dtype=np.float64)

    summary = {
        "a": str(args.a),
        "b": str(args.b),
        "frames_compared": len(rows),
        "a_only_rows": len(set(mats_a) - set(mats_b)),
        "b_only_rows": len(set(mats_b) - set(mats_a)),
    }
    for key in ("fro_abs", "max_abs", "translation_abs", "linear_fro_abs"):
        vals = values(key)
        summary[f"{key}_mean"] = f"{float(vals.mean()) if len(vals) else 0.0:.9f}"
        summary[f"{key}_p95"] = f"{float(np.percentile(vals, 95)) if len(vals) else 0.0:.9f}"
        summary[f"{key}_max"] = f"{float(vals.max()) if len(vals) else 0.0:.9f}"

    summary_csv = args.out_dir / "summary.csv"
    with summary_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary.keys()))
        writer.writeheader()
        writer.writerow(summary)

    print(f"frame_diff: {frame_csv}")
    print(f"summary: {summary_csv}")
    for key, value in summary.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
