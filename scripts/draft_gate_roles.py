import argparse
import csv
from pathlib import Path


OUTPUT_COLUMNS = [
    "name",
    "scenario_role",
    "suggested_scene_role",
    "review_priority",
    "reason",
    "sr_residual_pose",
    "improve_residual_trans_std",
    "improve_second_diff_top5_mean",
    "stab_p95_black_border_ratio",
    "layered_acceptance",
]


def as_float(row: dict[str, str], key: str) -> float:
    value = row.get(key, "")
    if value == "":
        return 0.0
    return float(value)


def draft_role(row: dict[str, str]) -> dict[str, str]:
    sr = as_float(row, "sr_residual_pose")
    residual = as_float(row, "improve_residual_trans_std")
    second = as_float(row, "improve_second_diff_top5_mean")
    layered = row.get("layered_acceptance", "")

    if layered == "pass_all_objective_gates":
        scenario_role = "gate"
        scene_role = "ordinary_shake_candidate"
        priority = "confirm_pass"
        reason = "passes current objective gates; needs visual veto check before becoming evidence"
    elif sr < 0.9 or residual < -0.05 or second < -0.5:
        scenario_role = "diagnostic"
        scene_role = "failure_or_mismatch_candidate"
        priority = "high"
        reason = "large proxy-metric regression; inspect for scene role, bad motion estimate, or visible artifact"
    elif sr >= 1.0 and second >= 0.0:
        scenario_role = "challenge"
        scene_role = "challenge_candidate"
        priority = "medium"
        reason = "some proxy improvement but residual stability gate fails; likely scene-dependent or too weak for hard gate"
    else:
        scenario_role = "diagnostic"
        scene_role = "ambiguous_candidate"
        priority = "medium"
        reason = "mixed proxy metrics; keep out of hard quality gate until visual role is known"

    return {
        "name": row["name"],
        "scenario_role": scenario_role,
        "suggested_scene_role": scene_role,
        "review_priority": priority,
        "reason": reason,
        "sr_residual_pose": f"{sr:.3f}",
        "improve_residual_trans_std": f"{residual:.3f}",
        "improve_second_diff_top5_mean": f"{second:.3f}",
        "stab_p95_black_border_ratio": f"{as_float(row, 'stab_p95_black_border_ratio'):.6f}",
        "layered_acceptance": layered,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Draft conservative per-clip roles from gate evaluation metrics.")
    parser.add_argument("--eval-csv", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    args = parser.parse_args()

    with args.eval_csv.open("r", newline="", encoding="utf-8") as f:
        rows = [draft_role(row) for row in csv.DictReader(f)]

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote role draft: {args.output_csv}")
    for row in rows:
        print(f"{row['name']}: {row['scenario_role']} / {row['suggested_scene_role']} / {row['review_priority']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
