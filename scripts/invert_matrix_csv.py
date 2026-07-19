from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np


MATRIX_FIELDS = ["m00", "m01", "m02", "m10", "m11", "m12", "m20", "m21", "m22"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Invert a cpu_stabilize.py 3x3 matrix CSV for device-side VPI warp.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def row_to_matrix(row: dict[str, str]) -> np.ndarray:
    missing = [field for field in MATRIX_FIELDS if field not in row]
    if missing:
        raise ValueError(f"missing matrix fields: {', '.join(missing)}")
    values = [float(row[field]) for field in MATRIX_FIELDS]
    return np.array(values, dtype=np.float64).reshape(3, 3)


def main() -> int:
    args = parse_args()
    with args.input.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise RuntimeError(f"empty CSV: {args.input}")
        fieldnames = list(reader.fieldnames)
        rows = list(reader)

    output_rows: list[dict[str, str]] = []
    for row in rows:
        inv = np.linalg.inv(row_to_matrix(row))
        out_row = dict(row)
        for field, value in zip(MATRIX_FIELDS, inv.reshape(-1), strict=True):
            out_row[field] = f"{float(value):.9f}"
        output_rows.append(out_row)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"inverted {len(output_rows)} matrices: {args.input} -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
