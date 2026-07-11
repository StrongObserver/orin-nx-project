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
SUMMARY="${SUMMARY:-$OUT_DIR/summary.csv}"
DETECT_LOG="${DETECT_LOG:-$OUT_DIR/detect.log}"
TRANSFORM_LOG="${TRANSFORM_LOG:-$OUT_DIR/transform.log}"
COMPARE_LOG="${COMPARE_LOG:-$OUT_DIR/compare.log}"

# vid.stab parameters. These defaults favor visible stabilization quality over speed.
SHAKINESS="${SHAKINESS:-8}"
ACCURACY="${ACCURACY:-15}"
STEPSIZE="${STEPSIZE:-6}"
SMOOTHING="${SMOOTHING:-45}"
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

elapsed_seconds() {
    "$PYTHON" -c 'import sys; print(f"{float(sys.argv[2]) - float(sys.argv[1]):.3f}")' "$1" "$2"
}

total_t0=$(date +%s.%N)

echo "[1/3] Detecting camera motion with vid.stab"
detect_t0=$(date +%s.%N)
"$FFMPEG" -y -i "$INPUT" \
    -vf "vidstabdetect=shakiness=$SHAKINESS:accuracy=$ACCURACY:stepsize=$STEPSIZE:result=$TRANSFORMS" \
    -f null - >"$DETECT_LOG" 2>&1
detect_t1=$(date +%s.%N)
detect_time_s=$(elapsed_seconds "$detect_t0" "$detect_t1")

echo "[2/3] Transforming video with vid.stab"
transform_t0=$(date +%s.%N)
"$FFMPEG" -y -i "$INPUT" \
    -vf "vidstabtransform=input=$TRANSFORMS:smoothing=$SMOOTHING:zoom=$ZOOM:optzoom=$OPTZOOM:crop=$CROP,unsharp=5:5:0.8:3:3:0.4" \
    -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -an "$STABILIZED" >"$TRANSFORM_LOG" 2>&1
transform_t1=$(date +%s.%N)
transform_time_s=$(elapsed_seconds "$transform_t0" "$transform_t1")

echo "[3/3] Creating side-by-side comparison"
compare_t0=$(date +%s.%N)
"$PYTHON" "$ROOT/src/make_comparison.py" \
    --original "$INPUT" \
    --stabilized "$STABILIZED" \
    --output "$COMPARE" >"$COMPARE_LOG" 2>&1
compare_t1=$(date +%s.%N)
compare_time_s=$(elapsed_seconds "$compare_t0" "$compare_t1")

total_t1=$(date +%s.%N)
total_time_s=$(elapsed_seconds "$total_t0" "$total_t1")

printf "input,shakiness,accuracy,stepsize,smoothing,zoom,optzoom,crop,detect_time_s,transform_time_s,compare_time_s,total_time_s,stabilized_path,compare_path,transforms_path,detect_log,transform_log,compare_log\n" >"$SUMMARY"
printf "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n" \
    "$INPUT" "$SHAKINESS" "$ACCURACY" "$STEPSIZE" "$SMOOTHING" "$ZOOM" "$OPTZOOM" "$CROP" \
    "$detect_time_s" "$transform_time_s" "$compare_time_s" "$total_time_s" \
    "$STABILIZED" "$COMPARE" "$TRANSFORMS" "$DETECT_LOG" "$TRANSFORM_LOG" "$COMPARE_LOG" >"$SUMMARY.tmp"
cat "$SUMMARY.tmp" >>"$SUMMARY"
rm "$SUMMARY.tmp"

echo "vid.stab baseline finished"
echo "input: $INPUT"
echo "transforms: $TRANSFORMS"
echo "stabilized: $STABILIZED"
echo "compare: $COMPARE"
echo "summary: $SUMMARY"
echo "detect_time_s: $detect_time_s"
echo "transform_time_s: $transform_time_s"
echo "compare_time_s: $compare_time_s"
echo "total_time_s: $total_time_s"
