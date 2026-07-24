from __future__ import annotations

import argparse
import csv
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Fade planned inclusion scale back to 1.0 after a startup window.")
    parser.add_argument("--scale-csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--hold-frames", type=int, default=30)
    parser.add_argument("--fade-frames", type=int, default=30)
    args = parser.parse_args()

    with args.scale_csv.open("r", newline="", encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))

    out_rows = []
    for row in rows:
        frame = int(row["frame_index"])
        planned = float(row["planned_extra_scale"])
        if frame < args.hold_frames:
            scale = planned
        elif frame < args.hold_frames + args.fade_frames:
            alpha = (frame - args.hold_frames + 1) / max(1, args.fade_frames)
            scale = planned * (1.0 - alpha) + 1.0 * alpha
        else:
            scale = 1.0
        out_row = dict(row)
        out_row["planned_extra_scale"] = f"{scale:.9f}"
        out_rows.append(out_row)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(out_rows[0].keys()))
        writer.writeheader()
        writer.writerows(out_rows)
    print(f"rows: {len(out_rows)}")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
