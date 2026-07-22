from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import vpi


BACKENDS = {
    "cpu": vpi.Backend.CPU,
    "cuda": vpi.Backend.CUDA,
    "pva": vpi.Backend.PVA,
    "vic": vpi.Backend.VIC,
    "ofa": vpi.Backend.OFA,
}


def make_image(width: int, height: int) -> np.ndarray:
    x = np.linspace(0, 255, width, dtype=np.uint8)
    y = np.linspace(0, 255, height, dtype=np.uint8)
    xx, yy = np.meshgrid(x, y)
    return np.dstack([xx, yy, ((xx.astype(np.uint16) + yy.astype(np.uint16)) // 2).astype(np.uint8)])


def make_identity_like_warpmap(width: int, height: int) -> vpi.WarpMap:
    grid = vpi.WarpGrid((width, height), interval=1)
    kin = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float32)
    xform = np.array(
        [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
        ],
        dtype=np.float32,
    )
    rcoeffs = np.zeros(4, dtype=np.float32)
    tcoeffs = np.zeros(2, dtype=np.float32)
    return vpi.WarpMap.polynomial_correction(grid, kin, xform, kin, rcoeffs, tcoeffs)


def probe_backend(image: vpi.Image, warpmap: vpi.WarpMap, backend_name: str, backend: vpi.Backend) -> dict:
    started = time.perf_counter()
    try:
        with backend:
            output = image.remap(
                warpmap,
                backend=backend,
                interp=vpi.Interp.LINEAR,
                border=vpi.Border.ZERO,
            )
        with output.rlock_cpu() as _:
            pass
        return {
            "operator": "remap",
            "backend": backend_name,
            "status": "pass",
            "elapsed_ms": f"{(time.perf_counter() - started) * 1000.0:.3f}",
            "detail": "",
        }
    except Exception as exc:  # noqa: BLE001 - support probe should record backend errors.
        return {
            "operator": "remap",
            "backend": backend_name,
            "status": "fail",
            "elapsed_ms": "",
            "detail": repr(exc).replace("\n", " ")[:300],
        }


def run_backend_subprocess(script: Path, backend_name: str, width: int, height: int) -> dict:
    started = time.perf_counter()
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--backend",
            backend_name,
            "--width",
            str(width),
            "--height",
            str(height),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=20,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    if completed.returncode == 0:
        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError:
            return {
                "operator": "remap",
                "backend": backend_name,
                "status": "fail_bad_json",
                "elapsed_ms": "",
                "detail": completed.stdout[-200:] + completed.stderr[-200:],
            }
    return {
        "operator": "remap",
        "backend": backend_name,
        "status": "fail_process",
        "elapsed_ms": "",
        "detail": f"rc={completed.returncode}; elapsed_ms={elapsed_ms:.3f}; stderr={completed.stderr[-240:]}",
    }


def run_single_backend(backend_name: str, width: int, height: int) -> int:
    backend = BACKENDS[backend_name]
    image = vpi.asimage(make_image(width, height))
    warpmap = make_identity_like_warpmap(width, height)
    row = probe_backend(image, warpmap, backend_name, backend)
    print(json.dumps(row, ensure_ascii=False), flush=True)
    return 0 if row["status"] == "pass" else 2


def write_outputs(out_dir: Path, rows: list[dict], raw: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "vpi_remap_minimal.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["operator", "backend", "status", "elapsed_ms", "detail"])
        writer.writeheader()
        writer.writerows(rows)
    (out_dir / "probe_raw.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# VPI Remap Minimal Probe",
        "",
        "| Operator | Backend | Status | Elapsed ms | Detail |",
        "|---|---|---|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['operator']} | {row['backend']} | {row['status']} | {row['elapsed_ms']} | {row['detail']} |"
        )
    lines.extend(
        [
            "",
            "This is a minimal Python VPI Remap support probe. It is not an end-to-end EIS speed claim.",
        ]
    )
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe minimal VPI Image.remap backend support.")
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--backend", choices=sorted(BACKENDS), default=None)
    parser.add_argument("--width", type=int, default=128)
    parser.add_argument("--height", type=int, default=96)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.backend is not None:
        run_single_backend(args.backend, args.width, args.height)
        return 0

    if args.out_dir is None:
        raise SystemExit("--out-dir is required unless --backend is set")
    rows = [run_backend_subprocess(Path(__file__), name, args.width, args.height) for name in BACKENDS]
    raw = {
        "vpi_version": getattr(vpi, "__version__", ""),
        "width": args.width,
        "height": args.height,
        "rows": rows,
    }
    write_outputs(args.out_dir, rows, raw)
    print(f"summary: {args.out_dir / 'summary.md'}")
    print(f"csv: {args.out_dir / 'vpi_remap_minimal.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
