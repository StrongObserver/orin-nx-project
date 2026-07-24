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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Repeat accepted EGLImage, stream-only, and NvBuffer-pair paths on the same source/matrix."
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
    parser.add_argument(
        "--out-dir",
        default="results/vpi_cuda_owned_bridge_20260724/accepted_path_compare_py",
    )
    parser.add_argument("--runs", type=int, default=5)
    return parser.parse_args()


def run_once(
    root: Path,
    out_dir: Path,
    name: str,
    binary: str,
    source: str,
    matrix: str,
    run_index: int,
) -> dict[str, object]:
    log_path = out_dir / f"{name}_{run_index}.log"
    output_path = out_dir / f"{name}_{run_index}.h264"
    env = os.environ.copy()
    env["VPI_MATRIX_CSV"] = str(root / matrix)
    command = [
        str(root / binary),
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
    wrapper_ms = stage100_ms = stageavg_ms = None
    if match:
        wrapper_ms = float(match.group(1))
        stage100_ms = float(match.group(2))
        stageavg_ms = float(match.group(3))
    return {
        "path": name,
        "run": run_index,
        "rc": proc.returncode,
        "success": int("App run was successful" in proc.stdout),
        "fallback_count": proc.stdout.count("fallback=1"),
        "wall_s": wall_s,
        "wrapper_ms": wrapper_ms,
        "stage100_ms": stage100_ms,
        "stageavg_ms": stageavg_ms,
        "bytes": output_path.stat().st_size if output_path.exists() else 0,
    }


def summarize(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    summary: list[dict[str, object]] = []
    for name in ["egl", "stream", "nvbuf"]:
        group = [row for row in rows if row["path"] == name]
        item: dict[str, object] = {
            "path": name,
            "runs": len(group),
            "rc0": sum(1 for row in group if row["rc"] == 0),
            "success": sum(int(row["success"]) for row in group),
            "fallback_total": sum(int(row["fallback_count"]) for row in group),
        }
        for key in ["wall_s", "wrapper_ms", "stage100_ms", "stageavg_ms"]:
            values = [float(row[key]) for row in group if row[key] is not None]
            item[f"{key}_mean"] = statistics.mean(values) if values else ""
            item[f"{key}_median"] = statistics.median(values) if values else ""
        summary.append(item)
    return summary


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
    binaries = {
        "egl": "_mmapi_work/jetson_multimedia_api/samples/99_vpi_transcode_matrix_eglimage/multivideo_transcode",
        "stream": "_mmapi_work/jetson_multimedia_api/samples/99_vpi_transcode_matrix_eglimage_stream_reuse/multivideo_transcode",
        "nvbuf": "_mmapi_work/jetson_multimedia_api/samples/99_vpi_transcode_matrix_nvbuffer_pair/multivideo_transcode",
    }
    rows: list[dict[str, object]] = []
    for run_index in range(1, args.runs + 1):
        for name, binary in binaries.items():
            row = run_once(root, out_dir, name, binary, args.source, args.matrix, run_index)
            rows.append(row)
            print(row, flush=True)

    summary = summarize(rows)
    write_csv(out_dir / "repeat_metrics.csv", rows)
    write_csv(out_dir / "repeat_summary.csv", summary)
    print("SUMMARY")
    for row in summary:
        print(row)

    failed = [row for row in rows if row["rc"] != 0 or int(row["success"]) != 1]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
