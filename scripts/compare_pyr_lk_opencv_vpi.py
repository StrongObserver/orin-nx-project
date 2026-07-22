from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
from pathlib import Path

import cv2
import numpy as np
import vpi


def percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * ratio))))
    return float(ordered[index])


def mean(values: list[float]) -> float:
    return float(statistics.mean(values)) if values else 0.0


def read_gray_frames(path: Path, max_frames: int, estimate_scale: float) -> list[np.ndarray]:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open input video: {path}")
    frames: list[np.ndarray] = []
    while len(frames) < max_frames:
        ok, frame = cap.read()
        if not ok:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if estimate_scale != 1.0:
            gray = cv2.resize(gray, None, fx=estimate_scale, fy=estimate_scale, interpolation=cv2.INTER_AREA)
        frames.append(gray)
    cap.release()
    if len(frames) < 2:
        raise RuntimeError("Need at least two frames")
    return frames


def make_keypoints(frame: np.ndarray, max_points: int) -> np.ndarray:
    pts = cv2.goodFeaturesToTrack(frame, maxCorners=max_points, qualityLevel=0.01, minDistance=8)
    if pts is None:
        raise RuntimeError("No keypoints found")
    return pts.reshape(-1, 2).astype(np.float32)


def run_opencv(frames: list[np.ndarray], keypoints: np.ndarray, warmup_pairs: int) -> tuple[dict, list[dict], list[np.ndarray]]:
    timings: list[float] = []
    rows: list[dict] = []
    outputs: list[np.ndarray] = []
    prev_pts = keypoints.reshape(-1, 1, 2)
    for index in range(1, len(frames)):
        started = time.perf_counter()
        next_pts, status, _ = cv2.calcOpticalFlowPyrLK(frames[index - 1], frames[index], prev_pts, None)
        elapsed = (time.perf_counter() - started) * 1000.0
        valid = status.reshape(-1).astype(bool) if status is not None else np.zeros(len(keypoints), dtype=bool)
        pts = next_pts.reshape(-1, 2).astype(np.float32) if next_pts is not None else np.zeros_like(keypoints)
        outputs.append(pts)
        if index > warmup_pairs:
            timings.append(elapsed)
        rows.append(
            {
                "pair_index": index,
                "backend": "opencv_cpu",
                "elapsed_ms": f"{elapsed:.6f}",
                "valid_points": int(valid.sum()),
            }
        )
        prev_pts = next_pts if next_pts is not None else prev_pts
    return summarize("opencv_cpu", timings, rows), rows, outputs


def make_vpi_keypoints(keypoints: np.ndarray):
    type_candidates = [
        getattr(getattr(vpi, "Type", object), "KEYPOINT_F32", None),
        getattr(vpi, "KeypointF32", None),
        getattr(getattr(vpi, "Type", object), "F32", None),
        None,
    ]
    last_error = ""
    for type_candidate in type_candidates:
        try:
            if type_candidate is None:
                return vpi.asarray(keypoints)
            return vpi.asarray(keypoints, type_candidate)
        except Exception as exc:  # noqa: BLE001 - support probe.
            last_error = repr(exc)
    raise RuntimeError(last_error)


def vpi_result_to_arrays(result, fallback_count: int) -> tuple[np.ndarray | None, np.ndarray | None, int]:
    candidates = result if isinstance(result, tuple) else (result,)
    arrays: list[np.ndarray] = []
    for item in candidates:
        if hasattr(item, "rlock_cpu"):
            try:
                with item.rlock_cpu() as data:
                    arr = np.array(data, copy=True)
                arrays.append(arr)
            except Exception:
                continue

    points = None
    status = None
    for arr in arrays:
        if arr.ndim >= 2 and arr.shape[-1] == 2:
            points = arr.reshape(-1, 2).astype(np.float32)
        elif arr.ndim >= 1:
            flat = arr.reshape(-1)
            if flat.size:
                status = flat.astype(np.int32)
    if points is None:
        return None, status, fallback_count + 1
    return points, status, fallback_count


def run_vpi(
    frames: list[np.ndarray],
    keypoints: np.ndarray,
    backend_name: str,
    backend,
    warmup_pairs: int,
) -> tuple[dict, list[dict], list[np.ndarray | None]]:
    rows: list[dict] = []
    timings: list[float] = []
    outputs: list[np.ndarray | None] = []
    fallback_count = 0
    try:
        prev = vpi.asimage(frames[0], vpi.Format.U8)
        vpi_keypoints = make_vpi_keypoints(keypoints)
        kptstatus = vpi.asarray(np.zeros((len(keypoints),), dtype=np.uint8))
        tracker = vpi.OpticalFlowPyrLK(prev, vpi_keypoints, 3, kptstatus=kptstatus, backend=backend)
    except Exception as exc:  # noqa: BLE001 - support probe.
        return {
            "backend": backend_name,
            "status": "fail_init",
            "pairs": 0,
            "avg_ms": "",
            "p90_ms": "",
            "valid_points_avg": "",
            "detail": repr(exc),
        }, rows, outputs

    for index in range(1, len(frames)):
        curr = vpi.asimage(frames[index], vpi.Format.U8)
        started = time.perf_counter()
        try:
            result = tracker(curr)
            arr, status, fallback_count = vpi_result_to_arrays(result, fallback_count)
            elapsed = (time.perf_counter() - started) * 1000.0
            outputs.append(arr)
            valid_points = ""
            if arr is not None:
                valid_points = len(arr)
            if status is not None:
                # VPI status uses 0 for tracked, non-zero for lost.
                valid_points = int((status[: len(keypoints)] == 0).sum())
            if index > warmup_pairs:
                timings.append(elapsed)
            rows.append(
                {
                    "pair_index": index,
                    "backend": backend_name,
                    "elapsed_ms": f"{elapsed:.6f}",
                    "valid_points": valid_points,
                }
            )
        except Exception as exc:  # noqa: BLE001 - support probe.
            return {
                "backend": backend_name,
                "status": "fail_runtime",
                "pairs": len(timings),
                "avg_ms": f"{mean(timings):.3f}" if timings else "",
                "p90_ms": f"{percentile(timings, 0.90):.3f}" if timings else "",
                "valid_points_avg": "",
                "detail": repr(exc),
            }, rows, outputs

    summary = summarize(backend_name, timings, rows)
    summary["fallback_result_readbacks"] = fallback_count
    return summary, rows, outputs


def summarize(backend: str, timings: list[float], rows: list[dict]) -> dict:
    valid_counts = [int(row["valid_points"]) for row in rows if str(row.get("valid_points", "")).isdigit()]
    return {
        "backend": backend,
        "status": "pass",
        "pairs": len(timings),
        "avg_ms": f"{mean(timings):.3f}",
        "p90_ms": f"{percentile(timings, 0.90):.3f}",
        "valid_points_avg": f"{mean(valid_counts):.3f}" if valid_counts else "",
        "detail": "",
    }


def compare_outputs(reference: list[np.ndarray], candidate: list[np.ndarray | None], backend: str) -> dict:
    diffs: list[float] = []
    compared = 0
    for ref, cand in zip(reference, candidate):
        if cand is None:
            continue
        count = min(len(ref), len(cand))
        if count == 0:
            continue
        delta = np.linalg.norm(ref[:count] - cand[:count], axis=1)
        diffs.extend(float(x) for x in delta)
        compared += 1
    return {
        "backend": backend,
        "pairs_compared": compared,
        "point_error_mean_px": f"{mean(diffs):.6f}" if diffs else "",
        "point_error_p95_px": f"{percentile(diffs, 0.95):.6f}" if diffs else "",
        "point_error_max_px": f"{max(diffs):.6f}" if diffs else "",
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare OpenCV PyrLK against VPI PyrLK on identical keypoints.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--max-frames", type=int, default=40)
    parser.add_argument("--warmup-pairs", type=int, default=3)
    parser.add_argument("--max-points", type=int, default=200)
    parser.add_argument("--estimate-scale", type=float, default=1.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    frames = read_gray_frames(args.input, args.max_frames, args.estimate_scale)
    keypoints = make_keypoints(frames[0], args.max_points)

    summaries: list[dict] = []
    event_rows: list[dict] = []
    diff_rows: list[dict] = []

    cv_summary, cv_rows, cv_outputs = run_opencv(frames, keypoints, args.warmup_pairs)
    summaries.append(cv_summary)
    event_rows.extend(cv_rows)

    for backend_name, backend in {"vpi_cpu": vpi.Backend.CPU, "vpi_cuda": vpi.Backend.CUDA}.items():
        summary, rows, outputs = run_vpi(frames, keypoints, backend_name, backend, args.warmup_pairs)
        summaries.append(summary)
        event_rows.extend(rows)
        diff_rows.append(compare_outputs(cv_outputs, outputs, backend_name))

    raw = {
        "input": str(args.input),
        "frames": len(frames),
        "keypoints": len(keypoints),
        "estimate_scale": args.estimate_scale,
        "summaries": summaries,
        "diffs": diff_rows,
    }
    write_csv(args.out_dir / "pyr_lk_summary.csv", summaries)
    write_csv(args.out_dir / "pyr_lk_events.csv", event_rows)
    write_csv(args.out_dir / "pyr_lk_point_diff.csv", diff_rows)
    (args.out_dir / "probe_raw.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"summary: {args.out_dir / 'pyr_lk_summary.csv'}")
    print(f"diff: {args.out_dir / 'pyr_lk_point_diff.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
