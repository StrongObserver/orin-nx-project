import argparse
import csv
from collections import Counter
import json
import sys
from pathlib import Path


def load_roles_csv(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    roles = {}
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if "name" not in (reader.fieldnames or []) or "scenario_role" not in (reader.fieldnames or []):
            raise ValueError("--roles-csv must contain columns: name, scenario_role")
        for row in reader:
            name = row.get("name", "").strip()
            role = row.get("scenario_role", "").strip()
            if not name or not role:
                continue
            if role not in {"gate", "challenge", "diagnostic"}:
                raise ValueError(f"invalid scenario_role for {name}: {role}")
            roles[name] = role
    return roles


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a stabilized gate matrix directory.")
    parser.add_argument("--raw-dir", type=Path, default=Path("results/gate_matrix/raw_clips"))
    parser.add_argument("--stab-dir", type=Path, required=True)
    parser.add_argument("--suffix", required=True, help="Suffix used by run_gate_matrix.py after each clip stem")
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--estimate-scale", type=float, default=1.0)
    parser.add_argument("--max-frames", type=int, default=600)
    parser.add_argument("--warmup-frames", type=int, default=0)
    parser.add_argument("--scenario-role", choices=["gate", "challenge", "diagnostic"], default="gate")
    parser.add_argument("--roles-csv", type=Path, help="Optional per-clip roles CSV with columns: name, scenario_role")
    parser.add_argument("--pattern", default="gate*.mp4", help="Glob pattern for raw clips under --raw-dir")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "src"))
    from evaluate_baseline_v1 import evaluate_pair, flatten_pair_result  # noqa: PLC0415

    roles_by_name = load_roles_csv(args.roles_csv)
    pairs = []
    for raw in sorted(args.raw_dir.glob(args.pattern)):
        name = raw.stem
        stabilized = args.stab_dir / f"{name}_{args.suffix}.mp4"
        metrics = args.stab_dir / f"{name}_{args.suffix}_metrics.csv"
        if stabilized.exists() and metrics.exists():
            pairs.append((name, raw, stabilized, metrics))

    if not pairs:
        raise RuntimeError(f"No evaluated pairs found for suffix={args.suffix} under {args.stab_dir}")

    results = [
        evaluate_pair(
            name,
            raw,
            stabilized,
            0.85,
            args.estimate_scale,
            args.max_frames,
            8,
            45,
            0.0,
            roles_by_name.get(name, args.scenario_role),
            metrics,
            args.warmup_frames,
        )
        for name, raw, stabilized, metrics in pairs
    ]
    rows = [flatten_pair_result(result) for result in results]

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps({"results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    with args.output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote JSON: {args.output_json}")
    print(f"Wrote CSV: {args.output_csv}")
    for row in rows:
        print(
            f"{row['name']}: SR_pose={row['sr_residual_pose']:.3f}, "
            f"residual_improve={row['improve_residual_trans_std']:.3f}, "
            f"acc_top5_improve={row['improve_second_diff_top5_mean']:.3f}, "
            f"black_p95={row['stab_p95_black_border_ratio']:.6f}, "
            f"role={row['scenario_role']}, "
            f"layered={row['layered_acceptance']}"
        )
    role_counts = Counter(row["scenario_role"] for row in rows)
    layered_by_role = Counter((row["scenario_role"], row["layered_acceptance"]) for row in rows)
    print("Role counts:")
    for role, count in sorted(role_counts.items()):
        print(f"  {role}: {count}")
    print("Layered acceptance by role:")
    for (role, layered), count in sorted(layered_by_role.items()):
        print(f"  {role}/{layered}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
