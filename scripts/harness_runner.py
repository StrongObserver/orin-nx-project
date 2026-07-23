import argparse
import csv
import json
from datetime import UTC, datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GATES = REPO_ROOT / "configs" / "harness" / "gates.json"
DEFAULT_CONTRACT = REPO_ROOT / "configs" / "harness" / "contracts" / "jetson_regular05_perf.json"
DEFAULT_LOOP_PROFILES = REPO_ROOT / "configs" / "harness" / "loop_profiles.json"
DEFAULT_EVALUATION_DATASETS = REPO_ROOT / "configs" / "harness" / "evaluation_datasets.json"
DEFAULT_METRIC_SCHEMA = REPO_ROOT / "configs" / "harness" / "metric_schema.json"
DEFAULT_ONBOARDING_MANIFEST = REPO_ROOT / "configs" / "harness" / "onboarding_manifest.json"


def repo_rel(path: Path | str) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def load_gates(path: Path) -> dict:
    data = load_json(path)
    datasets = {item["id"]: item for item in data.get("datasets", [])}
    data["_datasets_by_id"] = datasets
    return data


def read_manifest_names(path: Path) -> list[str]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        return [row.get("name", "") for row in csv.DictReader(f) if row.get("name")]


def command_doctor(args: argparse.Namespace) -> int:
    gates = load_gates(args.gates)
    print(f"gates: {display_path(args.gates)}")
    print(f"schema_version: {gates.get('schema_version')}")
    ok = True
    for dataset in gates.get("datasets", []):
        dataset_id = dataset["id"]
        role = dataset["role"]
        print(f"\n[{dataset_id}] role={role}")
        for key in ("raw_dir", "raw_clip", "manifest", "scene_gate_csv"):
            if key not in dataset:
                continue
            path = repo_rel(dataset[key])
            exists = path.exists()
            ok = ok and exists
            print(f"  {key}: {display_path(path)} exists={exists}")
        if "raw_dir" in dataset:
            raw_dir = repo_rel(dataset["raw_dir"])
            pattern = dataset.get("pattern", "*.mp4")
            clips = sorted(raw_dir.glob(pattern)) if raw_dir.exists() else []
            print(f"  clip_count({pattern}): {len(clips)}")
            expected = dataset.get("expected_clips", [])
            if expected:
                actual = {clip.stem for clip in clips}
                missing = [name for name in expected if name not in actual]
                if missing:
                    ok = False
                    print(f"  missing_expected: {', '.join(missing)}")
        if "manifest" in dataset:
            names = read_manifest_names(repo_rel(dataset["manifest"]))
            if names:
                print(f"  manifest_names: {', '.join(names[:8])}")
    print(f"\ndoctor_status: {'pass' if ok else 'fail'}")
    return 0 if ok else 1


def command_list_gates(args: argparse.Namespace) -> int:
    gates = load_gates(args.gates)
    for dataset in gates.get("datasets", []):
        print(f"{dataset['id']}\t{dataset['role']}\t{dataset['description']}")
    return 0


def command_check_claim(args: argparse.Namespace) -> int:
    gates = load_gates(args.gates)
    dataset = gates["_datasets_by_id"].get(args.gate_id)
    if dataset is None:
        print(f"unknown_gate: {args.gate_id}")
        return 1
    allowed = set(dataset.get("claims_allowed", []))
    forbidden = set(dataset.get("claims_forbidden", []))
    if args.claim in allowed:
        print(f"claim_status: allowed")
        print(f"gate_id: {args.gate_id}")
        print(f"role: {dataset['role']}")
        print(f"claim: {args.claim}")
        return 0
    if args.claim in forbidden:
        print(f"claim_status: forbidden")
        print(f"gate_id: {args.gate_id}")
        print(f"role: {dataset['role']}")
        print(f"claim: {args.claim}")
        print(f"reason: {dataset['description']}")
        return 2
    print(f"claim_status: unknown")
    print(f"gate_id: {args.gate_id}")
    print(f"role: {dataset['role']}")
    print(f"claim: {args.claim}")
    print("reason: claim is not declared in claims_allowed or claims_forbidden")
    return 1


def command_print_contract(args: argparse.Namespace) -> int:
    contract = load_json(args.contract)
    print(json.dumps(contract, ensure_ascii=False, indent=2))
    return 0


def command_onboard(args: argparse.Namespace) -> int:
    manifest = load_json(args.manifest)
    print(f"manifest_id: {manifest.get('manifest_id', '')}")
    print(f"mode: {manifest.get('default_onboarding_mode', '')}")
    print(f"active_loop_contract: {manifest.get('active_loop_contract', '')}")
    print(f"active_task_contract: {manifest.get('active_task_contract', '')}")
    if manifest.get("latest_completed_task_contract"):
        print(f"latest_completed_task_contract: {manifest.get('latest_completed_task_contract', '')}")
    print("\nstartup_sequence:")
    for item in manifest.get("startup_sequence", []):
        print(f"- {item}")
    print("\ntoken_hotspots:")
    for hotspot in manifest.get("token_hotspots_observed", []):
        print(f"- {hotspot.get('source', '')}")
        print(f"  reason: {hotspot.get('cost_reason', '')}")
        print(f"  rule: {hotspot.get('new_rule', '')}")
    print("\nload_on_demand:")
    for route in manifest.get("load_on_demand", []):
        print(f"- trigger: {route.get('trigger', '')}")
        for target in route.get("open", []):
            print(f"  open: {target}")
    print("\nhard_rules:")
    for item in manifest.get("hard_rules", []):
        print(f"- {item}")
    return 0


def command_list_loop_profiles(args: argparse.Namespace) -> int:
    data = load_json(args.loop_profiles)
    for profile in data.get("profiles", []):
        observations = ", ".join(profile.get("external_observation", []))
        print(
            f"{profile['id']}\t"
            f"autonomy={profile.get('recommended_autonomy', '')}\t"
            f"max_attempts={profile.get('max_attempts', '')}\t"
            f"observations={observations}"
        )
    return 0


def command_print_loop_profile(args: argparse.Namespace) -> int:
    data = load_json(args.loop_profiles)
    profiles = {profile["id"]: profile for profile in data.get("profiles", [])}
    profile = profiles.get(args.profile_id)
    if profile is None:
        print(f"unknown_loop_profile: {args.profile_id}")
        return 1
    print(json.dumps(profile, ensure_ascii=False, indent=2))
    return 0


def command_check_loop_rules(args: argparse.Namespace) -> int:
    data = load_json(args.loop_profiles)
    ok = True
    default_rules = data.get("default_rules", {})
    negative_policy = default_rules.get("negative_result_policy", {})
    core_tracks = data.get("active_core_tracks", [])
    profiles = {profile["id"]: profile for profile in data.get("profiles", [])}

    checks = [
        (
            "default_onboarding_mode_progressive",
            default_rules.get("default_onboarding_mode") == "progressive_disclosure",
        ),
        (
            "full_context_preload_forbidden",
            bool(default_rules.get("full_context_preload_forbidden", False)),
        ),
        (
            "onboarding_manifest_declared",
            bool(default_rules.get("onboarding_manifest")),
        ),
        (
            "stable_checkpoint_is_not_terminal_goal",
            bool(default_rules.get("stable_checkpoint_is_not_terminal_goal", False)),
        ),
        (
            "documentation_loop_cannot_replace_core_progress",
            bool(default_rules.get("documentation_loop_cannot_replace_core_progress", False)),
        ),
        (
            "negative_result_is_evidence_not_terminal",
            bool(negative_policy.get("negative_result_is_evidence_not_terminal", False)),
        ),
        (
            "has_active_core_tracks",
            len(core_tracks) >= 3,
        ),
    ]
    for name, passed in checks:
        ok = ok and passed
        print(f"{name}: {'pass' if passed else 'fail'}")

    required_after_negative = set(negative_policy.get("required_after_negative_result", []))
    required_negative_items = {
        "preserve_stable_checkpoint",
        "classify_failure_mode",
        "name_next_core_exploration_route",
        "create_or_select_followup_contract",
    }
    missing_required = sorted(required_negative_items - required_after_negative)
    if missing_required:
        ok = False
        print(f"negative_policy_missing_required: {', '.join(missing_required)}")
    else:
        print("negative_policy_required_items: pass")

    performance_loop = profiles.get("performance_loop", {})
    performance_recovery = set(performance_loop.get("recovery_actions", []))
    required_recovery_fragments = [
        "backend_swap_is_slower",
        "python_dataflow_is_too_expensive",
        "operator_speedup_does_not_become_end_to_end_speedup",
    ]
    for fragment in required_recovery_fragments:
        matched = any(fragment in action for action in performance_recovery)
        ok = ok and matched
        print(f"performance_recovery_{fragment}: {'pass' if matched else 'fail'}")

    documentation_loop = profiles.get("documentation_loop", {})
    doc_stop_reasons = set(documentation_loop.get("stop_reasons", []))
    doc_stop_ok = "would_replace_unfinished_core_track" in doc_stop_reasons
    ok = ok and doc_stop_ok
    print(f"documentation_core_replacement_guard: {'pass' if doc_stop_ok else 'fail'}")

    print(f"loop_rule_status: {'pass' if ok else 'fail'}")
    return 0 if ok else 1


def command_list_evaluation_datasets(args: argparse.Namespace) -> int:
    data = load_json(args.evaluation_datasets)
    for dataset in data.get("datasets", []):
        print(
            f"{dataset['id']}\t"
            f"role={dataset.get('role', '')}\t"
            f"status={dataset.get('status', '')}\t"
            f"priority={dataset.get('priority', '')}\t"
            f"category={dataset.get('category', dataset.get('family', ''))}"
        )
    return 0


def command_check_evaluation_datasets(args: argparse.Namespace) -> int:
    data = load_json(args.evaluation_datasets)
    ok = True
    for dataset in data.get("datasets", []):
        dataset_id = dataset["id"]
        status = dataset.get("status", "")
        print(f"\n[{dataset_id}] role={dataset.get('role', '')} status={status}")
        expected_missing = status in {"missing_download", "planned_reference_only"}
        for key in ("source_archive", "source_extracted_dir", "raw_dir", "stable_reference_dir", "manifest", "metadata", "raw_clip", "prepared_dir"):
            if key not in dataset:
                continue
            path = repo_rel(dataset[key])
            exists = path.exists()
            print(f"  {key}: {display_path(path)} exists={exists}")
            if not exists and not expected_missing and key not in {"prepared_dir"}:
                ok = False
        expected = dataset.get("expected_prepared_clips", [])
        raw_dir_text = dataset.get("raw_dir")
        if expected and raw_dir_text:
            raw_dir = repo_rel(raw_dir_text)
            actual = {clip.stem for clip in raw_dir.glob("*.mp4")} if raw_dir.exists() else set()
            missing = [name for name in expected if name not in actual]
            if missing:
                ok = False
                print(f"  missing_expected: {', '.join(missing)}")
    print(f"\nevaluation_dataset_status: {'pass' if ok else 'fail'}")
    return 0 if ok else 1


def command_list_metric_schema(args: argparse.Namespace) -> int:
    data = load_json(args.metric_schema)
    for layer in data.get("layers", []):
        print(f"{layer['id']}\tauthority={layer.get('authority', '')}")
        for metric in layer.get("metrics", []):
            print(f"  - {metric['id']}")
        for label in layer.get("labels", []):
            print(f"  - {label}")
    return 0


def materialize_template(text: str, date: str) -> str:
    return text.replace("<YYYYMMDD>", date)


def config_slug(contract: dict) -> str:
    cfg = contract["baseline_config"]
    crop = int(round(float(cfg["crop_ratio"]) * 100))
    sharpen = str(cfg["sharpen_strength"]).replace(".", "p")
    estimate = str(cfg["estimate_scale"]).replace(".", "p")
    strength = str(cfg.get("stabilization_strength", 1.0)).replace(".", "p")
    zoom = ""
    if cfg.get("dynamic_zoom", False):
        zoom = f"_dynzoom{str(cfg.get('max_zoom', '')).replace('.', 'p')}"
    return (
        f"crop{crop}{zoom}_{cfg['crop_interpolation']}_sharp{sharpen}_"
        f"{cfg['smoothing_method']}_{cfg['warp_backend']}_est{estimate}"
        f"_strength{strength}"
    )


def review_asset_name(contract: dict, date: str, asset_kind: str = "compare") -> str:
    clip_stem = Path(contract["clip_set_and_roles"]["clip"]).stem
    gate_id = contract["clip_set_and_roles"]["gate_id"]
    platform = contract.get("required_platform_label", "unknown_platform")
    return f"{date}_{gate_id}_{clip_stem}_{platform}_{config_slug(contract)}_{asset_kind}.mp4"


def command_init_evidence(args: argparse.Namespace) -> int:
    contract = load_json(args.contract)
    date = args.date or datetime.now().strftime("%Y%m%d")
    evidence_dir = Path(materialize_template(contract["evidence_output_directory"], date))
    review_dir = Path(materialize_template(contract["review_copy_directory"], date))
    evidence_abs = repo_rel(evidence_dir)
    evidence_abs.mkdir(parents=True, exist_ok=True)
    review_dir.mkdir(parents=True, exist_ok=True)

    contract_copy = evidence_abs / "contract.json"
    contract_copy.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")

    review_csv = evidence_abs / "human_review.csv"
    if not review_csv.exists():
        review_csv.write_text(
            "clip,side_by_side,manual_veto,scene_role,display_decision,notes\n",
            encoding="utf-8",
        )

    run_metadata = evidence_abs / "run_metadata.json"
    if not run_metadata.exists():
        metadata = {
            "contract_id": contract.get("contract_id"),
            "platform_label": args.platform_label or "",
            "platform_note": "Set platform_label to jetson for real Jetson evidence; use windows_simulation for harness self-tests.",
            "is_harness_self_test": bool(args.self_test),
            "created_utc_hint": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        run_metadata.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    command_txt = evidence_abs / "commands.txt"
    command_txt.write_text("\n".join(build_commands(contract, evidence_abs, review_dir)) + "\n", encoding="utf-8")

    print(f"evidence_dir: {display_path(evidence_abs)}")
    print(f"review_dir: {review_dir}")
    print(f"contract_copy: {display_path(contract_copy)}")
    print(f"run_metadata: {display_path(run_metadata)}")
    print(f"review_csv: {display_path(review_csv)}")
    print(f"commands: {display_path(command_txt)}")
    return 0


def find_summary_path(evidence_dir: Path, suffix: str, clip_stem: str) -> Path:
    return evidence_dir / f"{clip_stem}_{suffix}_summary.csv"


def output_suffix(contract: dict) -> str:
    return config_slug(contract)


def build_commands(
    contract: dict,
    evidence_dir: Path | None = None,
    review_dir: Path | None = None,
    date: str | None = None,
) -> list[str]:
    cfg = contract["baseline_config"]
    clip = contract["clip_set_and_roles"]["clip"]
    clip_stem = Path(clip).stem
    suffix = output_suffix(contract)
    date = date or datetime.now().strftime("%Y%m%d")
    if evidence_dir is None:
        evidence_dir = repo_rel(Path(materialize_template(contract["evidence_output_directory"], date)))
    if review_dir is None:
        review_dir = Path(materialize_template(contract["review_copy_directory"], date))
    output_mp4 = evidence_dir / f"{clip_stem}_{suffix}.mp4"
    metrics_csv = evidence_dir / f"{clip_stem}_{suffix}_metrics.csv"
    summary_csv = find_summary_path(evidence_dir, suffix, clip_stem)
    compare_mp4 = evidence_dir / f"{clip_stem}_{suffix}_compare.mp4"
    review_mp4 = review_dir / review_asset_name(contract, date, "compare")

    cpu_cmd = [
        "py -3.12 src\\cpu_stabilize.py",
        f"--input \"{clip}\"",
        f"--output \"{display_path(output_mp4)}\"",
        f"--metrics \"{display_path(metrics_csv)}\"",
        f"--summary \"{display_path(summary_csv)}\"",
        "--smoothing-radius 15",
        f"--smoothing-method {cfg['smoothing_method']}",
        f"--crop-ratio {cfg['crop_ratio']}",
        f"--crop-interpolation {cfg['crop_interpolation']}",
        f"--sharpen-strength {cfg['sharpen_strength']}",
        f"--sharpen-sigma {cfg['sharpen_sigma']}",
        f"--estimate-scale {cfg['estimate_scale']}",
        f"--warp-backend {cfg['warp_backend']}",
        f"--stabilization-strength {cfg.get('stabilization_strength', 1.0)}",
        "--feature-grid-size 12",
        "--foreground-reject-threshold 10",
        "--min-inliers 12",
        "--min-inlier-ratio 0.10",
        "--fallback-mode interpolate",
        f"--lp-trim-ratio {cfg['lp_trim_ratio']}",
        f"--lp-w1 {cfg['lp_w1']}",
        f"--lp-w2 {cfg['lp_w2']}",
        f"--lp-w3 {cfg['lp_w3']}",
        f"--lp-w4 {cfg['lp_w4']}",
        "--mask-safety-max-invalid 0.01",
    ]
    if cfg.get("dynamic_zoom", False):
        cpu_cmd.extend(
            [
                "--dynamic-zoom",
                f"--min-zoom {cfg.get('min_zoom', 1.0)}",
                f"--max-zoom {cfg.get('max_zoom', 1.06)}",
                f"--zoom-rate-limit {cfg.get('zoom_rate_limit', 0.003)}",
                f"--zoom-hysteresis {cfg.get('zoom_hysteresis', 0.02)}",
            ]
        )
    comparison_cmd = [
        "py -3.12 src\\make_comparison.py",
        f"--original \"{clip}\"",
        f"--stabilized \"{display_path(output_mp4)}\"",
        f"--output \"{display_path(compare_mp4)}\"",
    ]
    copy_cmd = f"Copy-Item -LiteralPath \"{display_path(compare_mp4)}\" -Destination \"{review_mp4}\" -Force"
    return [
        " ".join(cpu_cmd),
        " ".join(comparison_cmd),
        copy_cmd,
    ]


def command_print_commands(args: argparse.Namespace) -> int:
    contract = load_json(args.contract)
    date = args.date or datetime.now().strftime("%Y%m%d")
    for command in build_commands(contract, date=date):
        print(command)
        print()
    return 0


def infer_date_from_evidence_dir(path: Path) -> str | None:
    name = path.name
    if len(name) >= 8 and name[:8].isdigit():
        return name[:8]
    return None


def command_validate_evidence(args: argparse.Namespace) -> int:
    contract = load_json(args.contract)
    evidence_dir = repo_rel(args.evidence_dir)
    clip_stem = Path(contract["clip_set_and_roles"]["clip"]).stem
    suffix = output_suffix(contract)
    date = args.date or infer_date_from_evidence_dir(evidence_dir)
    review_dir = args.review_dir
    if review_dir is None and date is not None:
        review_dir = Path(materialize_template(contract["review_copy_directory"], date))
    review_copy = None
    if review_dir is not None:
        review_copy = review_dir / review_asset_name(contract, date, "compare")
    required = [
        evidence_dir / "contract.json",
        evidence_dir / "run_metadata.json",
        evidence_dir / f"{clip_stem}_{suffix}.mp4",
        evidence_dir / f"{clip_stem}_{suffix}_metrics.csv",
        evidence_dir / f"{clip_stem}_{suffix}_summary.csv",
        evidence_dir / f"{clip_stem}_{suffix}_compare.mp4",
        evidence_dir / "human_review.csv",
    ]
    if review_copy is not None:
        required.append(review_copy)
    ok = True
    for path in required:
        exists = path.exists()
        ok = ok and exists
        print(f"{display_path(path)} exists={exists}")
    summary_path = evidence_dir / f"{clip_stem}_{suffix}_summary.csv"
    if summary_path.exists():
        with summary_path.open("r", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        row = rows[0] if rows else {}
        for field in ("avg_estimate_ms", "avg_warp_ms", "total_wall_time_s"):
            present = field in row and row[field] != ""
            ok = ok and present
            print(f"summary_field {field} present={present} value={row.get(field, '')}")
    metadata_path = evidence_dir / "run_metadata.json"
    if metadata_path.exists():
        metadata = load_json(metadata_path)
        platform_label = metadata.get("platform_label", "")
        required_label = contract.get("required_platform_label")
        self_test = bool(metadata.get("is_harness_self_test", False))
        print(f"platform_label: {platform_label}")
        print(f"is_harness_self_test: {self_test}")
        if required_label and not self_test:
            platform_ok = platform_label == required_label
            ok = ok and platform_ok
            print(f"required_platform_label: {required_label} pass={platform_ok}")
        elif required_label and self_test:
            print(f"required_platform_label: {required_label} skipped_for_self_test=True")
    print(f"evidence_status: {'pass' if ok else 'fail'}")
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Orin NX heterogeneous video compute harness control-plane helper.")
    parser.add_argument("--gates", type=Path, default=DEFAULT_GATES)
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="Check configured gate paths and expected clips.")
    doctor.set_defaults(func=command_doctor)

    list_gates = subparsers.add_parser("list-gates", help="List configured gates and roles.")
    list_gates.set_defaults(func=command_list_gates)

    check_claim = subparsers.add_parser("check-claim", help="Check whether a gate may support a project claim.")
    check_claim.add_argument("--gate-id", required=True)
    check_claim.add_argument("--claim", required=True)
    check_claim.set_defaults(func=command_check_claim)

    print_contract = subparsers.add_parser("print-contract", help="Print a Done Contract JSON.")
    print_contract.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    print_contract.set_defaults(func=command_print_contract)

    onboard = subparsers.add_parser("onboard", help="Print lightweight progressive onboarding instructions.")
    onboard.add_argument("--manifest", type=Path, default=DEFAULT_ONBOARDING_MANIFEST)
    onboard.set_defaults(func=command_onboard)

    list_loop_profiles = subparsers.add_parser("list-loop-profiles", help="List Loop Engineering V2 profiles.")
    list_loop_profiles.add_argument("--loop-profiles", type=Path, default=DEFAULT_LOOP_PROFILES)
    list_loop_profiles.set_defaults(func=command_list_loop_profiles)

    print_loop_profile = subparsers.add_parser("print-loop-profile", help="Print one Loop Engineering V2 profile.")
    print_loop_profile.add_argument("--loop-profiles", type=Path, default=DEFAULT_LOOP_PROFILES)
    print_loop_profile.add_argument("--profile-id", required=True)
    print_loop_profile.set_defaults(func=command_print_loop_profile)

    check_loop_rules = subparsers.add_parser("check-loop-rules", help="Check Loop Engineering guardrails against conservative retreat after negative results.")
    check_loop_rules.add_argument("--loop-profiles", type=Path, default=DEFAULT_LOOP_PROFILES)
    check_loop_rules.set_defaults(func=command_check_loop_rules)

    list_eval_datasets = subparsers.add_parser("list-evaluation-datasets", help="List lifecycle evaluation datasets and roles.")
    list_eval_datasets.add_argument("--evaluation-datasets", type=Path, default=DEFAULT_EVALUATION_DATASETS)
    list_eval_datasets.set_defaults(func=command_list_evaluation_datasets)

    check_eval_datasets = subparsers.add_parser("check-evaluation-datasets", help="Check lifecycle evaluation dataset paths.")
    check_eval_datasets.add_argument("--evaluation-datasets", type=Path, default=DEFAULT_EVALUATION_DATASETS)
    check_eval_datasets.set_defaults(func=command_check_evaluation_datasets)

    list_metric_schema = subparsers.add_parser("list-metric-schema", help="List metric schema layers and metric ids.")
    list_metric_schema.add_argument("--metric-schema", type=Path, default=DEFAULT_METRIC_SCHEMA)
    list_metric_schema.set_defaults(func=command_list_metric_schema)

    init_evidence = subparsers.add_parser("init-evidence", help="Create an evidence directory from a contract.")
    init_evidence.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    init_evidence.add_argument("--date", help="YYYYMMDD override; defaults to today.")
    init_evidence.add_argument("--platform-label", help="Evidence platform label, e.g. jetson or windows_simulation.")
    init_evidence.add_argument("--self-test", action="store_true", help="Mark this package as a harness self-test, not project progress.")
    init_evidence.set_defaults(func=command_init_evidence)

    print_commands = subparsers.add_parser("print-commands", help="Print reproducible commands for a contract.")
    print_commands.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    print_commands.add_argument("--date", help="YYYYMMDD override; defaults to today.")
    print_commands.set_defaults(func=command_print_commands)

    validate_evidence = subparsers.add_parser("validate-evidence", help="Check an evidence package for required files.")
    validate_evidence.add_argument("evidence_dir", type=Path)
    validate_evidence.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    validate_evidence.add_argument("--date", help="YYYYMMDD override; inferred from evidence directory when possible.")
    validate_evidence.add_argument("--review-dir", type=Path, help="Override review-copy directory.")
    validate_evidence.set_defaults(func=command_validate_evidence)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
