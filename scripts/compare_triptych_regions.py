from __future__ import annotations

import argparse
import csv
from pathlib import Path

import cv2
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare two panels inside a side-by-side or triptych review video. "
            "This is useful when the original source videos are not all present locally."
        )
    )
    parser.add_argument("--input", type=Path, required=True, help="Review video containing equal-width panels.")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--columns", type=int, default=3, help="Number of equal-width panels in the review video.")
    parser.add_argument("--left-index", type=int, required=True, help="0-based panel index for reference.")
    parser.add_argument("--right-index", type=int, required=True, help="0-based panel index for candidate.")
    parser.add_argument("--left-label", default="left")
    parser.add_argument("--right-label", default="right")
    parser.add_argument("--max-frames", type=int, default=0)
    parser.add_argument(
        "--skip-top-ratio",
        type=float,
        default=0.08,
        help="Top band to ignore so panel labels do not dominate pixel differences.",
    )
    parser.add_argument(
        "--center-ratio",
        type=float,
        default=0.50,
        help="Central crop ratio used for less border-sensitive comparison.",
    )
    parser.add_argument("--sample-frames", default="0,30,60,90", help="Comma-separated frame ids for a contact sheet.")
    return parser.parse_args()


def percentile(values: list[float], q: float) -> float:
    return float(np.percentile(np.array(values, dtype=np.float64), q)) if values else 0.0


def format_float(value: float) -> str:
    return f"{value:.6f}"


def panel_bounds(width: int, columns: int, index: int) -> tuple[int, int]:
    if columns <= 0:
        raise ValueError("--columns must be positive")
    if index < 0 or index >= columns:
        raise ValueError(f"panel index {index} out of range for {columns} columns")
    panel_width = width // columns
    x0 = panel_width * index
    x1 = panel_width * (index + 1) if index < columns - 1 else width
    return x0, x1


def crop_regions(diff: np.ndarray, skip_top_ratio: float, center_ratio: float) -> dict[str, np.ndarray]:
    height, width = diff.shape[:2]
    y0 = min(height - 1, max(0, int(round(height * skip_top_ratio))))
    work = diff[y0:, :]
    wh, ww = work.shape[:2]

    center_ratio = min(1.0, max(0.05, center_ratio))
    cx0 = int(round((1.0 - center_ratio) * ww / 2.0))
    cx1 = ww - cx0
    cy0 = int(round((1.0 - center_ratio) * wh / 2.0))
    cy1 = wh - cy0
    center = work[cy0:cy1, cx0:cx1]

    edge_mask = np.ones((wh, ww), dtype=bool)
    edge_mask[cy0:cy1, cx0:cx1] = False
    edge = work[edge_mask]
    return {"all": work, "center": center, "edge": edge}


def diff_stats(region: np.ndarray) -> dict[str, float]:
    if region.size == 0:
        return {"mean": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0}
    return {
        "mean": float(region.mean()),
        "p95": float(np.percentile(region, 95)),
        "p99": float(np.percentile(region, 99)),
        "max": float(region.max()),
    }


def parse_sample_frames(text: str) -> set[int]:
    frames: set[int] = set()
    for item in text.split(","):
        item = item.strip()
        if not item:
            continue
        frames.add(int(item))
    return frames


def make_sample_sheet(samples: list[tuple[int, np.ndarray, np.ndarray, np.ndarray]], output: Path) -> None:
    if not samples:
        return
    rows = []
    for frame_index, left, right, diff in samples:
        diff_vis = cv2.applyColorMap(np.clip(diff * 4, 0, 255).astype(np.uint8), cv2.COLORMAP_INFERNO)
        cv2.putText(left, f"frame {frame_index}", (20, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
        cv2.putText(left, "reference", (20, 68), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        cv2.putText(right, "candidate", (20, 68), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        cv2.putText(diff_vis, "abs diff x4", (20, 68), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        rows.append(cv2.hconcat([left, right, diff_vis]))
    sheet = cv2.vconcat(rows)
    output.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output), sheet)


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(args.input))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open input video: {args.input}")

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    lx0, lx1 = panel_bounds(width, args.columns, args.left_index)
    rx0, rx1 = panel_bounds(width, args.columns, args.right_index)
    panel_width = min(lx1 - lx0, rx1 - rx0)

    sample_frame_ids = parse_sample_frames(args.sample_frames)
    rows: list[dict[str, str | int]] = []
    samples: list[tuple[int, np.ndarray, np.ndarray, np.ndarray]] = []
    frame_index = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if args.max_frames and frame_index >= args.max_frames:
            break

        left = frame[:, lx0 : lx0 + panel_width].copy()
        right = frame[:, rx0 : rx0 + panel_width].copy()
        diff = np.abs(left.astype(np.int16) - right.astype(np.int16)).astype(np.uint8)
        regions = crop_regions(diff, args.skip_top_ratio, args.center_ratio)
        stats = {name: diff_stats(region) for name, region in regions.items()}
        rows.append(
            {
                "frame": frame_index,
                "mean_abs_all": format_float(stats["all"]["mean"]),
                "p95_abs_all": format_float(stats["all"]["p95"]),
                "p99_abs_all": format_float(stats["all"]["p99"]),
                "max_abs_all": int(stats["all"]["max"]),
                "mean_abs_center": format_float(stats["center"]["mean"]),
                "p95_abs_center": format_float(stats["center"]["p95"]),
                "p99_abs_center": format_float(stats["center"]["p99"]),
                "max_abs_center": int(stats["center"]["max"]),
                "mean_abs_edge": format_float(stats["edge"]["mean"]),
                "p95_abs_edge": format_float(stats["edge"]["p95"]),
                "p99_abs_edge": format_float(stats["edge"]["p99"]),
                "max_abs_edge": int(stats["edge"]["max"]),
            }
        )
        if frame_index in sample_frame_ids:
            samples.append((frame_index, left, right, diff))
        frame_index += 1

    cap.release()

    frame_csv = args.out_dir / "frame_diff.csv"
    if rows:
        with frame_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    numeric_fields = [key for key in rows[0].keys() if key != "frame"] if rows else []
    summary: dict[str, str | int] = {
        "input": str(args.input),
        "columns": args.columns,
        "left_index": args.left_index,
        "right_index": args.right_index,
        "left_label": args.left_label,
        "right_label": args.right_label,
        "video_width": width,
        "video_height": height,
        "panel_width": panel_width,
        "fps": format_float(fps),
        "reported_frame_count": total_frames,
        "frames_compared": len(rows),
        "skip_top_ratio": format_float(args.skip_top_ratio),
        "center_ratio": format_float(args.center_ratio),
    }
    for field in numeric_fields:
        values = [float(row[field]) for row in rows]
        summary[f"{field}_avg"] = format_float(sum(values) / len(values)) if values else "0.000000"
        summary[f"{field}_p95_over_frames"] = format_float(percentile(values, 95))
        summary[f"{field}_max_over_frames"] = format_float(max(values) if values else 0.0)

    summary_csv = args.out_dir / "summary.csv"
    with summary_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary.keys()))
        writer.writeheader()
        writer.writerow(summary)

    sample_sheet = args.out_dir / "sample_contact_sheet.jpg"
    make_sample_sheet(samples, sample_sheet)

    summary_md = args.out_dir / "summary.md"
    summary_md.write_text(
        "\n".join(
            [
                "# Triptych Region Difference Summary",
                "",
                f"- input: `{args.input}`",
                f"- compared panels: `{args.left_label}` index {args.left_index} vs `{args.right_label}` index {args.right_index}",
                f"- frames compared: {len(rows)}",
                f"- panel size: {panel_width}x{height}",
                f"- skipped top ratio: {args.skip_top_ratio}",
                f"- center ratio: {args.center_ratio}",
                "",
                "| Metric | Avg | P95 over frames | Max over frames |",
                "|---|---:|---:|---:|",
                f"| mean_abs_center | {summary.get('mean_abs_center_avg', '0')} | {summary.get('mean_abs_center_p95_over_frames', '0')} | {summary.get('mean_abs_center_max_over_frames', '0')} |",
                f"| p95_abs_center | {summary.get('p95_abs_center_avg', '0')} | {summary.get('p95_abs_center_p95_over_frames', '0')} | {summary.get('p95_abs_center_max_over_frames', '0')} |",
                f"| mean_abs_edge | {summary.get('mean_abs_edge_avg', '0')} | {summary.get('mean_abs_edge_p95_over_frames', '0')} | {summary.get('mean_abs_edge_max_over_frames', '0')} |",
                f"| p95_abs_edge | {summary.get('p95_abs_edge_avg', '0')} | {summary.get('p95_abs_edge_p95_over_frames', '0')} | {summary.get('p95_abs_edge_max_over_frames', '0')} |",
                "",
                "This compares panels already encoded into the review video. It is a stronger local check than single-frame sanity images, but it is not strict raw-frame equivalence.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    print(f"frame_diff: {frame_csv}")
    print(f"summary: {summary_csv}")
    print(f"summary_md: {summary_md}")
    if samples:
        print(f"sample_contact_sheet: {sample_sheet}")
    print(f"frames_compared: {len(rows)}")
    print(f"mean_abs_center_avg: {summary.get('mean_abs_center_avg', '0')}")
    print(f"p95_abs_center_avg: {summary.get('p95_abs_center_avg', '0')}")
    print(f"mean_abs_edge_avg: {summary.get('mean_abs_edge_avg', '0')}")
    print(f"p95_abs_edge_avg: {summary.get('p95_abs_edge_avg', '0')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
