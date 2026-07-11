#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"

INPUT="${INPUT:-$ROOT/data/raw/sample_1920x1080_from4k.mp4}"
OUT_DIR="${OUT_DIR:-$ROOT/results/estimate_scale_sweep}"
WARP_BACKEND="${WARP_BACKEND:-opencv_cpu}"
SMOOTHING_RADIUS="${SMOOTHING_RADIUS:-45}"
CROP_RATIO="${CROP_RATIO:-0.80}"
SCALES="${SCALES:-1.0 0.5 0.33}"
COMBINED_SUMMARY="${COMBINED_SUMMARY:-$OUT_DIR/summary.csv}"

mkdir -p "$OUT_DIR"
rm -f "$COMBINED_SUMMARY"

for scale in $SCALES; do
    safe_scale="${scale//./p}"
    output="$OUT_DIR/stabilized_${WARP_BACKEND}_est${safe_scale}.mp4"
    metrics="$OUT_DIR/metrics_${WARP_BACKEND}_est${safe_scale}.csv"
    summary="$OUT_DIR/summary_${WARP_BACKEND}_est${safe_scale}.csv"

    echo "[estimate-scale] input=$INPUT backend=$WARP_BACKEND estimate_scale=$scale"
    "$PYTHON" "$ROOT/src/cpu_stabilize.py" \
        --input "$INPUT" \
        --output "$output" \
        --metrics "$metrics" \
        --summary "$summary" \
        --smoothing-radius "$SMOOTHING_RADIUS" \
        --crop-ratio "$CROP_RATIO" \
        --warp-backend "$WARP_BACKEND" \
        --estimate-scale "$scale"

    if [[ ! -s "$COMBINED_SUMMARY" ]]; then
        cat "$summary" >"$COMBINED_SUMMARY"
    else
        tail -n +2 "$summary" >>"$COMBINED_SUMMARY"
    fi
done

echo "estimate scale sweep finished"
echo "summary: $COMBINED_SUMMARY"
