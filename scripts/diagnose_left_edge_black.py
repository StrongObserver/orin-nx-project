from __future__ import annotations

import argparse
import csv
from pathlib import Path

import cv2
import numpy as np


def parse_item(value: str) -> tuple[str, Path]:
    if "|" not in value:
        raise ValueError("--item must be label|path")
    label, path = value.split("|", 1)
    return label, Path(path)


def panel_slices(label: str, gray: np.ndarray) -> dict[str, np.ndarray]:
    if label != "grid":
        return {label: gray}
    h, w = gray.shape
    if h < 720 or w < 1280:
        return {label: gray}
    return {
        "source_panel": gray[0:360, 0:640],
        "egl_panel": gray[0:360, 640:1280],
        "stream_panel": gray[360:720, 0:640],
        "nvbuf_panel": gray[360:720, 640:1280],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure left-edge near-black area in the first frames.")
    parser.add_argument("--item", action="append", required=True, help="label|path")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--frames", type=int, default=60)
    parser.add_argument("--threshold", type=int, default=8)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    summary: list[dict[str, object]] = []
    for label, path in [parse_item(item) for item in args.item]:
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open {label}: {path}")
        rows: list[dict[str, object]] = []
        worst: tuple[float, int, str, np.ndarray] | None = None
        frame_index = 0
        while frame_index < args.frames:
            ok, frame = cap.read()
            if not ok:
                break
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            for panel, panel_gray in panel_slices(label, gray).items():
                left24 = float((panel_gray[:, 0:24] <= args.threshold).mean())
                left80 = float((panel_gray[:, 0:80] <= args.threshold).mean())
                rows.append(
                    {
                        "frame": frame_index,
                        "panel": panel,
                        "left24": f"{left24:.9f}",
                        "left80": f"{left80:.9f}",
                    }
                )
                if worst is None or left80 > worst[0]:
                    worst = (left80, frame_index, panel, frame.copy())
            frame_index += 1
        cap.release()
        with (args.out_dir / f"{label}_left_edge.csv").open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        values = np.array([float(row["left80"]) for row in rows], dtype=np.float64)
        summary.append(
            {
                "video": label,
                "rows": len(rows),
                "max_left80": f"{float(values.max()) if len(values) else 0.0:.9f}",
                "mean_left80": f"{float(values.mean()) if len(values) else 0.0:.9f}",
            }
        )
        if worst is not None:
            _, idx, panel, frame = worst
            cv2.imwrite(str(args.out_dir / f"{label}_worst_left_f{idx:04d}_{panel}.jpg"), frame)

    with (args.out_dir / "summary.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(summary[0].keys()))
        writer.writeheader()
        writer.writerows(summary)
    for row in summary:
        print(row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
