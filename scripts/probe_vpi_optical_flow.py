from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np


BACKENDS = ["cpu", "cuda", "pva", "vic", "ofa"]


def percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * ratio))))
    return float(ordered[index])


def mean(values: list[float]) -> float:
    return float(statistics.mean(values)) if values else 0.0


def status_row(operator: str, backend: str, status: str, detail: str = "", timings: list[float] | None = None) -> dict:
    timings = timings or []
    return {
        "operator": operator,
        "backend": backend,
        "status": status,
        "frames": len(timings),
        "avg_ms": f"{mean(timings):.3f}" if timings else "",
        "p90_ms": f"{percentile(timings, 0.90):.3f}" if timings else "",
        "detail": detail.replace("\n", " ")[:400],
    }


def read_gray_frames(input_path: Path, max_frames: int) -> list[np.ndarray]:
    cap = cv2.VideoCapture(str(input_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open input video: {input_path}")
    frames: list[np.ndarray] = []
    while len(frames) < max_frames:
        ok, frame = cap.read()
        if not ok:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frames.append(gray)
    cap.release()
    if len(frames) < 2:
        raise RuntimeError(f"Need at least two frames: {input_path}")
    return frames


def backend_map(vpi) -> dict:
    return {
        "cpu": getattr(vpi.Backend, "CPU", None),
        "cuda": getattr(vpi.Backend, "CUDA", None),
        "pva": getattr(vpi.Backend, "PVA", None),
        "vic": getattr(vpi.Backend, "VIC", None),
        "ofa": getattr(vpi.Backend, "OFA", None),
    }


def probe_dense(vpi, frames: list[np.ndarray], backend_name: str, backend, warmup: int) -> tuple[dict, list[dict]]:
    rows = []
    timings: list[float] = []
    raw_events: list[dict] = []
    if backend is None:
        return status_row("dense_optical_flow", backend_name, "api_missing", "Backend enum missing"), raw_events

    try:
        prev = vpi.asimage(frames[0], vpi.Format.U8)
        curr = vpi.asimage(frames[1], vpi.Format.U8)
        with backend:
            out = vpi.optflow_dense(prev, curr, quality=vpi.OptFlowQuality.LOW)
        with out.rlock_cpu() as _:
            pass
    except Exception as exc:  # noqa: BLE001 - support probe.
        return status_row("dense_optical_flow", backend_name, "fail_init_or_first_call", repr(exc)), raw_events

    for index in range(1, len(frames)):
        prev = vpi.asimage(frames[index - 1], vpi.Format.U8)
        curr = vpi.asimage(frames[index], vpi.Format.U8)
        started = time.perf_counter()
        try:
            with backend:
                out = vpi.optflow_dense(prev, curr, quality=vpi.OptFlowQuality.LOW)
            with out.rlock_cpu() as _:
                pass
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            raw_events.append({"pair_index": index, "backend": backend_name, "elapsed_ms": elapsed_ms, "status": "pass"})
            if index > warmup:
                timings.append(elapsed_ms)
        except Exception as exc:  # noqa: BLE001 - support probe.
            raw_events.append({"pair_index": index, "backend": backend_name, "status": "fail", "detail": repr(exc)})
            return status_row("dense_optical_flow", backend_name, "fail_runtime", repr(exc), timings), raw_events
    return status_row("dense_optical_flow", backend_name, "pass", timings=timings), raw_events


def make_keypoints(frame: np.ndarray, max_points: int) -> np.ndarray:
    points = cv2.goodFeaturesToTrack(frame, maxCorners=max_points, qualityLevel=0.01, minDistance=8)
    if points is None:
        points = np.array([[[frame.shape[1] / 2.0, frame.shape[0] / 2.0]]], dtype=np.float32)
    points = points.reshape(-1, 2).astype(np.float32)
    return points


def probe_pyr_lk(vpi, frames: list[np.ndarray], backend_name: str, backend, warmup: int, max_points: int) -> tuple[dict, list[dict]]:
    raw_events: list[dict] = []
    timings: list[float] = []
    if backend is None:
        return status_row("pyramidal_lk_optical_flow", backend_name, "api_missing", "Backend enum missing"), raw_events

    keypoints_np = make_keypoints(frames[0], max_points)
    type_candidates = [
        getattr(getattr(vpi, "Type", object), "KEYPOINT_F32", None),
        getattr(vpi, "KeypointF32", None),
        getattr(getattr(vpi, "Type", object), "F32", None),
        None,
    ]
    last_error = ""
    keypoints = None
    for type_candidate in type_candidates:
        try:
            if type_candidate is None:
                keypoints = vpi.asarray(keypoints_np)
            else:
                keypoints = vpi.asarray(keypoints_np, type_candidate)
            break
        except Exception as exc:  # noqa: BLE001 - support probe.
            last_error = repr(exc)
            keypoints = None
    if keypoints is None:
        return status_row("pyramidal_lk_optical_flow", backend_name, "fail_keypoint_array", last_error), raw_events

    try:
        prev = vpi.asimage(frames[0], vpi.Format.U8)
        tracker = vpi.OpticalFlowPyrLK(prev, keypoints, 3, backend=backend)
    except Exception as exc:  # noqa: BLE001 - support probe.
        return status_row("pyramidal_lk_optical_flow", backend_name, "fail_payload_create", repr(exc)), raw_events

    for index in range(1, len(frames)):
        curr = vpi.asimage(frames[index], vpi.Format.U8)
        started = time.perf_counter()
        try:
            result = tracker(curr)
            # Result type varies by VPI version. Force synchronization/readback where possible.
            if isinstance(result, tuple):
                for item in result:
                    if hasattr(item, "rlock_cpu"):
                        with item.rlock_cpu() as _:
                            pass
            elif hasattr(result, "rlock_cpu"):
                with result.rlock_cpu() as _:
                    pass
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            raw_events.append({"pair_index": index, "backend": backend_name, "elapsed_ms": elapsed_ms, "status": "pass"})
            if index > warmup:
                timings.append(elapsed_ms)
        except Exception as exc:  # noqa: BLE001 - support probe.
            raw_events.append({"pair_index": index, "backend": backend_name, "status": "fail", "detail": repr(exc)})
            return status_row("pyramidal_lk_optical_flow", backend_name, "fail_runtime", repr(exc), timings), raw_events
    return status_row("pyramidal_lk_optical_flow", backend_name, "pass", f"keypoints={len(keypoints_np)}", timings), raw_events


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["operator", "backend", "status", "frames", "avg_ms", "p90_ms", "detail"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(path: Path, rows: list[dict], input_path: Path, frame_count: int) -> None:
    lines = [
        "# VPI Optical Flow Probe",
        "",
        f"- input: `{input_path}`",
        f"- frames read: {frame_count}",
        "",
        "| Operator | Backend | Status | Frames | Avg ms | P90 ms | Detail |",
        "|---|---|---|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['operator']} | {row['backend']} | {row['status']} | {row['frames']} | {row['avg_ms']} | {row['p90_ms']} | {row['detail']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `pass` means the minimal Python VPI path ran on this Jetson.",
            "- `fail_*` means the API/backend path needs either a different data format, a different binding pattern, or C++ sample verification.",
            "- These numbers are host-observed probe timings, not final EIS module speedups.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe VPI dense optical flow and pyramidal LK optical flow on Jetson.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--max-frames", type=int, default=40)
    parser.add_argument("--warmup-pairs", type=int, default=3)
    parser.add_argument("--max-points", type=int, default=200)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    import vpi

    frames = read_gray_frames(args.input, args.max_frames)
    backends = backend_map(vpi)
    rows: list[dict] = []
    raw_events: list[dict] = []

    for backend_name in BACKENDS:
        row, events = probe_dense(vpi, frames, backend_name, backends.get(backend_name), args.warmup_pairs)
        rows.append(row)
        raw_events.extend({"operator": "dense_optical_flow", **event} for event in events)

    for backend_name in BACKENDS:
        row, events = probe_pyr_lk(
            vpi,
            frames,
            backend_name,
            backends.get(backend_name),
            args.warmup_pairs,
            args.max_points,
        )
        rows.append(row)
        raw_events.extend({"operator": "pyramidal_lk_optical_flow", **event} for event in events)

    raw = {
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "input": str(args.input),
        "frames": len(frames),
        "rows": rows,
        "events": raw_events,
    }
    write_csv(args.out_dir / "vpi_optical_flow_probe.csv", rows)
    write_summary(args.out_dir / "summary.md", rows, args.input, len(frames))
    (args.out_dir / "probe_raw.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"summary: {args.out_dir / 'summary.md'}")
    print(f"csv: {args.out_dir / 'vpi_optical_flow_probe.csv'}")
    print(f"raw: {args.out_dir / 'probe_raw.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
