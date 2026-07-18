from __future__ import annotations

import argparse
import csv
from pathlib import Path

import cv2


def inspect_pattern(label: str, pattern: str) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(Path(".").glob(pattern)):
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            rows.append({"label": label, "file": str(path), "read": 0})
            continue
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        rows.append(
            {
                "label": label,
                "file": str(path),
                "read": 1,
                "width": image.shape[1],
                "height": image.shape[0],
                "mean": f"{float(gray.mean()):.6f}",
                "std": f"{float(gray.std()):.6f}",
                "nonzero_ratio": f"{float((gray > 4).mean()):.6f}",
                "black_ratio": f"{float((gray < 5).mean()):.6f}",
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect extracted frame images for basic non-empty/brightness sanity.")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--pattern", action="append", nargs=2, metavar=("LABEL", "GLOB"), required=True)
    args = parser.parse_args()
    rows: list[dict] = []
    for label, pattern in args.pattern:
        rows.extend(inspect_pattern(label, pattern))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["label", "file", "read", "width", "height", "mean", "std", "nonzero_ratio", "black_ratio"]
    with args.out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    for row in rows:
        print(row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
