from __future__ import annotations

import argparse
import csv
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Set planned inclusion scale to a single constant value.")
    parser.add_argument("--scale-csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--frames", type=int, default=0, help="Only apply to the first N frames; 0 means all frames.")
    args = parser.parse_args()

    with args.scale_csv.open("r", newline="", encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))
    limit = args.frames if args.frames > 0 else len(rows)
    constant = max(float(row["required_extra_scale"]) for row in rows[:limit])
    for index, row in enumerate(rows):
        row["planned_extra_scale"] = f"{constant if index < limit else 1.0:.9f}"

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"constant_scale: {constant:.9f}")
    print(f"rows: {len(rows)}")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
