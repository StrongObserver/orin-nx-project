#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"

INPUT="${INPUT:-$ROOT/data/raw/ostrich_shaky.mp4}"
OUT_DIR="${OUT_DIR:-$ROOT/results/vpi_dataflow_benchmark}"
SUMMARY="${SUMMARY:-$OUT_DIR/summary.csv}"
MAX_FRAMES="${MAX_FRAMES:-0}"
WARMUP_FRAMES="${WARMUP_FRAMES:-5}"
WRITE_VIDEO="${WRITE_VIDEO:-0}"
VPI_CONVERT_BACKEND="${VPI_CONVERT_BACKEND:-cuda}"
BACKENDS="${BACKENDS:-opencv_cpu vpi_cpu vpi_cuda vpi_vic}"

mkdir -p "$OUT_DIR"
rm -f "$SUMMARY"

run_backend() {
    local backend="$1"
    local video_arg=()
    if [[ "$WRITE_VIDEO" == "1" ]]; then
        video_arg=(--write-video)
    fi

    echo "[vpi-dataflow] backend=$backend convert_backend=$VPI_CONVERT_BACKEND"
    "$PYTHON" "$ROOT/src/vpi_dataflow_benchmark.py" \
        --input "$INPUT" \
        --out-dir "$OUT_DIR" \
        --summary "$SUMMARY" \
        --backend "$backend" \
        --max-frames "$MAX_FRAMES" \
        --warmup-frames "$WARMUP_FRAMES" \
        --vpi-convert-backend "$VPI_CONVERT_BACKEND" \
        "${video_arg[@]}"
}

for backend in $BACKENDS; do
    run_backend "$backend"
done

echo "VPI dataflow benchmark finished"
echo "summary: $SUMMARY"
