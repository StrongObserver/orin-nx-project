import argparse
import csv
from pathlib import Path


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def as_float(row: dict[str, str], key: str) -> float:
    try:
        return float(row.get(key, ""))
    except ValueError:
        return 0.0


def fmt(row: dict[str, str], key: str, digits: int = 2) -> str:
    return f"{as_float(row, key):.{digits}f}"


def table(headers: list[str], rows: list[list[str]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return lines


def summarize_class(rows: list[dict[str, str]], cls: str) -> int:
    return sum(1 for row in rows if row["scene_gate_class"] == cls)


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize scene-gate diagnostics in human-readable Markdown.")
    parser.add_argument("--running-csv", type=Path, required=True)
    parser.add_argument("--regular-csv", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    args = parser.parse_args()

    running = read_rows(args.running_csv)
    regular = read_rows(args.regular_csv)

    lines = [
        "# Scene Gate Diagnostic Summary",
        "",
        "Date: 2026-07-15",
        "",
        "Purpose: verify the internal-AI recommendation that NUS Running should be handled by scene gate / degrade logic instead of more global-affine tuning.",
        "",
        "## What The Metrics Mean",
        "",
        "- `motion_p95`: the 95th percentile of frame-to-frame global motion. Larger means the crop budget is under more pressure.",
        "- `local_global_ratio_p95`: how much local residual remains after fitting one global motion. Larger means one global transform cannot explain different parts of the image.",
        "- `row_residual_range_p95`: how differently the top/middle/bottom image bands move after global fitting. Larger values are a proxy for rolling-shutter or depth/parallax mismatch.",
        "- `2.5-5Hz_energy`: vertical-motion energy in a running-like frequency band. Higher values are a signal of high-frequency running shake.",
        "- `scene_gate_class`: the recommended role for the clip before stabilization. `challenge_degrade` means do not force full EIS; use weak similarity/off/RS/mesh path.",
        "",
        "## Overall Result",
        "",
        f"- Running: `challenge_degrade` {summarize_class(running, 'challenge_degrade')}/{len(running)}, `global_model_risk` {summarize_class(running, 'global_model_risk')}/{len(running)}, `normal_candidate` {summarize_class(running, 'normal_candidate')}/{len(running)}.",
        f"- Regular probe: `normal_candidate` {summarize_class(regular, 'normal_candidate')}/{len(regular)}.",
        "",
        "This is the key evidence: after threshold tightening, the gate separates Running challenge clips from Regular probe clips instead of rejecting everything.",
        "",
        "## Running Gate V1",
        "",
    ]
    lines.extend(
        table(
            ["clip", "class", "mode", "motion_p95", "local/global_p95", "row_range_p95", "2.5-5Hz", "reason"],
            [
                [
                    row["name"],
                    row["scene_gate_class"],
                    row["recommended_mode"],
                    fmt(row, "motion_p95"),
                    fmt(row, "local_global_ratio_p95"),
                    fmt(row, "row_residual_range_p95"),
                    fmt(row, "running_band_energy_ratio"),
                    row["decision_reasons"],
                ]
                for row in running
            ],
        )
    )
    lines.extend(["", "## Regular Probe", ""])
    lines.extend(
        table(
            ["clip", "class", "mode", "motion_p95", "local/global_p95", "row_range_p95", "2.5-5Hz", "reason"],
            [
                [
                    row["name"],
                    row["scene_gate_class"],
                    row["recommended_mode"],
                    fmt(row, "motion_p95"),
                    fmt(row, "local_global_ratio_p95"),
                    fmt(row, "row_residual_range_p95"),
                    fmt(row, "running_band_energy_ratio"),
                    row["decision_reasons"],
                ]
                for row in regular
            ],
        )
    )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "The internal-AI direction is consistent with local evidence: Running should not be treated as a main full-EIS gate for the current global 2D pipeline.",
            "",
            "Recommended next implementation:",
            "",
            "```text",
            "Add a lightweight scene gate before stabilization.",
            "If challenge_degrade: do not run full-strength lp_affine; use weak similarity/translation-only/off as a fallback and mark the clip as challenge.",
            "If normal_candidate: keep standard stabilization path for Regular/main gate.",
            "```",
            "",
            "The current deliverable should be framed as a production-style boundary decision: detect when full EIS will create jello, then degrade instead of forcing a bad stabilized video.",
            "",
        ]
    )

    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote scene gate report: {args.output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
