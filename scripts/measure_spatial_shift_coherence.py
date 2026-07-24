from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import cv2
import numpy as np


IMAGE_SUFFIXES = {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}


def read_gray_frames(path: Path, max_frames: int) -> list[np.ndarray]:
    if path.suffix.lower() in IMAGE_SUFFIXES:
        image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise RuntimeError(f"Cannot read image: {path}")
        return [image.astype(np.float32)]

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"Cannot open video: {path}")
    frames: list[np.ndarray] = []
    while not max_frames or len(frames) < max_frames:
        ok, frame = capture.read()
        if not ok:
            break
        frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32))
    capture.release()
    if not frames:
        raise RuntimeError(f"No frames read: {path}")
    return frames


def band_bounds(height: int, bands_y: int, margin: int) -> list[tuple[int, int]]:
    inner_top = margin
    inner_bottom = height - margin
    if inner_bottom - inner_top < bands_y * 16:
        raise ValueError("Frame is too short for the requested margin and band count")
    edges = np.linspace(inner_top, inner_bottom, bands_y + 1, dtype=np.int32)
    return [(int(edges[index]), int(edges[index + 1])) for index in range(bands_y)]


def estimate_shift(reference: np.ndarray, candidate: np.ndarray) -> tuple[float, float, float]:
    if reference.shape != candidate.shape:
        raise ValueError(f"Shape mismatch: {reference.shape} vs {candidate.shape}")
    height, width = reference.shape
    window = cv2.createHanningWindow((width, height), cv2.CV_32F)
    shift, response = cv2.phaseCorrelate(reference * window, candidate * window)
    return float(shift[0]), float(shift[1]), float(response)


def measure(
    reference_frames: list[np.ndarray],
    candidate_frames: list[np.ndarray],
    *,
    bands_y: int,
    margin: int,
    expected_shift_x: float,
    expected_shift_y: float,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    frame_count = min(len(reference_frames), len(candidate_frames))
    if frame_count == 0:
        raise ValueError("No overlapping frames")
    rows: list[dict[str, object]] = []
    frame_shift_spread: list[float] = []
    frame_expected_error: list[float] = []
    frame_reference_mae: list[float] = []
    responses: list[float] = []

    for frame_index in range(frame_count):
        reference = reference_frames[frame_index]
        candidate = candidate_frames[frame_index]
        if reference.shape != candidate.shape:
            raise ValueError(
                f"Frame {frame_index} shape mismatch: {reference.shape} vs {candidate.shape}"
            )
        height, width = reference.shape
        if margin * 2 >= width:
            raise ValueError("Margin removes the whole frame width")
        expected = cv2.warpAffine(
            reference,
            np.asarray(
                [[1.0, 0.0, expected_shift_x], [0.0, 1.0, expected_shift_y]],
                dtype=np.float32,
            ),
            (width, height),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
        shifts: list[tuple[float, float]] = []
        reference_mae: list[float] = []
        for band_index, (top, bottom) in enumerate(band_bounds(height, bands_y, margin)):
            reference_band = reference[top:bottom, margin : width - margin]
            candidate_band = candidate[top:bottom, margin : width - margin]
            expected_band = expected[top:bottom, margin : width - margin]
            shift_x, shift_y, response = estimate_shift(reference_band, candidate_band)
            error = float(
                np.hypot(shift_x - expected_shift_x, shift_y - expected_shift_y)
            )
            expected_reference_mae = float(
                np.mean(np.abs(candidate_band - expected_band))
            )
            rows.append(
                {
                    "frame": frame_index,
                    "band": band_index,
                    "top": top,
                    "bottom": bottom,
                    "shift_x": f"{shift_x:.6f}",
                    "shift_y": f"{shift_y:.6f}",
                    "response": f"{response:.6f}",
                    "expected_error_px": f"{error:.6f}",
                    "expected_reference_mae": f"{expected_reference_mae:.6f}",
                }
            )
            shifts.append((shift_x, shift_y))
            reference_mae.append(expected_reference_mae)
            responses.append(response)

        shift_array = np.asarray(shifts, dtype=np.float64)
        center = np.median(shift_array, axis=0)
        spread = np.linalg.norm(shift_array - center, axis=1)
        errors = np.linalg.norm(
            shift_array - np.asarray([expected_shift_x, expected_shift_y]), axis=1
        )
        frame_shift_spread.append(float(np.percentile(spread, 95)))
        frame_expected_error.append(float(np.percentile(errors, 95)))
        frame_reference_mae.append(float(np.percentile(reference_mae, 95)))

    spread_array = np.asarray(frame_shift_spread, dtype=np.float64)
    error_array = np.asarray(frame_expected_error, dtype=np.float64)
    reference_mae_array = np.asarray(frame_reference_mae, dtype=np.float64)
    response_array = np.asarray(responses, dtype=np.float64)
    summary: dict[str, object] = {
        "frames_compared": frame_count,
        "bands_y": bands_y,
        "margin_px": margin,
        "expected_shift_x": expected_shift_x,
        "expected_shift_y": expected_shift_y,
        "band_shift_spread_p95_px": float(np.percentile(spread_array, 95)),
        "band_shift_spread_max_px": float(spread_array.max()),
        "expected_shift_error_p95_px": float(np.percentile(error_array, 95)),
        "expected_shift_error_max_px": float(error_array.max()),
        "expected_reference_mae_p95": float(np.percentile(reference_mae_array, 95)),
        "expected_reference_mae_max": float(reference_mae_array.max()),
        "phase_response_p05": float(np.percentile(response_array, 5)),
        "phase_response_mean": float(response_array.mean()),
    }
    return rows, summary


def write_outputs(
    out_dir: Path,
    rows: list[dict[str, object]],
    summary: dict[str, object],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "band_shifts.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    with (out_dir / "summary.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(summary.keys()))
        writer.writeheader()
        writer.writerow(summary)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Measure whether a translated output has one coherent full-frame shift "
            "instead of band-dependent block displacement."
        )
    )
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--max-frames", type=int, default=30)
    parser.add_argument("--bands-y", type=int, default=8)
    parser.add_argument("--margin", type=int, default=32)
    parser.add_argument("--expected-shift-x", type=float, default=0.0)
    parser.add_argument("--expected-shift-y", type=float, default=0.0)
    parser.add_argument("--max-spread-p95", type=float, default=2.0)
    parser.add_argument("--max-expected-error-p95", type=float, default=3.0)
    parser.add_argument("--max-expected-reference-mae-p95", type=float, default=15.0)
    parser.add_argument("--min-response-p05", type=float, default=0.05)
    args = parser.parse_args()

    rows, summary = measure(
        read_gray_frames(args.reference, args.max_frames),
        read_gray_frames(args.candidate, args.max_frames),
        bands_y=args.bands_y,
        margin=args.margin,
        expected_shift_x=args.expected_shift_x,
        expected_shift_y=args.expected_shift_y,
    )
    summary["spread_gate"] = (
        "pass"
        if float(summary["band_shift_spread_p95_px"]) <= args.max_spread_p95
        else "fail"
    )
    summary["expected_shift_gate"] = (
        "pass"
        if float(summary["expected_shift_error_p95_px"])
        <= args.max_expected_error_p95
        else "fail"
    )
    summary["response_gate"] = (
        "pass"
        if float(summary["phase_response_p05"]) >= args.min_response_p05
        else "fail"
    )
    summary["expected_reference_gate"] = (
        "pass"
        if float(summary["expected_reference_mae_p95"])
        <= args.max_expected_reference_mae_p95
        else "fail"
    )
    summary["coherence_status"] = (
        "pass"
        if summary["spread_gate"] == "pass"
        and summary["expected_shift_gate"] == "pass"
        and summary["response_gate"] == "pass"
        and summary["expected_reference_gate"] == "pass"
        else "fail"
    )
    write_outputs(args.out_dir, rows, summary)
    for key, value in summary.items():
        print(f"{key}: {value}")
    return 0 if summary["coherence_status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
