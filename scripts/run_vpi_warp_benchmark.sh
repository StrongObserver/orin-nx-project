#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"

INPUT="${INPUT:-$ROOT/data/raw/ostrich_shaky.mp4}"
OUT_DIR="${OUT_DIR:-$ROOT/results/vpi_warp_benchmark}"
SUMMARY="${SUMMARY:-$OUT_DIR/summary.csv}"
MAX_FRAMES="${MAX_FRAMES:-0}"
WARMUP_FRAMES="${WARMUP_FRAMES:-5}"
WRITE_VIDEO="${WRITE_VIDEO:-0}"

mkdir -p "$OUT_DIR"
rm -f "$SUMMARY"

run_backend() {
    local backend="$1"
    local video_arg=()
    if [[ "$WRITE_VIDEO" == "1" ]]; then
        video_arg=(--write-video)
    fi

    echo "[vpi-warp] backend=$backend"
    "$PYTHON" "$ROOT/src/vpi_warp_benchmark.py" \
        --input "$INPUT" \
        --out-dir "$OUT_DIR" \
        --summary "$SUMMARY" \
        --backend "$backend" \
        --max-frames "$MAX_FRAMES" \
        --warmup-frames "$WARMUP_FRAMES" \
        "${video_arg[@]}"
}

run_backend opencv_cpu
run_backend vpi_cpu
run_backend vpi_cuda
run_backend vpi_vic

echo "VPI warp benchmark finished"
echo "summary: $SUMMARY"
