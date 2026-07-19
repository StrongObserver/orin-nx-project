from __future__ import annotations

import argparse
import csv
from pathlib import Path

import cv2
import numpy as np


MATRIX_FIELDS = ["m00", "m01", "m02", "m10", "m11", "m12", "m20", "m21", "m22"]


def read_matrices(path: Path) -> list[np.ndarray]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    mats = []
    for row in rows:
        mats.append(np.array([float(row[field]) for field in MATRIX_FIELDS], dtype=np.float64).reshape(3, 3))
    return mats


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply per-frame matrices with VPI Python using allocated VPI images.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--backend", choices=["cuda", "cpu", "vic"], default="cuda")
    parser.add_argument("--input-format", choices=["bgr8", "rgb8"], default="bgr8")
    parser.add_argument("--max-frames", type=int, default=0)
    args = parser.parse_args()

    import vpi

    backend_map = {
        "cuda": vpi.Backend.CUDA,
        "cpu": vpi.Backend.CPU,
        "vic": vpi.Backend.VIC,
    }
    backend = backend_map[args.backend]
    mats = read_matrices(args.matrix)
    cap = cv2.VideoCapture(str(args.input))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open input: {args.input}")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(args.output), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"Cannot open output: {args.output}")

    frame_index = 0
    while True:
        if args.max_frames and frame_index >= args.max_frames:
            break
        ok, frame_bgr = cap.read()
        if not ok:
            break
        mat = mats[frame_index] if frame_index < len(mats) else np.eye(3, dtype=np.float64)
        if args.input_format == "rgb8":
            frame_for_vpi = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            source_format = vpi.Format.RGB8
        else:
            frame_for_vpi = frame_bgr
            source_format = vpi.Format.BGR8
        with vpi.Backend.CUDA:
            frame_vpi = vpi.asimage(frame_for_vpi, source_format).convert(vpi.Format.NV12_ER)
        with backend:
            warped = frame_vpi.perspwarp(mat)
        with vpi.Backend.CUDA:
            warped = warped.convert(vpi.Format.RGB8)
        with warped.rlock_cpu() as data_rgb:
            out_rgb = np.array(data_rgb, copy=True)
        writer.write(cv2.cvtColor(out_rgb, cv2.COLOR_RGB2BGR))
        frame_index += 1

    cap.release()
    writer.release()
    print(f"output: {args.output}")
    print(f"frames_written: {frame_index}")
    print(f"fps: {fps}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
