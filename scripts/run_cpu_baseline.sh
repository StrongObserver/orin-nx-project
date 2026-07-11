#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"

INPUT="$ROOT/data/raw/ostrich_shaky.mp4"
OUTPUT="${OUTPUT:-$ROOT/results/cpu_baseline/ostrich_stabilized_r45_crop80_reflect.mp4}"
METRICS="${METRICS:-$ROOT/results/cpu_baseline/ostrich_metrics_r45_crop80_reflect.csv}"
SMOOTHING_RADIUS="${SMOOTHING_RADIUS:-45}"
CROP_RATIO="${CROP_RATIO:-0.80}"

"$PYTHON" "$ROOT/src/cpu_stabilize.py" --input "$INPUT" --output "$OUTPUT" --metrics "$METRICS" --smoothing-radius "$SMOOTHING_RADIUS" --crop-ratio "$CROP_RATIO"
