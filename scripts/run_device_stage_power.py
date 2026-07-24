from __future__ import annotations

import argparse
import base64
import csv
import os
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path


DEFAULT_BINARIES = {
    "egl": "_mmapi_work/jetson_multimedia_api/samples/99_vpi_transcode_matrix_eglimage/multivideo_transcode",
    "stream": "_mmapi_work/jetson_multimedia_api/samples/99_vpi_transcode_matrix_eglimage_stream_reuse/multivideo_transcode",
    "nvbuf": "_mmapi_work/jetson_multimedia_api/samples/99_vpi_transcode_matrix_nvbuffer_pair/multivideo_transcode",
}
HANDOFF_RE = re.compile(
    r"MATRIX_HANDOFF\s+frame=(?P<frame>\d+)\s+matrix_index=(?P<matrix_index>-?\d+)\s+"
    r"fallback=(?P<fallback>[01])"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run interleaved device-stage blocks while sampling INA3221 rails."
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
    parser.add_argument("--out-dir", default="results/device_stage_power_20260724/interleaved")
    parser.add_argument("--paths", default="egl,stream,nvbuf")
    parser.add_argument("--blocks", type=int, default=3, help="Blocks per path.")
    parser.add_argument("--runs-per-block", type=int, default=3)
    parser.add_argument("--sample-interval", type=float, default=0.1)
    parser.add_argument("--expected-frames", type=int, default=180)
    return parser.parse_args()


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int((pct / 100.0) * (len(ordered) - 1) + 0.999999)
    return ordered[max(0, min(index, len(ordered) - 1))]


def parse_handoff(text: str) -> tuple[int, int]:
    fallback = 0
    mismatch = 0
    for match in HANDOFF_RE.finditer(text):
        frame = int(match.group("frame"))
        matrix_index = int(match.group("matrix_index"))
        fallback += int(match.group("fallback"))
        if matrix_index >= 0 and matrix_index != frame - 1:
            mismatch += 1
    return fallback, mismatch


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def read_power_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def run_workload(
    root: Path,
    out_dir: Path,
    path_name: str,
    block_index: int,
    run_index: int,
    source: str,
    matrix: str,
    expected_frames: int,
) -> dict[str, object]:
    output = out_dir / f"{path_name}_b{block_index:02d}_r{run_index:02d}.h264"
    log = out_dir / f"{path_name}_b{block_index:02d}_r{run_index:02d}.log"
    env = os.environ.copy()
    env["VPI_MATRIX_CSV"] = str(root / matrix)
    command = [
        str(root / DEFAULT_BINARIES[path_name]),
        "num_files",
        "1",
        str(root / source),
        "H264",
        str(output),
        "H264",
    ]
    start_ms = int(time.time() * 1000)
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
    end_ms = int(time.time() * 1000)
    log.write_text(proc.stdout, encoding="utf-8")
    fallback, mismatch = parse_handoff(proc.stdout)
    success = int("App run was successful" in proc.stdout)
    reasons: list[str] = []
    if proc.returncode != 0:
        reasons.append(f"rc={proc.returncode}")
    if not success:
        reasons.append("success_marker_missing")
    if fallback:
        reasons.append(f"fallback={fallback}")
    if mismatch:
        reasons.append(f"mismatch={mismatch}")
    if not output.exists() or output.stat().st_size == 0:
        reasons.append("empty_output")
    return {
        "path": path_name,
        "block": block_index,
        "run": run_index,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "wall_s": f"{wall_s:.6f}",
        "rc": proc.returncode,
        "success": success,
        "fallback": fallback,
        "mismatch": mismatch,
        "expected_frames": expected_frames,
        "bytes": output.stat().st_size if output.exists() else 0,
        "failure_reason": ";".join(reasons),
    }


def main() -> int:
    args = parse_args()
    root = args.root
    out_dir = root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = [item.strip() for item in args.paths.split(",") if item.strip()]
    if not paths or any(path not in DEFAULT_BINARIES for path in paths):
        raise ValueError("unsupported --paths")

    encoded_password = sys.stdin.readline().strip()
    if not encoded_password:
        raise RuntimeError("expected base64 sudo password on stdin")
    sudo_password = base64.b64decode(encoded_password).decode("utf-8")
    validated = subprocess.run(
        ["sudo", "-S", "-p", "", "-v"],
        input=sudo_password + "\n",
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        check=False,
    )
    sudo_password = ""
    encoded_password = ""
    if validated.returncode != 0:
        raise RuntimeError(f"sudo validation failed: {validated.stderr.strip()}")

    power_csv = out_dir / "ina_power.csv"
    sampler = subprocess.Popen(
        [
            "sudo",
            "-n",
            "python3",
            str(root / "scripts/sample_ina_power.py"),
            "--out",
            str(power_csv),
            "--metadata-out",
            str(out_dir / "ina_metadata.json"),
            "--interval",
            str(args.sample_interval),
        ],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    time.sleep(max(0.3, args.sample_interval * 3))

    runs: list[dict[str, object]] = []
    blocks: list[dict[str, object]] = []
    try:
        for cycle in range(args.blocks):
            rotated = paths[cycle % len(paths) :] + paths[: cycle % len(paths)]
            for path_name in rotated:
                block_index = cycle + 1
                block_start_ms = int(time.time() * 1000)
                block_runs = []
                for run_index in range(1, args.runs_per_block + 1):
                    row = run_workload(
                        root,
                        out_dir,
                        path_name,
                        block_index,
                        run_index,
                        args.source,
                        args.matrix,
                        args.expected_frames,
                    )
                    runs.append(row)
                    block_runs.append(row)
                    print(row, flush=True)
                block_end_ms = int(time.time() * 1000)
                blocks.append(
                    {
                        "path": path_name,
                        "block": block_index,
                        "start_ms": block_start_ms,
                        "end_ms": block_end_ms,
                        "runs": len(block_runs),
                        "frames": args.expected_frames * len(block_runs),
                        "wall_s": f"{sum(float(row['wall_s']) for row in block_runs):.6f}",
                        "failed_runs": sum(1 for row in block_runs if row["failure_reason"]),
                    }
                )
    finally:
        subprocess.run(
            ["sudo", "-n", "kill", "-TERM", str(sampler.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        try:
            sampler.wait(timeout=5)
        except subprocess.TimeoutExpired:
            subprocess.run(
                ["sudo", "-n", "kill", "-KILL", str(sampler.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            sampler.wait(timeout=5)

    power_rows = read_power_rows(power_csv)
    for block in blocks:
        active = [
            row
            for row in power_rows
            if int(block["start_ms"]) <= int(row["timestamp_ms"]) <= int(block["end_ms"])
        ]
        watts = [float(row["vdd_in_w"]) for row in active]
        block_wall = float(block["wall_s"])
        frames = int(block["frames"])
        avg_w = statistics.mean(watts) if watts else 0.0
        block["power_samples"] = len(watts)
        block["vdd_in_w_mean"] = f"{avg_w:.6f}" if watts else ""
        block["vdd_in_w_p95"] = f"{percentile(watts, 95):.6f}" if watts else ""
        block["fps"] = f"{frames / block_wall:.6f}" if block_wall > 0 else ""
        block["joules_per_frame"] = f"{avg_w * block_wall / frames:.6f}" if watts and frames else ""
        block["fps_per_w"] = f"{frames / block_wall / avg_w:.6f}" if watts and avg_w > 0 else ""

    summary: list[dict[str, object]] = []
    for path_name in paths:
        group = [row for row in blocks if row["path"] == path_name]
        item: dict[str, object] = {
            "path": path_name,
            "blocks": len(group),
            "runs": sum(int(row["runs"]) for row in group),
            "failed_runs": sum(int(row["failed_runs"]) for row in group),
        }
        for field in ("vdd_in_w_mean", "fps", "joules_per_frame", "fps_per_w"):
            values = [float(row[field]) for row in group if row[field] != ""]
            item[f"{field}_mean"] = f"{statistics.mean(values):.6f}" if values else ""
            item[f"{field}_p95"] = f"{percentile(values, 95):.6f}" if values else ""
        summary.append(item)

    write_csv(out_dir / "workload_runs.csv", runs)
    write_csv(out_dir / "power_blocks.csv", blocks)
    write_csv(out_dir / "power_summary.csv", summary)
    for row in summary:
        print(row)
    return 1 if any(str(row["failure_reason"]) for row in runs) else 0


if __name__ == "__main__":
    raise SystemExit(main())
