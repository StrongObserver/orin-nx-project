from __future__ import annotations

import argparse
import csv
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Multiply planned inclusion scale by a uniform hardware safety margin.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--margin", type=float, required=True)
    args = parser.parse_args()

    with args.input.open("r", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
        fieldnames = ["frame_index", "required_extra_scale", "planned_extra_scale"]

    out_rows = []
    for row in rows:
        out_rows.append(
            {
                "frame_index": row["frame_index"],
                "required_extra_scale": row["required_extra_scale"],
                "planned_extra_scale": f"{float(row['planned_extra_scale']) * args.margin:.9f}",
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)
    print(f"rows: {len(out_rows)}")
    print(f"margin: {args.margin}")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
