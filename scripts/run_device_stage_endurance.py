from __future__ import annotations

import argparse
import csv
import os
import re
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


def run_one(root: Path, out_dir: Path, name: str, run_index: int, source: str, matrix: str) -> dict[str, object]:
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
    return {
        "path": name,
        "run": run_index,
        "rc": proc.returncode,
        "success": int("App run was successful" in proc.stdout),
        "fallback_count": proc.stdout.count("fallback=1"),
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
    try:
        while True:
            if args.runs > 0 and run_index > args.runs:
                break
            if args.runs <= 0 and rows and (time.perf_counter() - started) >= args.duration_sec:
                break
            for name in paths:
                row = run_one(root, out_dir, name, run_index, args.source, args.matrix)
                rows.append(row)
                print(row, flush=True)
            run_index += 1
    finally:
        stop_process(tegra_proc)

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

    failed = [row for row in rows if int(row["rc"]) != 0 or int(row["success"]) != 1]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
