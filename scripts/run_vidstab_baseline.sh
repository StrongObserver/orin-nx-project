#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
FFMPEG="${FFMPEG:-ffmpeg}"

INPUT="${INPUT:-$ROOT/data/raw/ostrich_shaky.mp4}"
OUT_DIR="${OUT_DIR:-$ROOT/results/vidstab_baseline}"
TRANSFORMS="${TRANSFORMS:-$OUT_DIR/ostrich_vidstab.trf}"
STABILIZED="${STABILIZED:-$OUT_DIR/ostrich_vidstab_stabilized.mp4}"
COMPARE="${COMPARE:-$OUT_DIR/ostrich_vidstab_compare.mp4}"

# vid.stab parameters. These defaults favor visible stabilization quality over speed.
SHAKINESS="${SHAKINESS:-8}"
ACCURACY="${ACCURACY:-15}"
STEPSIZE="${STEPSIZE:-6}"
SMOOTHING="${SMOOTHING:-30}"
ZOOM="${ZOOM:--5}"
OPTZOOM="${OPTZOOM:-1}"
CROP="${CROP:-black}"

mkdir -p "$OUT_DIR"

if ! command -v "$FFMPEG" >/dev/null 2>&1; then
    echo "ffmpeg not found. Install FFmpeg with vid.stab filters, or set FFMPEG=/path/to/ffmpeg." >&2
    exit 1
fi

FILTER_LIST="$OUT_DIR/ffmpeg_filters.txt"
"$FFMPEG" -hide_banner -filters >"$FILTER_LIST" 2>/dev/null
if ! grep -q "vidstabdetect" "$FILTER_LIST"; then
    echo "The current FFmpeg does not include vid.stab filters." >&2
    echo "Need filters: vidstabdetect and vidstabtransform." >&2
    exit 1
fi

echo "[1/3] Detecting camera motion with vid.stab"
"$FFMPEG" -y -i "$INPUT" \
    -vf "vidstabdetect=shakiness=$SHAKINESS:accuracy=$ACCURACY:stepsize=$STEPSIZE:result=$TRANSFORMS" \
    -f null -

echo "[2/3] Transforming video with vid.stab"
"$FFMPEG" -y -i "$INPUT" \
    -vf "vidstabtransform=input=$TRANSFORMS:smoothing=$SMOOTHING:zoom=$ZOOM:optzoom=$OPTZOOM:crop=$CROP,unsharp=5:5:0.8:3:3:0.4" \
    -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -an "$STABILIZED"

echo "[3/3] Creating side-by-side comparison"
"$PYTHON" "$ROOT/src/make_comparison.py" \
    --original "$INPUT" \
    --stabilized "$STABILIZED" \
    --output "$COMPARE"

echo "vid.stab baseline finished"
echo "input: $INPUT"
echo "transforms: $TRANSFORMS"
echo "stabilized: $STABILIZED"
echo "compare: $COMPARE"
