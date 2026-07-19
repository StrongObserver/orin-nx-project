from __future__ import annotations

import argparse
import csv
from pathlib import Path

import cv2
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a contact sheet and region stats for extracted EIS comparison frames.")
    parser.add_argument("--frames-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--frames", required=True, help="Comma-separated frame indices")
    parser.add_argument("--labels", default="source,cpu,oldinv,postgeom")
    return parser.parse_args()


def load_frame(frames_dir: Path, label: str, frame_index: int) -> np.ndarray:
    path = frames_dir / f"{label}_{frame_index:04d}.png"
    frame = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if frame is None:
        raise RuntimeError(f"Cannot read frame: {path}")
    return frame


def draw_label(frame: np.ndarray, text: str) -> np.ndarray:
    out = frame.copy()
    cv2.putText(out, text, (16, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(out, text, (14, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (255, 255, 255), 2, cv2.LINE_AA)
    return out


def region_stats(diff: np.ndarray) -> dict[str, float]:
    h, w = diff.shape[:2]
    y0, y1 = h // 4, (h * 3) // 4
    x0, x1 = w // 4, (w * 3) // 4
    center = diff[y0:y1, x0:x1]
    edge_mask = np.ones((h, w), dtype=bool)
    edge_mask[y0:y1, x0:x1] = False
    edge = diff[edge_mask]
    return {
        "mean_all": float(diff.mean()),
        "p95_all": float(np.percentile(diff, 95)),
        "mean_center": float(center.mean()),
        "p95_center": float(np.percentile(center, 95)),
        "mean_edge": float(edge.mean()),
        "p95_edge": float(np.percentile(edge, 95)),
    }


def main() -> int:
    args = parse_args()
    frame_ids = [int(item.strip()) for item in args.frames.split(",") if item.strip()]
    labels = [item.strip() for item in args.labels.split(",") if item.strip()]
    args.out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    sheet_rows = []
    for frame_index in frame_ids:
        frames = {label: load_frame(args.frames_dir, label, frame_index) for label in labels}
        cpu = frames["cpu"]
        post = frames["postgeom"]
        old = frames["oldinv"]
        diff_post = np.abs(cpu.astype(np.int16) - post.astype(np.int16)).astype(np.uint8)
        diff_old = np.abs(cpu.astype(np.int16) - old.astype(np.int16)).astype(np.uint8)
        diff_vis = cv2.applyColorMap(np.clip(diff_post * 4, 0, 255).astype(np.uint8), cv2.COLORMAP_INFERNO)
        row_images = [
            draw_label(cv2.resize(frames["source"], (480, 270)), f"source f{frame_index}"),
            draw_label(cv2.resize(cpu, (480, 270)), "cpu"),
            draw_label(cv2.resize(old, (480, 270)), "old inverse"),
            draw_label(cv2.resize(post, (480, 270)), "post geometry"),
            draw_label(cv2.resize(diff_vis, (480, 270)), "abs diff x4"),
        ]
        sheet_rows.append(cv2.hconcat(row_images))

        for name, diff in (("cpu_vs_oldinv", diff_old), ("cpu_vs_postgeom", diff_post)):
            stats = region_stats(diff)
            rows.append(
                {
                    "frame": frame_index,
                    "comparison": name,
                    **{key: f"{value:.6f}" for key, value in stats.items()},
                }
            )

    sheet = cv2.vconcat(sheet_rows)
    sheet_path = args.out_dir / "frame_attribution_sheet.jpg"
    cv2.imwrite(str(sheet_path), sheet)

    csv_path = args.out_dir / "frame_region_stats.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"sheet: {sheet_path}")
    print(f"stats: {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
