from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stream matrix CSV rows to a FIFO or regular file for MMAPI matrix handoff tests.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sleep-ms", type=float, default=0.0)
    parser.add_argument("--flush-each-row", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with args.input.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        rows = list(reader)
    if not rows:
        raise RuntimeError(f"empty input CSV: {args.input}")

    row_count = 0
    t0 = time.perf_counter()
    with args.output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for row in rows:
            writer.writerow(row)
            row_count += 1
            if args.flush_each_row:
                f.flush()
            if args.sleep_ms > 0 and row_count > 1:
                time.sleep(args.sleep_ms / 1000.0)
    elapsed_s = time.perf_counter() - t0
    print(f"streamed_rows: {row_count}")
    print(f"data_rows: {max(0, row_count - 1)}")
    print(f"elapsed_s: {elapsed_s:.6f}")
    print(f"input: {args.input}")
    print(f"output: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
