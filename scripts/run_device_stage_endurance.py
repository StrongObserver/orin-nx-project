from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import statistics
import subprocess
import time
from pathlib import Path


PATTERNS = {
    "egl": re.compile(
        r"EGL_STAGE_TIMING frame=100 .*?wrapper_call_ms=([0-9.]+)"
        r".*?total_stage_ms=([0-9.]+).*?avg_total_stage_ms=([0-9.]+)"
    ),
    "stream": re.compile(
        r"EGL_STAGE_TIMING frame=100 .*?wrapper_call_ms=([0-9.]+)"
        r".*?total_stage_ms=([0-9.]+).*?avg_total_stage_ms=([0-9.]+)"
    ),
    "nvbuf": re.compile(
        r"NVBUFFER_PAIR_STAGE_TIMING frame=100 .*?wrapper_call_ms=([0-9.]+)"
        r".*?total_stage_ms=([0-9.]+).*?avg_total_stage_ms=([0-9.]+)"
    ),
}

DEFAULT_BINARIES = {
    "egl": "_mmapi_work/jetson_multimedia_api/samples/99_vpi_transcode_matrix_eglimage/multivideo_transcode",
    "stream": "_mmapi_work/jetson_multimedia_api/samples/99_vpi_transcode_matrix_eglimage_stream_reuse/multivideo_transcode",
    "nvbuf": "_mmapi_work/jetson_multimedia_api/samples/99_vpi_transcode_matrix_nvbuffer_pair/multivideo_transcode",
}

TEGRATS_GR3D_RE = re.compile(r"GR3D_FREQ\s+(\d+)%")
TEGRATS_TEMP_RE = re.compile(r"([A-Za-z0-9_]+)@([0-9.]+)C")
HANDOFF_RE = re.compile(
    r"MATRIX_HANDOFF\s+frame=(?P<frame>\d+)\s+matrix_index=(?P<matrix_index>-?\d+)\s+"
    r"fallback=(?P<fallback>[01])\s+elapsed_us=(?P<elapsed>[0-9.]+)"
)
MATRIX_COUNT_RE = re.compile(r"VPI_MATRIX_LOADED\s+.*?\s+count=(\d+)")


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int((pct / 100.0) * (len(ordered) - 1) + 0.999999)
    index = max(0, min(index, len(ordered) - 1))
    return float(ordered[index])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run alternating MMAPI/VPI/NVENC device-stage paths and summarize endurance/tail metrics."
    )
    parser.add_argument("--root", type=Path, default=Path("/home/nvidia/orin-nx-project"))
    parser.add_argument(
        "--source",
        default="results/regular_gate_safe103_crop98_validation_20260720/regular_gate05_regular_6/source.h264",
    )
    parser.add_argument(
        "--matrix",
        default="results/regular_gate_nvbuffer_pair_resid_20260723/regular_gate05_regular_6/resid_r15_s07.csv",
    )
    parser.add_argument("--out-dir", default="results/device_stage_endurance_20260724/regular05")
    parser.add_argument("--paths", default="egl,stream,nvbuf")
    parser.add_argument("--runs", type=int, default=0, help="Runs per path. If 0, use --duration-sec.")
    parser.add_argument("--duration-sec", type=float, default=1200.0)
    parser.add_argument("--tegrastats", action="store_true")
    parser.add_argument("--tegrastats-interval-ms", type=int, default=1000)
    parser.add_argument("--expected-frames", type=int, default=180)
    parser.add_argument(
        "--retain-outputs",
        choices=["all", "samples", "failures"],
        default="samples",
        help="Keep every output, first/last-cycle samples, or failed outputs only.",
    )
    return parser.parse_args()


def start_tegrastats(out_dir: Path, interval_ms: int) -> subprocess.Popen[str] | None:
    if not (Path("/usr/bin/tegrastats").exists() or Path("/bin/tegrastats").exists()):
        return None
    log_path = out_dir / "tegrastats.log"
    return subprocess.Popen(
        ["tegrastats", "--interval", str(interval_ms)],
        stdout=log_path.open("w", encoding="utf-8"),
        stderr=subprocess.STDOUT,
        text=True,
    )


def stop_process(proc: subprocess.Popen[str] | None) -> None:
    if proc is None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def parse_handoff(log_text: str) -> dict[str, int]:
    samples = [match.groupdict() for match in HANDOFF_RE.finditer(log_text)]
    return {
        "handoff_samples": len(samples),
        "fallback_count": sum(int(sample["fallback"]) for sample in samples),
        "frame_index_mismatch_count": sum(
            1
            for sample in samples
            if int(sample["matrix_index"]) >= 0
            and int(sample["matrix_index"]) != int(sample["frame"]) - 1
        ),
        "max_handoff_frame": max((int(sample["frame"]) for sample in samples), default=0),
    }


def probe_frame_count(path: Path) -> tuple[int, int]:
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None or not path.exists() or path.stat().st_size == 0:
        return 0, 0
    proc = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-count_frames",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=nb_read_frames",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        return 0, 0
    try:
        return 1, int(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return 0, 0


def classify_failure(
    return_code: int,
    success: bool,
    handoff: dict[str, int],
    handoff_required: bool,
    readable: int,
    frame_count: int,
    expected_frames: int,
    timing_required: bool,
    timing_present: bool,
) -> str:
    reasons: list[str] = []
    if return_code != 0:
        reasons.append(f"rc={return_code}")
    if not success:
        reasons.append("success_marker_missing")
    if handoff_required and handoff["handoff_samples"] == 0:
        reasons.append("handoff_instrumentation_missing")
    if handoff["fallback_count"]:
        reasons.append(f"fallback={handoff['fallback_count']}")
    if handoff["frame_index_mismatch_count"]:
        reasons.append(f"mismatch={handoff['frame_index_mismatch_count']}")
    if not readable:
        reasons.append("output_unreadable")
    elif expected_frames > 0 and frame_count != expected_frames:
        reasons.append(f"frames={frame_count}")
    if timing_required and not timing_present:
        reasons.append("stage_timing_missing")
    return ";".join(reasons)


def run_one(
    root: Path,
    out_dir: Path,
    name: str,
    run_index: int,
    sequence: int,
    order_position: int,
    source: str,
    matrix: str,
    expected_frames: int,
) -> dict[str, object]:
    binary = root / DEFAULT_BINARIES[name]
    output_path = out_dir / f"{name}_{run_index:04d}.h264"
    log_path = out_dir / f"{name}_{run_index:04d}.log"
    env = os.environ.copy()
    env["VPI_MATRIX_CSV"] = str(root / matrix)
    command = [
        str(binary),
        "num_files",
        "1",
        str(root / source),
        "H264",
        str(output_path),
        "H264",
    ]
    started = time.perf_counter()
    proc = subprocess.run(
        command,
        cwd=root,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    wall_s = time.perf_counter() - started
    log_path.write_text(proc.stdout, encoding="utf-8")
    match = PATTERNS[name].search(proc.stdout)
    wrapper_ms = stage100_ms = stageavg_ms = ""
    if match:
        wrapper_ms = f"{float(match.group(1)):.6f}"
        stage100_ms = f"{float(match.group(2)):.6f}"
        stageavg_ms = f"{float(match.group(3)):.6f}"
    handoff = parse_handoff(proc.stdout)
    matrix_match = MATRIX_COUNT_RE.search(proc.stdout)
    matrix_count = int(matrix_match.group(1)) if matrix_match else 0
    readable, frame_count = probe_frame_count(output_path)
    success = "App run was successful" in proc.stdout
    failure_reason = classify_failure(
        return_code=proc.returncode,
        success=success,
        handoff=handoff,
        handoff_required=True,
        readable=readable,
        frame_count=frame_count,
        expected_frames=expected_frames,
        timing_required=name != "egl",
        timing_present=match is not None,
    )
    return {
        "path": name,
        "run": run_index,
        "sequence": sequence,
        "order_position": order_position,
        "rc": proc.returncode,
        "success": int(success),
        **handoff,
        "matrix_count": matrix_count,
        "readable": readable,
        "frame_count": frame_count,
        "failure_reason": failure_reason,
        "wall_s": f"{wall_s:.6f}",
        "wrapper_ms": wrapper_ms,
        "stage100_ms": stage100_ms,
        "stageavg_ms": stageavg_ms,
        "bytes": output_path.stat().st_size if output_path.exists() else 0,
    }


def summarize_path(name: str, rows: list[dict[str, object]]) -> dict[str, object]:
    group = [row for row in rows if row["path"] == name]
    item: dict[str, object] = {
        "path": name,
        "runs": len(group),
        "rc0": sum(1 for row in group if int(row["rc"]) == 0),
        "success": sum(int(row["success"]) for row in group),
        "fallback_total": sum(int(row["fallback_count"]) for row in group),
        "mismatch_total": sum(int(row["frame_index_mismatch_count"]) for row in group),
        "readable": sum(int(row["readable"]) for row in group),
        "frame_count_ok": sum(
            1 for row in group if int(row["frame_count"]) > 0 and not str(row["failure_reason"])
        ),
        "failed_runs": sum(1 for row in group if str(row["failure_reason"])),
    }
    for key in ["wall_s", "wrapper_ms", "stage100_ms", "stageavg_ms"]:
        values = [float(row[key]) for row in group if row[key] != ""]
        item[f"{key}_mean"] = f"{statistics.mean(values):.6f}" if values else ""
        item[f"{key}_p50"] = f"{statistics.median(values):.6f}" if values else ""
        item[f"{key}_p95"] = f"{percentile(values, 95):.6f}" if values else ""
        item[f"{key}_p99"] = f"{percentile(values, 99):.6f}" if values else ""
    return item


def parse_tegrastats(out_dir: Path) -> dict[str, object]:
    log_path = out_dir / "tegrastats.log"
    if not log_path.exists():
        return {
            "tegrastats_samples": 0,
            "gr3d_avg_pct": "",
            "gr3d_max_pct": "",
            "cpu_temp_max_c": "",
            "gpu_temp_max_c": "",
        }
    gr3d_values: list[float] = []
    cpu_temps: list[float] = []
    gpu_temps: list[float] = []
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        gr3d_match = TEGRATS_GR3D_RE.search(line)
        if gr3d_match:
            gr3d_values.append(float(gr3d_match.group(1)))
        for name, value in TEGRATS_TEMP_RE.findall(line):
            if name.lower().startswith("cpu"):
                cpu_temps.append(float(value))
            if name.lower().startswith("gpu"):
                gpu_temps.append(float(value))
    return {
        "tegrastats_samples": len(gr3d_values),
        "gr3d_avg_pct": f"{statistics.mean(gr3d_values):.3f}" if gr3d_values else "",
        "gr3d_max_pct": f"{max(gr3d_values):.3f}" if gr3d_values else "",
        "cpu_temp_max_c": f"{max(cpu_temps):.3f}" if cpu_temps else "",
        "gpu_temp_max_c": f"{max(gpu_temps):.3f}" if gpu_temps else "",
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    root = args.root
    out_dir = root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = [item.strip() for item in args.paths.split(",") if item.strip()]
    for path in paths:
        if path not in DEFAULT_BINARIES:
            raise ValueError(f"unsupported path: {path}")

    tegra_proc = start_tegrastats(out_dir, args.tegrastats_interval_ms) if args.tegrastats else None
    rows: list[dict[str, object]] = []
    started = time.perf_counter()
    run_index = 1
    sequence = 1
    try:
        while True:
            if args.runs > 0 and run_index > args.runs:
                break
            if args.runs <= 0 and rows and (time.perf_counter() - started) >= args.duration_sec:
                break
            offset = (run_index - 1) % len(paths)
            cycle_paths = paths[offset:] + paths[:offset]
            for order_position, name in enumerate(cycle_paths, start=1):
                row = run_one(
                    root,
                    out_dir,
                    name,
                    run_index,
                    sequence,
                    order_position,
                    args.source,
                    args.matrix,
                    args.expected_frames,
                )
                rows.append(row)
                print(row, flush=True)
                sequence += 1
            run_index += 1
    finally:
        stop_process(tegra_proc)

    final_cycle = run_index - 1
    if args.retain_outputs != "all":
        for row in rows:
            keep = bool(str(row["failure_reason"]))
            if args.retain_outputs == "samples":
                keep = keep or int(row["run"]) in {1, final_cycle}
            if not keep:
                (out_dir / f"{row['path']}_{int(row['run']):04d}.h264").unlink(missing_ok=True)

    summary = [summarize_path(name, rows) for name in paths]
    tegra = parse_tegrastats(out_dir)
    for row in summary:
        row.update(tegra)
        row["duration_wall_sec"] = f"{time.perf_counter() - started:.6f}"

    write_csv(out_dir / "endurance_metrics.csv", rows)
    write_csv(out_dir / "endurance_summary.csv", summary)
    print("SUMMARY")
    for row in summary:
        print(row)

    failed = [row for row in rows if str(row["failure_reason"])]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
