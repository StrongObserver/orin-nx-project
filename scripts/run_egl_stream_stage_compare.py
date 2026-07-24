from __future__ import annotations

import argparse
import csv
import os
import re
import statistics
import subprocess
import time
from pathlib import Path


PATTERN = re.compile(
    r"EGL_STAGE_TIMING frame=100 .*?wrapper_call_ms=([0-9.]+)"
    r".*?total_stage_ms=([0-9.]+).*?avg_total_stage_ms=([0-9.]+)"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare EGL timing and stream-only reuse samples.")
    parser.add_argument("--root", type=Path, default=Path("/home/nvidia/orin-nx-project"))
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument(
        "--source",
        default="results/regular_gate_safe103_crop98_validation_20260720/regular_gate05_regular_6/source.h264",
    )
    parser.add_argument(
        "--matrix",
        default="results/regular_gate_nvbuffer_pair_resid_20260723/regular_gate05_regular_6/resid_r15_s07.csv",
    )
    parser.add_argument(
        "--out-dir",
        default="results/vpi_cuda_owned_bridge_20260724/accepted_stage_compare_py",
    )
    return parser.parse_args()


def run_path(root: Path, out_dir: Path, name: str, binary: str, source: str, matrix: str, index: int) -> dict[str, object]:
    env = os.environ.copy()
    env["VPI_MATRIX_CSV"] = str(root / matrix)
    output = out_dir / f"{name}_{index}.h264"
    log = out_dir / f"{name}_{index}.log"
    command = [str(root / binary), "num_files", "1", str(root / source), "H264", str(output), "H264"]
    started = time.perf_counter()
    proc = subprocess.run(command, cwd=root, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    wall_s = time.perf_counter() - started
    log.write_text(proc.stdout, encoding="utf-8")
    match = PATTERN.search(proc.stdout)
    row: dict[str, object] = {
        "path": name,
        "run": index,
        "rc": proc.returncode,
        "success": int("App run was successful" in proc.stdout),
        "fallback_count": proc.stdout.count("fallback=1"),
        "wall_s": wall_s,
        "wrapper_ms": "",
        "stage100_ms": "",
        "stageavg_ms": "",
        "bytes": output.stat().st_size if output.exists() else 0,
    }
    if match:
        row["wrapper_ms"] = float(match.group(1))
        row["stage100_ms"] = float(match.group(2))
        row["stageavg_ms"] = float(match.group(3))
    return row


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    root = args.root
    out_dir = root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    binaries = {
        "egl_timing": "_mmapi_work/jetson_multimedia_api/samples/99_vpi_transcode_matrix_eglimage_timing/multivideo_transcode",
        "stream": "_mmapi_work/jetson_multimedia_api/samples/99_vpi_transcode_matrix_eglimage_stream_reuse/multivideo_transcode",
    }
    rows: list[dict[str, object]] = []
    for index in range(1, args.runs + 1):
        for name, binary in binaries.items():
            row = run_path(root, out_dir, name, binary, args.source, args.matrix, index)
            rows.append(row)
            print(row, flush=True)
    summary: list[dict[str, object]] = []
    for name in binaries:
        group = [row for row in rows if row["path"] == name]
        item: dict[str, object] = {
            "path": name,
            "runs": len(group),
            "rc0": sum(1 for row in group if row["rc"] == 0),
            "success": sum(int(row["success"]) for row in group),
            "fallback_total": sum(int(row["fallback_count"]) for row in group),
        }
        for key in ["wall_s", "wrapper_ms", "stage100_ms", "stageavg_ms"]:
            values = [float(row[key]) for row in group if row[key] != ""]
            item[f"{key}_mean"] = statistics.mean(values) if values else ""
            item[f"{key}_median"] = statistics.median(values) if values else ""
        summary.append(item)
    write_csv(out_dir / "stage_metrics.csv", rows)
    write_csv(out_dir / "stage_summary.csv", summary)
    print("SUMMARY")
    for row in summary:
        print(row)
    return 0 if all(row["rc"] == 0 and row["success"] == 1 for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
