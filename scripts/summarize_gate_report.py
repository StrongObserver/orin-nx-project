import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path


def as_float(row: dict[str, str], key: str) -> float:
    value = row.get(key, "")
    if value == "":
        return 0.0
    return float(value)


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize gate-matrix evaluation by scenario role.")
    parser.add_argument("--eval-csv", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    parser.add_argument("--title", default="Gate Matrix Report")
    args = parser.parse_args()

    with args.eval_csv.open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise RuntimeError(f"No rows found: {args.eval_csv}")

    by_role: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_role[row.get("scenario_role", "gate")].append(row)

    lines = [
        f"# {args.title}",
        "",
        f"Source CSV: `{args.eval_csv}`",
        "",
        "## Overall",
        "",
    ]
    overall = Counter(row["layered_acceptance"] for row in rows)
    lines.append(f"- clips: {len(rows)}")
    lines.append(f"- complete objective pass: {overall.get('pass_all_objective_gates', 0)}/{len(rows)}")
    lines.append(f"- black hard fail: {sum(1 for row in rows if row['black_border_class'] == 'fail')}/{len(rows)}")
    lines.append(f"- crop hard fail: {sum(1 for row in rows if row['crop_loss_class'] == 'fail')}/{len(rows)}")
    lines.append("")

    for role in sorted(by_role):
        role_rows = by_role[role]
        layered = Counter(row["layered_acceptance"] for row in role_rows)
        lines.extend(
            [
                f"## Role: {role}",
                "",
                f"- clips: {len(role_rows)}",
                f"- complete objective pass: {layered.get('pass_all_objective_gates', 0)}/{len(role_rows)}",
                f"- mean SR residual pose: {mean([as_float(row, 'sr_residual_pose') for row in role_rows]):.3f}",
                f"- mean residual improvement: {mean([as_float(row, 'improve_residual_trans_std') for row in role_rows]):.3f}",
                f"- mean second-diff improvement: {mean([as_float(row, 'improve_second_diff_top5_mean') for row in role_rows]):.3f}",
                "",
                "| clip | layered | SR | residual improve | second improve | black p95 |",
                "|---|---|---:|---:|---:|---:|",
            ]
        )
        for row in role_rows:
            lines.append(
                f"| {row['name']} | {row['layered_acceptance']} | "
                f"{as_float(row, 'sr_residual_pose'):.3f} | "
                f"{as_float(row, 'improve_residual_trans_std'):.3f} | "
                f"{as_float(row, 'improve_second_diff_top5_mean'):.3f} | "
                f"{as_float(row, 'stab_p95_black_border_ratio'):.6f} |"
            )
        lines.append("")

    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote report: {args.output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
