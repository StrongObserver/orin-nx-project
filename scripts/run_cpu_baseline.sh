#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"

INPUT="${INPUT:-$ROOT/data/raw/ostrich_shaky.mp4}"
WARP_BACKEND="${WARP_BACKEND:-opencv_cpu}"
SMOOTHING_RADIUS="${SMOOTHING_RADIUS:-45}"
CROP_RATIO="${CROP_RATIO:-0.80}"
ESTIMATE_SCALE="${ESTIMATE_SCALE:-1.0}"
OUTPUT="${OUTPUT:-$ROOT/results/cpu_baseline/ostrich_stabilized_r45_crop80_${WARP_BACKEND}_est${ESTIMATE_SCALE}.mp4}"
METRICS="${METRICS:-$ROOT/results/cpu_baseline/ostrich_metrics_r45_crop80_${WARP_BACKEND}_est${ESTIMATE_SCALE}.csv}"
SUMMARY="${SUMMARY:-$ROOT/results/cpu_baseline/ostrich_summary_r45_crop80_${WARP_BACKEND}_est${ESTIMATE_SCALE}.csv}"

"$PYTHON" "$ROOT/src/cpu_stabilize.py" \
    --input "$INPUT" \
    --output "$OUTPUT" \
    --metrics "$METRICS" \
    --smoothing-radius "$SMOOTHING_RADIUS" \
    --crop-ratio "$CROP_RATIO" \
    --warp-backend "$WARP_BACKEND" \
    --estimate-scale "$ESTIMATE_SCALE" \
    --summary "$SUMMARY"
