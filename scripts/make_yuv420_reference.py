from __future__ import annotations

import argparse
import math
from pathlib import Path

import cv2
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a planar YUV420 software warp reference.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--width", type=int, required=True)
    parser.add_argument("--height", type=int, required=True)
    parser.add_argument("--frames", type=int, default=0)
    parser.add_argument("--mode", choices=["copy", "translate", "affine"], default="copy")
    parser.add_argument("--dx", type=float, default=8.0)
    parser.add_argument("--dy", type=float, default=0.0)
    parser.add_argument("--angle-deg", type=float, default=0.0)
    parser.add_argument("--scale", type=float, default=1.0)
    return parser.parse_args()


def destination_to_source_matrix(args: argparse.Namespace) -> np.ndarray:
    if args.mode == "copy":
        return np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float32)
    if args.mode == "translate":
        return np.array([[1.0, 0.0, -args.dx], [0.0, 1.0, -args.dy]], dtype=np.float32)
    center = (args.width * 0.5, args.height * 0.5)
    source_to_dest = cv2.getRotationMatrix2D(center, args.angle_deg, args.scale)
    source_to_dest[:, 2] += [args.dx, args.dy]
    return cv2.invertAffineTransform(source_to_dest).astype(np.float32)


def chroma_matrix(matrix: np.ndarray) -> np.ndarray:
    # CUDA maps a chroma sample at (c + 0.5) to luma coordinates
    # (2*c + 0.5), then maps the sampled luma coordinate back to chroma.
    out = matrix.astype(np.float64, copy=True)
    out[0, 2] = 0.25 * (matrix[0, 0] + matrix[0, 1] - 1.0) + 0.5 * matrix[0, 2]
    out[1, 2] = 0.25 * (matrix[1, 0] + matrix[1, 1] - 1.0) + 0.5 * matrix[1, 2]
    return out.astype(np.float32)


def main() -> int:
    args = parse_args()
    if args.width % 2 or args.height % 2:
        raise ValueError("YUV420 dimensions must be even")
    frame_bytes = args.width * args.height * 3 // 2
    total_bytes = args.input.stat().st_size
    available_frames = total_bytes // frame_bytes
    frame_count = available_frames if args.frames <= 0 else min(args.frames, available_frames)
    if frame_count <= 0:
        raise RuntimeError("input does not contain a complete YUV420 frame")

    matrix_y = destination_to_source_matrix(args)
    matrix_c = chroma_matrix(matrix_y)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    y_size = args.width * args.height
    c_width = args.width // 2
    c_height = args.height // 2
    c_size = c_width * c_height
    with args.input.open("rb") as src, args.output.open("wb") as dst:
        for _ in range(frame_count):
            raw = src.read(frame_bytes)
            y = np.frombuffer(raw[:y_size], dtype=np.uint8).reshape(args.height, args.width)
            u = np.frombuffer(raw[y_size : y_size + c_size], dtype=np.uint8).reshape(c_height, c_width)
            v = np.frombuffer(raw[y_size + c_size :], dtype=np.uint8).reshape(c_height, c_width)
            y_out = cv2.warpAffine(
                y, matrix_y, (args.width, args.height),
                flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
                borderMode=cv2.BORDER_CONSTANT, borderValue=16,
            )
            u_out = cv2.warpAffine(
                u, matrix_c, (c_width, c_height),
                flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
                borderMode=cv2.BORDER_CONSTANT, borderValue=128,
            )
            v_out = cv2.warpAffine(
                v, matrix_c, (c_width, c_height),
                flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
                borderMode=cv2.BORDER_CONSTANT, borderValue=128,
            )
            dst.write(y_out.tobytes())
            dst.write(u_out.tobytes())
            dst.write(v_out.tobytes())
    print(f"frames_written: {frame_count}")
    print("dst_to_src_matrix: " + ",".join(f"{value:.9f}" for value in matrix_y.reshape(-1)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
