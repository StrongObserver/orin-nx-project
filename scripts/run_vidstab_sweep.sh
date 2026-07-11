#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FFMPEG="${FFMPEG:-ffmpeg}"

INPUT="${INPUT:-$ROOT/data/raw/ostrich_shaky.mp4}"
OUT_DIR="${OUT_DIR:-$ROOT/results/vidstab_sweep}"
SUMMARY="$OUT_DIR/summary.csv"

SHAKINESS="${SHAKINESS:-8}"
ACCURACY="${ACCURACY:-15}"
STEPSIZE="${STEPSIZE:-6}"

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

printf "case,shakiness,accuracy,stepsize,smoothing,zoom,optzoom,detect_time_s,transform_time_s,stabilized_path,transforms_path\n" >"$SUMMARY"

run_case() {
    local name="$1"
    local smoothing="$2"
    local zoom="$3"
    local optzoom="$4"

    local case_dir="$OUT_DIR/$name"
    local transforms="$case_dir/ostrich_vidstab.trf"
    local stabilized="$case_dir/stabilized.mp4"
    local detect_log="$case_dir/detect.log"
    local transform_log="$case_dir/transform.log"

    mkdir -p "$case_dir"

    echo "[$name] detect: smoothing=$smoothing zoom=$zoom optzoom=$optzoom"
    local t0 t1 detect_s transform_s
    t0=$(date +%s.%N)
    "$FFMPEG" -y -i "$INPUT" \
        -vf "vidstabdetect=shakiness=$SHAKINESS:accuracy=$ACCURACY:stepsize=$STEPSIZE:result=$transforms" \
        -f null - >"$detect_log" 2>&1
    t1=$(date +%s.%N)
    detect_s=$(python3 -c "print(f'{float($t1) - float($t0):.3f}')")

    echo "[$name] transform"
    t0=$(date +%s.%N)
    "$FFMPEG" -y -i "$INPUT" \
        -vf "vidstabtransform=input=$transforms:smoothing=$smoothing:zoom=$zoom:optzoom=$optzoom:crop=black,unsharp=5:5:0.8:3:3:0.4" \
        -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -an "$stabilized" >"$transform_log" 2>&1
    t1=$(date +%s.%N)
    transform_s=$(python3 -c "print(f'{float($t1) - float($t0):.3f}')")

    printf "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n" \
        "$name" "$SHAKINESS" "$ACCURACY" "$STEPSIZE" "$smoothing" "$zoom" "$optzoom" \
        "$detect_s" "$transform_s" "$stabilized" "$transforms" >>"$SUMMARY"
}

run_case "s30_z-5_opt1" 30 -5 1
run_case "s45_z-5_opt1" 45 -5 1
run_case "s45_z0_opt1" 45 0 1
run_case "s60_z-5_opt1" 60 -5 1

echo "vid.stab sweep finished"
echo "summary: $SUMMARY"
