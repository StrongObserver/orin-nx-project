from __future__ import annotations

import argparse
import csv
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


BACKEND_NAMES = ["CPU", "CUDA", "PVA", "VIC", "OFA"]
GST_ELEMENTS = [
    "nvv4l2decoder",
    "nvv4l2h264enc",
    "nvv4l2h265enc",
    "nvvidconv",
    "nvarguscamerasrc",
]


def run_command(command: list[str], timeout: float = 8.0) -> dict:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        return {
            "command": command,
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "elapsed_s": round(time.perf_counter() - started, 3),
            "timed_out": False,
        }
    except FileNotFoundError as exc:
        return {
            "command": command,
            "exit_code": None,
            "stdout": "",
            "stderr": str(exc),
            "elapsed_s": round(time.perf_counter() - started, 3),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "exit_code": None,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "elapsed_s": round(time.perf_counter() - started, 3),
            "timed_out": True,
        }


def status_row(operator: str, backend: str, status: str, detail: str = "", elapsed_ms: float | None = None) -> dict:
    return {
        "operator": operator,
        "backend": backend,
        "status": status,
        "elapsed_ms": "" if elapsed_ms is None else f"{elapsed_ms:.3f}",
        "detail": detail.replace("\n", " ")[:300],
    }


def import_optional(module_name: str):
    try:
        return __import__(module_name), ""
    except Exception as exc:  # noqa: BLE001 - this is a probe.
        return None, repr(exc)


def available_vpi_backends(vpi) -> dict:
    available = {}
    for name in BACKEND_NAMES:
        available[name.lower()] = getattr(vpi.Backend, name, None)
    return available


def make_test_image():
    import numpy as np

    height, width = 96, 128
    x = np.linspace(0, 255, width, dtype=np.uint8)
    y = np.linspace(0, 255, height, dtype=np.uint8)
    xx, yy = np.meshgrid(x, y)
    return np.dstack([xx, yy, ((xx.astype(np.uint16) + yy.astype(np.uint16)) // 2).astype(np.uint8)])


def probe_vpi() -> tuple[dict, list[dict]]:
    vpi, vpi_error = import_optional("vpi")
    np, np_error = import_optional("numpy")
    if vpi is None:
        return (
            {
                "vpi_import": "fail",
                "vpi_import_error": vpi_error,
                "numpy_import": "pass" if np is not None else f"fail: {np_error}",
                "vpi_version": "",
                "visible_backends": [],
                "vpi_symbols": [],
            },
            [status_row("vpi_import", "all", "env_missing", vpi_error)],
        )

    visible_backends = available_vpi_backends(vpi)
    present_backend_names = [name for name, value in visible_backends.items() if value is not None]
    interesting_symbols = sorted(
        name for name in dir(vpi) if any(token in name.lower() for token in ("flow", "warp", "remap", "pyr", "of"))
    )
    metadata = {
        "vpi_import": "pass",
        "vpi_import_error": "",
        "numpy_import": "pass" if np is not None else f"fail: {np_error}",
        "vpi_version": str(getattr(vpi, "__version__", "")),
        "visible_backends": present_backend_names,
        "vpi_symbols": interesting_symbols,
    }

    rows: list[dict] = []
    if np is None:
        rows.append(status_row("numpy_import", "all", "env_missing", np_error))
        return metadata, rows

    image_bgr = make_test_image()
    image_vpi = vpi.asimage(image_bgr)
    matrix = np.array(
        [
            [0.998, -0.018, 2.0],
            [0.018, 0.998, -1.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )

    for backend_name, backend in visible_backends.items():
        if backend is None:
            rows.append(status_row("backend_visible", backend_name, "api_missing", "Backend enum not present"))
            continue
        rows.append(status_row("backend_visible", backend_name, "visible"))

        try:
            started = time.perf_counter()
            with backend:
                converted = image_vpi.convert(vpi.Format.NV12_ER)
            elapsed = (time.perf_counter() - started) * 1000.0
            rows.append(status_row("image_convert_bgr_to_nv12", backend_name, "pass", elapsed_ms=elapsed))
        except Exception as exc:  # noqa: BLE001 - backend support probe.
            rows.append(status_row("image_convert_bgr_to_nv12", backend_name, "fail", repr(exc)))
            converted = None

        if converted is None:
            rows.append(status_row("perspective_warp", backend_name, "not_attempted", "input conversion failed"))
        else:
            try:
                started = time.perf_counter()
                with backend:
                    warped = converted.perspwarp(matrix)
                with warped.rlock_cpu() as _:
                    pass
                elapsed = (time.perf_counter() - started) * 1000.0
                rows.append(status_row("perspective_warp", backend_name, "pass", elapsed_ms=elapsed))
            except Exception as exc:  # noqa: BLE001 - backend support probe.
                rows.append(status_row("perspective_warp", backend_name, "fail", repr(exc)))

        remap_method = getattr(image_vpi, "remap", None)
        if remap_method is None:
            rows.append(status_row("remap_api_presence", backend_name, "api_missing", "vpi.Image.remap not present"))
        else:
            rows.append(status_row("remap_api_presence", backend_name, "api_present", "Manual map construction required"))

    symbol_text = " ".join(interesting_symbols).lower()
    for operator, needles in {
        "pyramidal_lk_optical_flow_api_presence": ["pyr", "lk", "flow"],
        "dense_optical_flow_api_presence": ["dense", "flow"],
        "optical_flow_hardware_api_presence": ["ofa", "flow"],
    }.items():
        present = all(needle in symbol_text for needle in needles)
        rows.append(
            status_row(
                operator,
                "all",
                "api_present_needs_manual_probe" if present else "api_unclear",
                ", ".join(interesting_symbols[:40]),
            )
        )

    return metadata, rows


def collect_environment() -> dict:
    cv2, cv2_error = import_optional("cv2")
    env = {
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": sys.version.replace("\n", " "),
        "python_executable": sys.executable,
        "cv2_import": "pass" if cv2 is not None else "fail",
        "cv2_import_error": cv2_error,
        "cv2_version": str(getattr(cv2, "__version__", "")) if cv2 is not None else "",
    }
    return env


def collect_system_commands() -> dict:
    commands = {
        "nvpmodel_q": ["nvpmodel", "-q"],
        "tegrastats_help": ["tegrastats", "--help"],
        "gst_version": ["gst-launch-1.0", "--version"],
    }
    for element in GST_ELEMENTS:
        commands[f"gst_inspect_{element}"] = ["gst-inspect-1.0", element]
    return {name: run_command(command) for name, command in commands.items()}


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["operator", "backend", "status", "elapsed_ms", "detail"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(path: Path, env: dict, vpi_metadata: dict, rows: list[dict], commands: dict) -> None:
    def command_status(name: str) -> str:
        item = commands[name]
        if item["timed_out"]:
            return "timeout"
        if item["exit_code"] == 0:
            return "pass"
        return "fail"

    lines = [
        "# Jetson Backend Probe Summary",
        "",
        "## Environment",
        "",
        f"- platform: {env['platform']}",
        f"- machine: {env['machine']}",
        f"- python: {env['python_executable']}",
        f"- cv2: {env['cv2_version'] or env['cv2_import']}",
        f"- vpi: {vpi_metadata.get('vpi_version', '') or vpi_metadata.get('vpi_import')}",
        f"- visible VPI backends: {', '.join(vpi_metadata.get('visible_backends', []))}",
        "",
        "## VPI Operator Probe",
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
            "## System Probe",
            "",
            "| Probe | Status |",
            "|---|---|",
        ]
    )
    for name in commands:
        lines.append(f"| {name} | {command_status(name)} |")
    lines.extend(
        [
            "",
            "## Interpretation Rules",
            "",
            "- `pass` means this exact minimal probe ran on this device.",
            "- `fail` means the API or backend was attempted and failed; inspect `probe_raw.json`.",
            "- `api_missing` or `api_unclear` means the Python binding did not expose a simple probe path here.",
            "- This table is a backend support entry point; it is not an end-to-end EIS speedup claim.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe Jetson VPI/GStreamer/power backend readiness.")
    parser.add_argument("--out-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    env = collect_environment()
    vpi_metadata, vpi_rows = probe_vpi()
    commands = collect_system_commands()

    raw = {
        "environment": env,
        "vpi_metadata": vpi_metadata,
        "vpi_operator_rows": vpi_rows,
        "commands": commands,
    }
    (args.out_dir / "probe_raw.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(args.out_dir / "vpi_backend_support.csv", vpi_rows)
    write_summary(args.out_dir / "summary.md", env, vpi_metadata, vpi_rows, commands)

    print(f"summary: {args.out_dir / 'summary.md'}")
    print(f"vpi_backend_support: {args.out_dir / 'vpi_backend_support.csv'}")
    print(f"raw: {args.out_dir / 'probe_raw.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
