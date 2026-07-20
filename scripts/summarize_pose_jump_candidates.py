from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import numpy as np


MATRIX_FIELDS = ["m00", "m01", "m02", "m10", "m11", "m12", "m20", "m21", "m22"]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def row_to_matrix(row: dict[str, str]) -> np.ndarray:
    return np.array([float(row[field]) for field in MATRIX_FIELDS], dtype=np.float64).reshape(3, 3)


def decompose_similarity(mat: np.ndarray) -> tuple[float, float, float, float]:
    scale = math.hypot(float(mat[0, 0]), float(mat[1, 0]))
    angle = math.atan2(float(mat[1, 0]), float(mat[0, 0]))
    return scale, angle, float(mat[0, 2]), float(mat[1, 2])


def invalid_ratio(mat: np.ndarray, width: int, height: int, margin_px: float) -> float:
    inv = np.linalg.inv(mat)
    xs, ys = np.meshgrid(np.arange(width, dtype=np.float64), np.arange(height, dtype=np.float64))
    points = np.stack([xs, ys, np.ones_like(xs)], axis=-1).reshape(-1, 3)
    mapped = (inv @ points.T).T
    xy = mapped[:, :2] / mapped[:, 2:3]
    valid = (
        (xy[:, 0] >= margin_px)
        & (xy[:, 0] <= width - 1.0 - margin_px)
        & (xy[:, 1] >= margin_px)
        & (xy[:, 1] <= height - 1.0 - margin_px)
    )
    return float(1.0 - valid.mean())


def safe_percentile(values: np.ndarray, percentile: float) -> float:
    if len(values) == 0:
        return 0.0
    return float(np.percentile(values, percentile))


def summarize_matrix(
    matrix_path: Path,
    clip: str,
    candidate: str,
    status: str,
    width: int,
    height: int,
    margin_px: float,
    seam_stride: int,
) -> dict[str, object]:
    rows = read_rows(matrix_path)
    mats = [row_to_matrix(row) for row in rows]
    params = np.array([decompose_similarity(mat) for mat in mats], dtype=np.float64)
    scale = params[:, 0]
    angle = np.unwrap(params[:, 1])
    tx = params[:, 2]
    ty = params[:, 3]
    pose = np.stack([tx, ty, angle], axis=1)

    d1 = np.diff(pose, axis=0)
    d2 = np.diff(pose, n=2, axis=0)
    d3 = np.diff(pose, n=3, axis=0)
    trans_d1 = np.linalg.norm(d1[:, :2], axis=1) if len(d1) else np.array([], dtype=np.float64)
    trans_d2 = np.linalg.norm(d2[:, :2], axis=1) if len(d2) else np.array([], dtype=np.float64)
    trans_d3 = np.linalg.norm(d3[:, :2], axis=1) if len(d3) else np.array([], dtype=np.float64)
    angle_d1 = np.abs(d1[:, 2]) if len(d1) else np.array([], dtype=np.float64)
    angle_d2 = np.abs(d2[:, 2]) if len(d2) else np.array([], dtype=np.float64)
    angle_d3 = np.abs(d3[:, 2]) if len(d3) else np.array([], dtype=np.float64)
    scale_d1 = np.abs(np.diff(scale)) if len(scale) > 1 else np.array([], dtype=np.float64)

    invalid = np.array([invalid_ratio(mat, width, height, margin_px) for mat in mats], dtype=np.float64)

    seam_trans_d1: list[float] = []
    seam_trans_d2: list[float] = []
    seam_angle_d1: list[float] = []
    seam_angle_d2: list[float] = []
    if seam_stride > 0:
        for seam_frame in range(seam_stride, len(pose), seam_stride):
            d1_idx = seam_frame - 1
            d2_idx = seam_frame - 2
            if 0 <= d1_idx < len(d1):
                seam_trans_d1.append(float(trans_d1[d1_idx]))
                seam_angle_d1.append(float(angle_d1[d1_idx]))
            if 0 <= d2_idx < len(d2):
                seam_trans_d2.append(float(trans_d2[d2_idx]))
                seam_angle_d2.append(float(angle_d2[d2_idx]))

    top_d1_frame = int(np.argmax(trans_d1) + 1) if len(trans_d1) else 0
    top_d2_frame = int(np.argmax(trans_d2) + 2) if len(trans_d2) else 0
    top_d3_frame = int(np.argmax(trans_d3) + 3) if len(trans_d3) else 0

    return {
        "clip": clip,
        "candidate": candidate,
        "status": status,
        "matrix": str(matrix_path),
        "frames": len(rows),
        "scale_delta_p95": f"{safe_percentile(scale_d1, 95):.9f}",
        "scale_delta_max": f"{float(scale_d1.max()) if len(scale_d1) else 0.0:.9f}",
        "trans_d1_p95": f"{safe_percentile(trans_d1, 95):.9f}",
        "trans_d1_max": f"{float(trans_d1.max()) if len(trans_d1) else 0.0:.9f}",
        "trans_d1_top_frame": top_d1_frame,
        "angle_d1_p95": f"{safe_percentile(angle_d1, 95):.9f}",
        "angle_d1_max": f"{float(angle_d1.max()) if len(angle_d1) else 0.0:.9f}",
        "trans_d2_p95": f"{safe_percentile(trans_d2, 95):.9f}",
        "trans_d2_max": f"{float(trans_d2.max()) if len(trans_d2) else 0.0:.9f}",
        "trans_d2_top_frame": top_d2_frame,
        "angle_d2_p95": f"{safe_percentile(angle_d2, 95):.9f}",
        "angle_d2_max": f"{float(angle_d2.max()) if len(angle_d2) else 0.0:.9f}",
        "trans_d3_p95": f"{safe_percentile(trans_d3, 95):.9f}",
        "trans_d3_max": f"{float(trans_d3.max()) if len(trans_d3) else 0.0:.9f}",
        "trans_d3_top_frame": top_d3_frame,
        "angle_d3_p95": f"{safe_percentile(angle_d3, 95):.9f}",
        "angle_d3_max": f"{float(angle_d3.max()) if len(angle_d3) else 0.0:.9f}",
        "invalid_p95": f"{safe_percentile(invalid, 95):.9f}",
        "invalid_max": f"{float(invalid.max()) if len(invalid) else 0.0:.9f}",
        "invalid_frames_gt_0p01": int(np.sum(invalid > 0.01)),
        "seam_trans_d1_max": f"{max(seam_trans_d1) if seam_trans_d1 else 0.0:.9f}",
        "seam_trans_d2_max": f"{max(seam_trans_d2) if seam_trans_d2 else 0.0:.9f}",
        "seam_angle_d1_max": f"{max(seam_angle_d1) if seam_angle_d1 else 0.0:.9f}",
        "seam_angle_d2_max": f"{max(seam_angle_d2) if seam_angle_d2 else 0.0:.9f}",
    }


def write_markdown(rows: list[dict[str, object]], path: Path) -> None:
    fields = [
        "clip",
        "candidate",
        "status",
        "trans_d1_p95",
        "trans_d2_max",
        "trans_d3_max",
        "angle_d1_p95",
        "invalid_p95",
        "seam_trans_d2_max",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write("# Pose Jump Candidate Summary\n\n")
        f.write("| " + " | ".join(fields) + " |\n")
        f.write("|" + "|".join(["---"] * len(fields)) + "|\n")
        for row in rows:
            f.write("| " + " | ".join(str(row[field]) for field in fields) + " |\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize pose-jump metrics across matrix candidates.")
    parser.add_argument("--manifest", type=Path, required=True, help="CSV with clip,candidate,status,matrix columns.")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=360)
    parser.add_argument("--margin-px", type=float, default=0.0)
    parser.add_argument("--seam-stride", type=int, default=5)
    args = parser.parse_args()

    manifest_rows = read_rows(args.manifest)
    out_rows = []
    for row in manifest_rows:
        matrix_path = Path(row["matrix"])
        if not matrix_path.is_absolute():
            matrix_path = args.manifest.parent / matrix_path
        if not matrix_path.exists():
            raise FileNotFoundError(f"matrix missing for {row['clip']} {row['candidate']}: {matrix_path}")
        out_rows.append(
            summarize_matrix(
                matrix_path,
                row["clip"],
                row["candidate"],
                row.get("status", ""),
                args.width,
                args.height,
                args.margin_px,
                args.seam_stride,
            )
        )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.out_dir / "pose_jump_candidate_summary.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        writer.writeheader()
        writer.writerows(out_rows)
    md_path = args.out_dir / "pose_jump_candidate_summary.md"
    write_markdown(out_rows, md_path)
    print(f"summary_csv: {csv_path}")
    print(f"summary_md: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
