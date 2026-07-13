import argparse
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run cpu_stabilize.py over a gate clip matrix.")
    parser.add_argument("--raw-dir", type=Path, default=Path("results/gate_matrix/raw_clips"))
    parser.add_argument("--out-dir", type=Path, default=Path("results/gate_matrix/lp_affine"))
    parser.add_argument("--suffix", default="lp_affine_crop85", help="Output suffix appended after each clip stem")
    parser.add_argument("--smoothing-method", default="lp_affine")
    parser.add_argument("--smoothing-radius", default="15")
    parser.add_argument("--crop-ratio", default="0.85")
    parser.add_argument("--lp-trim-ratio", default="0.10", help="Override LP corner/FOV trim ratio; 0 derives from crop ratio")
    parser.add_argument("--mask-safety-max-invalid", default="0.01")
    parser.add_argument("--lp-w1", default="50")
    parser.add_argument("--lp-w2", default="10")
    parser.add_argument("--lp-w3", default="20")
    parser.add_argument("--lp-w4", default="30")
    parser.add_argument("--intent-proximity-blend", default="0.0")
    parser.add_argument("--intent-proximity-band-px", default="12.0")
    parser.add_argument("--intent-proximity-radius", default="30")
    parser.add_argument("--intent-proximity-stdev", default="0.0")
    parser.add_argument("--stabilization-strength", default="1.0")
    parser.add_argument("--lp-anchor-first", action="store_true")
    parser.add_argument("--lp-warp-inverse", action="store_true")
    parser.add_argument("--clip", action="append", default=[], help="Optional clip stem to run; can be repeated")
    args, extra_args = parser.parse_known_args()

    raw_dir = args.raw_dir
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    clips = sorted(raw_dir.glob("gate*.mp4"))
    if args.clip:
        keep = set(args.clip)
        clips = [clip for clip in clips if clip.stem in keep]
    if not clips:
        raise RuntimeError(f"No gate clips found under {raw_dir}")

    for clip in clips:
        name = clip.stem
        cmd = [
            sys.executable,
            "src/cpu_stabilize.py",
            "--input",
            str(clip),
            "--output",
            str(out_dir / f"{name}_{args.suffix}.mp4"),
            "--metrics",
            str(out_dir / f"{name}_{args.suffix}_metrics.csv"),
            "--summary",
            str(out_dir / f"{name}_{args.suffix}_summary.csv"),
            "--smoothing-method",
            args.smoothing_method,
            "--smoothing-radius",
            args.smoothing_radius,
            "--crop-ratio",
            args.crop_ratio,
            "--estimate-scale",
            "1.0",
            "--fallback-mode",
            "interpolate",
            "--max-translation-ratio",
            "0",
            "--max-rotation-deg",
            "0",
            "--accel-limit-px",
            "0",
            "--accel-limit-deg",
            "0",
            "--fallback-recovery-alpha",
            "0",
            "--inclusion-trim-ratio",
            "0",
            "--constrained-margin-scale",
            "1.0",
            "--lp-trim-ratio",
            args.lp_trim_ratio,
            "--mask-safety-max-invalid",
            args.mask_safety_max_invalid,
            "--lp-w1",
            args.lp_w1,
            "--lp-w2",
            args.lp_w2,
            "--lp-w3",
            args.lp_w3,
            "--lp-w4",
            args.lp_w4,
            "--intent-proximity-blend",
            args.intent_proximity_blend,
            "--intent-proximity-band-px",
            args.intent_proximity_band_px,
            "--intent-proximity-radius",
            args.intent_proximity_radius,
            "--intent-proximity-stdev",
            args.intent_proximity_stdev,
            "--stabilization-strength",
            args.stabilization_strength,
        ]
        if args.lp_anchor_first:
            cmd.append("--lp-anchor-first")
        if args.lp_warp_inverse:
            cmd.append("--lp-warp-inverse")
        cmd.extend(extra_args)
        print(f"RUN\t{name}")
        subprocess.run(cmd, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
