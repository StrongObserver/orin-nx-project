import argparse
import csv
import math
from pathlib import Path

import cv2
import numpy as np


REGIONS = [
    ("top_left", 0.0, 0.35, 0.0, 0.35),
    ("top_right", 0.65, 1.0, 0.0, 0.35),
    ("bottom_left", 0.0, 0.35, 0.65, 1.0),
    ("bottom_right", 0.65, 1.0, 0.65, 1.0),
    ("center", 0.30, 0.70, 0.30, 0.70),
    ("top_band", 0.0, 1.0, 0.0, 0.33),
    ("middle_band", 0.0, 1.0, 0.33, 0.67),
    ("bottom_band", 0.0, 1.0, 0.67, 1.0),
]


def open_video(path: Path) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {path}")
    return cap


def percentile(values: list[float], pct: float) -> float:
    return float(np.percentile(values, pct)) if values else 0.0


def mean(values: list[float]) -> float:
    return float(np.mean(values)) if values else 0.0


def estimate_affine(prev_gray: np.ndarray, gray: np.ndarray):
    pts = cv2.goodFeaturesToTrack(prev_gray, maxCorners=700, qualityLevel=0.01, minDistance=8, blockSize=3)
    if pts is None or len(pts) < 16:
        return None
    next_pts, status, _ = cv2.calcOpticalFlowPyrLK(prev_gray, gray, pts, None)
    if next_pts is None or status is None:
        return None
    mask = status.reshape(-1).astype(bool)
    src = pts.reshape(-1, 2)[mask]
    dst = next_pts.reshape(-1, 2)[mask]
    if len(src) < 16:
        return None
    mat, inliers = cv2.estimateAffine2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=3.0)
    if mat is None or inliers is None:
        return None
    inlier_mask = inliers.reshape(-1).astype(bool)
    if int(np.sum(inlier_mask)) < 16:
        return None
    src_h = np.hstack([src, np.ones((len(src), 1), dtype=np.float32)])
    pred = (mat @ src_h.T).T
    residual = dst - pred
    return src, dst, residual, inlier_mask, mat


def region_mask(points: np.ndarray, width: int, height: int, x0: float, x1: float, y0: float, y1: float) -> np.ndarray:
    return (
        (points[:, 0] >= x0 * width)
        & (points[:, 0] < x1 * width)
        & (points[:, 1] >= y0 * height)
        & (points[:, 1] < y1 * height)
    )


def region_vector(residual: np.ndarray, mask: np.ndarray) -> np.ndarray | None:
    if int(np.sum(mask)) < 6:
        return None
    return np.median(residual[mask], axis=0)


def affine_shape_metrics(mat: np.ndarray) -> tuple[float, float, float]:
    linear = mat[:2, :2].astype(np.float64)
    singular = np.linalg.svd(linear, compute_uv=False)
    scale = float(np.sqrt(abs(np.linalg.det(linear))))
    anisotropy = float(singular[0] / max(singular[1], 1e-9))
    gram = linear.T @ linear
    mean_square_scale = float(np.trace(gram) * 0.5)
    shear_proxy = float(np.linalg.norm(gram - np.eye(2) * mean_square_scale, ord="fro"))
    return abs(scale - 1.0), abs(anisotropy - 1.0), shear_proxy


def analyze(path: Path, max_frames: int, tail_frames: int) -> tuple[dict[str, object], list[dict[str, object]]]:
    cap = open_video(path)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    ok, prev = cap.read()
    if not ok:
        cap.release()
        raise RuntimeError(f"Cannot read first frame: {path}")
    prev_gray = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)

    frame_rows = []
    pairs = 0
    while max_frames <= 0 or pairs < max_frames:
        ok, frame = cap.read()
        if not ok:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        est = estimate_affine(prev_gray, gray)
        pairs += 1
        if est is None:
            prev_gray = gray
            continue
        src, dst, residual, inlier_mask, mat = est
        inlier_residual = residual[inlier_mask]
        residual_norm = np.linalg.norm(inlier_residual, axis=1)
        region_vectors = {}
        region_counts = {}
        for name, x0, x1, y0, y1 in REGIONS:
            mask = inlier_mask & region_mask(src, width, height, x0, x1, y0, y1)
            region_counts[name] = int(np.sum(mask))
            vec = region_vector(residual, mask)
            if vec is not None:
                region_vectors[name] = vec

        center = region_vectors.get("center", np.array([0.0, 0.0], dtype=np.float32))
        corner_deltas = []
        for name in ("top_left", "top_right", "bottom_left", "bottom_right"):
            if name in region_vectors:
                corner_deltas.append(float(np.linalg.norm(region_vectors[name] - center)))
        opposite_deltas = []
        for a, b in (("top_left", "bottom_right"), ("top_right", "bottom_left")):
            if a in region_vectors and b in region_vectors:
                opposite_deltas.append(float(np.linalg.norm(region_vectors[a] - region_vectors[b])))
        row_deltas = []
        if "top_band" in region_vectors and "bottom_band" in region_vectors:
            row_deltas.append(float(np.linalg.norm(region_vectors["top_band"] - region_vectors["bottom_band"])))
        if "top_band" in region_vectors and "middle_band" in region_vectors:
            row_deltas.append(float(np.linalg.norm(region_vectors["top_band"] - region_vectors["middle_band"])))
        if "middle_band" in region_vectors and "bottom_band" in region_vectors:
            row_deltas.append(float(np.linalg.norm(region_vectors["middle_band"] - region_vectors["bottom_band"])))

        scale_delta, anisotropy_delta, shear_proxy = affine_shape_metrics(mat)
        trans = float(np.linalg.norm(mat[:2, 2]))
        frame_rows.append(
            {
                "pair_index": pairs,
                "tracked": len(src),
                "inliers": int(np.sum(inlier_mask)),
                "inlier_ratio": int(np.sum(inlier_mask)) / max(1, len(src)),
                "global_translation": trans,
                "residual_p50": percentile(residual_norm.tolist(), 50),
                "residual_p95": percentile(residual_norm.tolist(), 95),
                "corner_center_delta_max": max(corner_deltas) if corner_deltas else 0.0,
                "corner_center_delta_mean": mean(corner_deltas),
                "opposite_corner_delta_max": max(opposite_deltas) if opposite_deltas else 0.0,
                "row_delta_max": max(row_deltas) if row_deltas else 0.0,
                "scale_abs_delta": scale_delta,
                "anisotropy_abs_delta": anisotropy_delta,
                "shear_proxy": shear_proxy,
                **{f"count_{name}": count for name, count in region_counts.items()},
            }
        )
        prev_gray = gray
    cap.release()

    tail_start = max(1, frame_count - int(tail_frames))
    tail = [row for row in frame_rows if int(row["pair_index"]) >= tail_start]
    summary = summarize(path, width, height, fps, frame_count, frame_rows, tail, tail_start)
    return summary, frame_rows


def summarize(
    path: Path,
    width: int,
    height: int,
    fps: float,
    frame_count: int,
    rows: list[dict[str, object]],
    tail: list[dict[str, object]],
    tail_start: int,
) -> dict[str, object]:
    def values(key: str, source: list[dict[str, object]] = rows) -> list[float]:
        return [float(row[key]) for row in source if key in row]

    return {
        "name": path.stem,
        "path": str(path),
        "width": width,
        "height": height,
        "fps": f"{fps:.3f}",
        "frames": frame_count,
        "pairs_valid": len(rows),
        "tail_start_pair": tail_start,
        "tail_pairs_valid": len(tail),
        "motion_p95": f"{percentile(values('global_translation'), 95):.6f}",
        "tail_motion_p95": f"{percentile(values('global_translation', tail), 95):.6f}",
        "residual_p95": f"{percentile(values('residual_p95'), 95):.6f}",
        "tail_residual_p95": f"{percentile(values('residual_p95', tail), 95):.6f}",
        "corner_center_delta_p95": f"{percentile(values('corner_center_delta_max'), 95):.6f}",
        "tail_corner_center_delta_p95": f"{percentile(values('corner_center_delta_max', tail), 95):.6f}",
        "opposite_corner_delta_p95": f"{percentile(values('opposite_corner_delta_max'), 95):.6f}",
        "tail_opposite_corner_delta_p95": f"{percentile(values('opposite_corner_delta_max', tail), 95):.6f}",
        "row_delta_p95": f"{percentile(values('row_delta_max'), 95):.6f}",
        "tail_row_delta_p95": f"{percentile(values('row_delta_max', tail), 95):.6f}",
        "scale_abs_delta_p95": f"{percentile(values('scale_abs_delta'), 95):.6f}",
        "tail_scale_abs_delta_p95": f"{percentile(values('scale_abs_delta', tail), 95):.6f}",
        "anisotropy_abs_delta_p95": f"{percentile(values('anisotropy_abs_delta'), 95):.6f}",
        "tail_anisotropy_abs_delta_p95": f"{percentile(values('anisotropy_abs_delta', tail), 95):.6f}",
        "shear_proxy_p95": f"{percentile(values('shear_proxy'), 95):.6f}",
        "tail_shear_proxy_p95": f"{percentile(values('shear_proxy', tail), 95):.6f}",
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose local corner/row residual artifacts in stabilized videos.")
    parser.add_argument("--input", action="append", required=True, help="Video path. Can be repeated.")
    parser.add_argument("--name", action="append", default=[], help="Optional display name, repeated in input order.")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--max-frames", type=int, default=0)
    parser.add_argument("--tail-frames", type=int, default=45)
    args = parser.parse_args()

    summaries = []
    for idx, item in enumerate(args.input):
        path = Path(item)
        summary, frame_rows = analyze(path, args.max_frames, args.tail_frames)
        if idx < len(args.name):
            summary["name"] = args.name[idx]
        summaries.append(summary)
        safe_name = str(summary["name"]).replace("/", "_").replace("\\", "_")
        write_csv(args.out_dir / f"{safe_name}_local_artifact_frames.csv", frame_rows)
        print(
            f"{summary['name']}: tail_motion_p95={summary['tail_motion_p95']} "
            f"tail_corner_delta_p95={summary['tail_corner_center_delta_p95']} "
            f"tail_row_delta_p95={summary['tail_row_delta_p95']} "
            f"tail_shear_p95={summary['tail_shear_proxy_p95']}"
        )
    write_csv(args.out_dir / "local_artifact_summary.csv", summaries)
    print(f"Wrote local artifact summary: {args.out_dir / 'local_artifact_summary.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
