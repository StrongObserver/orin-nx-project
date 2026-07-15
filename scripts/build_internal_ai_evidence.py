import argparse
import csv
from pathlib import Path


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_one_row(path: Path) -> dict[str, str]:
    rows = read_csv_rows(path)
    if not rows:
        raise RuntimeError(f"Empty CSV: {path}")
    return rows[0]


def as_float(row: dict[str, str], key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key, ""))
    except ValueError:
        return default


def fmt(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}f}"


def load_eval(path: Path) -> dict[str, dict[str, str]]:
    return {row["name"]: row for row in read_csv_rows(path)}


def summary_for_config(
    config_name: str,
    eval_rows: dict[str, dict[str, str]],
    summary_dir: Path,
    suffix: str,
) -> list[dict[str, str]]:
    out = []
    for name in sorted(eval_rows):
        eval_row = eval_rows[name]
        summary_path = summary_dir / f"{name}_{suffix}_summary.csv"
        summary = read_one_row(summary_path) if summary_path.exists() else {}
        out.append(
            {
                "config": config_name,
                "clip": name,
                "layered": eval_row.get("layered_acceptance", ""),
                "sr_pose": fmt(as_float(eval_row, "sr_residual_pose")),
                "residual_improve": fmt(as_float(eval_row, "improve_residual_trans_std")),
                "second_diff_improve": fmt(as_float(eval_row, "improve_second_diff_top5_mean")),
                "black_p95": fmt(as_float(eval_row, "stab_p95_black_border_ratio"), 6),
                "avg_tracked": fmt(as_float(summary, "avg_tracked_features")),
                "avg_inliers": fmt(as_float(summary, "avg_inliers")),
                "avg_inlier_ratio": fmt(as_float(summary, "avg_inlier_ratio")),
                "fallback_frames": str(int(as_float(summary, "fallback_frames"))),
                "rollback_frames": str(int(as_float(summary, "mask_safety_rollback_frames"))),
                "rollback_min_beta": fmt(as_float(summary, "mask_safety_min_beta"), 3),
                "warp_ms": fmt(as_float(summary, "avg_warp_ms"), 3),
                "estimate_ms": fmt(as_float(summary, "avg_estimate_ms"), 3),
            }
        )
    return out


def table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a compact evidence package for internal AI escalation.")
    parser.add_argument("--out-md", type=Path, default=Path("results/diagnostics/internal_ai_evidence_20260715.md"))
    args = parser.parse_args()

    current_eval = load_eval(Path("results/nus_running_gate_v1/running_lp_affine_trim010_eval.csv"))
    rigid_eval = load_eval(Path("results/diagnostics/running_full_candidates/running_lp_rigid_trim010_eval.csv"))
    strength_eval = load_eval(Path("results/diagnostics/running_full_candidates/running_lp_affine_strength075_eval.csv"))

    current = summary_for_config(
        "current_lp_affine_strength1",
        current_eval,
        Path("results/nus_running_gate_v1/lp_affine_trim010"),
        "lp_affine_trim010_crop85",
    )
    rigid = summary_for_config(
        "lp_rigid_strength1",
        rigid_eval,
        Path("results/diagnostics/running_full_candidates/lp_rigid_trim010"),
        "lp_rigid_trim010_crop85",
    )
    strength = summary_for_config(
        "lp_affine_strength075",
        strength_eval,
        Path("results/diagnostics/running_full_candidates/lp_affine_strength075"),
        "lp_affine_strength075_crop85",
    )

    sharpness_rows = read_csv_rows(Path("results/diagnostics/artifact_boundary_v1/sharpness_metrics.csv"))
    affine_rows = read_csv_rows(Path("results/diagnostics/artifact_boundary_v1/affine_motion_metrics.csv"))

    def mean_of(rows: list[dict[str, str]], key: str) -> float:
        vals = [as_float(row, key) for row in rows]
        return sum(vals) / len(vals) if vals else 0.0

    aggregate_rows = []
    for config_name, rows in [
        ("current_lp_affine_strength1", current),
        ("lp_rigid_strength1", rigid),
        ("lp_affine_strength075", strength),
    ]:
        aggregate_rows.append(
            [
                config_name,
                f"{sum(1 for r in rows if r['layered'] == 'pass_all_objective_gates')}/5",
                fmt(mean_of(rows, "sr_pose")),
                fmt(mean_of(rows, "residual_improve")),
                fmt(mean_of(rows, "second_diff_improve")),
                str(sum(1 for r in rows if as_float(r, "black_p95") > 0.01)),
                ", ".join(r["rollback_frames"] for r in rows),
            ]
        )

    detailed_headers = [
        "config",
        "clip",
        "layered",
        "SR",
        "residual",
        "second",
        "tracked/inlier_ratio",
        "fallback",
        "rollback",
    ]
    detailed_rows = []
    for row in current + rigid + strength:
        detailed_rows.append(
            [
                row["config"],
                row["clip"],
                row["layered"],
                row["sr_pose"],
                row["residual_improve"],
                row["second_diff_improve"],
                f"{row['avg_tracked']}/{row['avg_inlier_ratio']}",
                row["fallback_frames"],
                row["rollback_frames"],
            ]
        )

    selected_sharpness = [
        row
        for row in sharpness_rows
        if row["variant"] in {"encode_only", "crop85_only", "current_lp_affine_trim010", "lp_rigid", "strength075"}
    ]
    sharp_rows = [
        [
            row["clip"],
            row["variant"],
            f"{as_float(row, 'laplacian_ratio_vs_raw'):.3f}",
            f"{as_float(row, 'tenengrad_ratio_vs_raw'):.3f}",
        ]
        for row in selected_sharpness
    ]

    selected_affine = [
        row
        for row in affine_rows
        if row["variant"] in {"raw", "current_lp_affine_trim010", "lp_rigid", "strength075"}
    ]
    affine_table_rows = [
        [
            row["clip"],
            row["variant"],
            f"{as_float(row, 'anisotropy_abs_delta_mean'):.6f}",
            f"{as_float(row, 'shear_proxy_mean'):.6f}",
            f"{as_float(row, 'translation_norm_mean'):.3f}",
        ]
        for row in selected_affine
    ]

    md = f"""# Internal AI Evidence Package - Orin NX EIS Running/Jello Issue

Date: 2026-07-15

## One-Sentence Problem

On NUS/SIGGRAPH2013 Running clips, our pure-visual global 2D EIS reduces some camera shake and eliminates black borders, but the user still sees strong cloth-like corner pulling / jello-like deformation and blur. Local tuning improved metrics but did not meet visual expectations.

## Pipeline Under Test

```text
GFTT/LK feature tracking
-> grid selection + foreground outlier rejection
-> OpenCV estimateAffinePartial2D + RANSAC
-> LP smoothing, lp_affine or lp_rigid
-> cv2.warpAffine, BORDER_REFLECT
-> fixed center crop + resize back to original size
```

Source code anchors:

```text
src/cpu_stabilize.py: estimateAffinePartial2D around motion estimation
src/cpu_stabilize.py: solve_lp_motion_stabilizer_affine / solve_lp_motion_stabilizer_rigid
src/cpu_stabilize.py: apply_mask_safety_rollback_mats
src/cpu_stabilize.py: fixed_center_crop_and_resize
src/cpu_stabilize.py: cv2.warpAffine final warp
```

## Dataset / Clips

```text
Dataset: NUS / SIGGRAPH2013 video stabilization dataset
Category: Running
Selected gate v1 clips: Running/16, Running/4, Running/17, Running/15, Running/18
Local raw clips: results/nus_running_gate_v1/raw_clips/
User visual review copies: C:\\Users\\Admin\\Videos\\orin nx\\running_full_candidates\\
```

## User Visual Observation

```text
Black border is controlled and stabilization has some effect.
However the frame looks like an elastic cloth.
The four corners look as if they are pulled by four hands with chaotic force.
The output is still blurred compared with the raw input.
lp_affine strength=0.75 and lp_rigid both still look unacceptable by eye.
```

## Aggregate Objective Results

{table(["config", "full_pass", "mean_SR", "mean_residual", "mean_second_diff", "black_fail_count", "rollback_frames"], aggregate_rows)}

## Detailed Per-Clip Evidence

{table(detailed_headers, detailed_rows)}

Key reading:

```text
Feature tracking is not obviously collapsing: avg tracked features are usually ~77-114 and inlier ratio is high.
Current lp_affine strength=1.0 has many mask-safety rollback frames: 131,172,160,157,220.
lp_affine strength=0.75 removes rollback frames completely and improves second-diff metrics, but user still sees cloth-like pulling.
lp_rigid improves SR/residual but still fails smoothness on 4/5 and user still sees pulling.
```

## Blur Evidence

Ratios are measured against raw input. Encode-only preserves almost all sharpness, so encoding is not the main blur source.

{table(["clip", "variant", "laplacian_ratio", "tenengrad_ratio"], sharp_rows)}

Key reading:

```text
crop85-only already drops Laplacian to about 20-26% and Tenengrad to about 60-71%.
current full pipeline drops further to about 11-14% Laplacian and 51-60% Tenengrad.
Blur is dominated by crop+resize first, then warp/stabilization resampling and source motion blur.
```

## Affine / Deformation Proxy Evidence

Frame-to-frame affine re-estimation on output videos:

{table(["clip", "variant", "anisotropy_delta_mean", "shear_proxy_mean", "translation_mean"], affine_table_rows)}

Key reading:

```text
Current lp_affine reduces translation but increases anisotropy/shear proxy relative to raw and lp_rigid.
lp_rigid reduces translation without increasing the same shear proxy.
This supports the suspicion that global affine deformation contributes to cloth-like pulling.
However the user still sees pulling in lp_rigid, so rolling shutter / parallax / local non-rigid motion may also dominate.
```

## What We Need From Internal AI

Please do not just suggest parameter tuning. We need mature EIS / production-style guidance:

```text
1. Is global 2D affine/rigid warp fundamentally unsuitable for NUS Running-like high-frequency running clips without gyro?
2. What does the described four-corner cloth-pulling artifact usually mean in production EIS?
3. Should Running be scene-gated as challenge/fail-boundary rather than a main gate?
4. What is the lowest-cost mature approach worth copying: scene gate, gyro-like intent separation, mesh/grid warp, RS correction, foreground/background split, or simply disable/downscale stabilization?
5. Which internal/open-source repo/files/functions should we inspect for this exact artifact class?
```

## Evidence Paths

```text
results/diagnostics/artifact_boundary_v1/artifact_boundary_report.md
results/diagnostics/artifact_boundary_v1/sharpness_metrics.csv
results/diagnostics/artifact_boundary_v1/affine_motion_metrics.csv
results/diagnostics/running_full_candidates/candidate_followup_report.md
results/diagnostics/running_full_candidates/running_lp_affine_strength075_eval.csv
results/diagnostics/running_full_candidates/running_lp_rigid_trim010_eval.csv
C:\\Users\\Admin\\Videos\\orin nx\\artifact_boundary_v1\\
C:\\Users\\Admin\\Videos\\orin nx\\running_full_candidates\\
```
"""

    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.write_text(md, encoding="utf-8")
    print(f"Wrote evidence package: {args.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
