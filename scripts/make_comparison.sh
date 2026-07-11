#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"

ORIGINAL="${ORIGINAL:-$ROOT/data/raw/ostrich_shaky.mp4}"
STABILIZED="${STABILIZED:-$ROOT/results/cpu_baseline/ostrich_stabilized_r45_crop80_reflect.mp4}"
OUTPUT="${OUTPUT:-$ROOT/results/cpu_baseline/ostrich_compare_side_by_side_r45_crop80_reflect.mp4}"

"$PYTHON" "$ROOT/src/make_comparison.py" --original "$ORIGINAL" --stabilized "$STABILIZED" --output "$OUTPUT"
