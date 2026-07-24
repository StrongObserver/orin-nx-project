from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import subprocess
import time
from pathlib import Path


DEFAULT_HWMON = Path("/sys/devices/platform/c240000.i2c/i2c-1/1-0040/hwmon/hwmon4")


def sudo_cat(path: Path, sudo_password: str | None) -> str:
    if os.geteuid() == 0 or os.access(path, os.R_OK):
        return path.read_text(encoding="utf-8").strip()
    command = ["sudo", "-S", "-p", "", "cat", str(path)]
    completed = subprocess.run(
        command,
        input="" if sudo_password is None else sudo_password + "\n",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=2,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"cannot read {path}: {completed.stderr.strip()}")
    return completed.stdout.strip()


def read_int(path: Path, sudo_password: str | None) -> int:
    value = sudo_cat(path, sudo_password)
    return int(value)


def read_optional(path: Path, sudo_password: str | None) -> str:
    try:
        return sudo_cat(path, sudo_password)
    except RuntimeError:
        return ""


def decode_password() -> str | None:
    encoded = os.environ.get("JETSON_SUDO_B64", "")
    if not encoded:
        return None
    return base64.b64decode(encoded).decode("utf-8")


def sample_once(hwmon: Path, sudo_password: str | None) -> dict:
    in1_mv = read_int(hwmon / "in1_input", sudo_password)
    curr1_ma = read_int(hwmon / "curr1_input", sudo_password)
    in2_mv = read_int(hwmon / "in2_input", sudo_password)
    curr2_ma = read_int(hwmon / "curr2_input", sudo_password)
    in3_mv = read_int(hwmon / "in3_input", sudo_password)
    curr3_ma = read_int(hwmon / "curr3_input", sudo_password)
    return {
        "timestamp_ms": int(time.time() * 1000),
        "in1_mv": in1_mv,
        "curr1_ma": curr1_ma,
        "vdd_in_w": f"{in1_mv * curr1_ma / 1_000_000.0:.6f}",
        "in2_mv": in2_mv,
        "curr2_ma": curr2_ma,
        "vdd_cpu_gpu_cv_w": f"{in2_mv * curr2_ma / 1_000_000.0:.6f}",
        "in3_mv": in3_mv,
        "curr3_ma": curr3_ma,
        "vdd_soc_w": f"{in3_mv * curr3_ma / 1_000_000.0:.6f}",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sample Jetson INA3221 power rails to CSV.")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--duration", type=float, default=0.0, help="0 means run until interrupted.")
    parser.add_argument("--hwmon", type=Path, default=DEFAULT_HWMON)
    parser.add_argument("--metadata-out", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    sudo_password = decode_password()
    if args.metadata_out is not None:
        args.metadata_out.parent.mkdir(parents=True, exist_ok=True)
        metadata = {
            "hwmon": str(args.hwmon),
            "name": read_optional(args.hwmon / "name", sudo_password),
            "voltage_unit": "millivolt",
            "current_unit": "milliamp",
            "derived_power_unit": "watt",
            "rails": [
                {
                    "channel": index,
                    "label": read_optional(args.hwmon / f"in{index}_label", sudo_password),
                    "shunt_resistor_microohm": read_optional(
                        args.hwmon / f"shunt{index}_resistor", sudo_password
                    ),
                }
                for index in range(1, 4)
            ],
        }
        args.metadata_out.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    fieldnames = [
        "timestamp_ms",
        "in1_mv",
        "curr1_ma",
        "vdd_in_w",
        "in2_mv",
        "curr2_ma",
        "vdd_cpu_gpu_cv_w",
        "in3_mv",
        "curr3_ma",
        "vdd_soc_w",
    ]
    start = time.perf_counter()
    with args.out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        while True:
            writer.writerow(sample_once(args.hwmon, sudo_password))
            f.flush()
            if args.duration > 0 and time.perf_counter() - start >= args.duration:
                break
            time.sleep(args.interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
