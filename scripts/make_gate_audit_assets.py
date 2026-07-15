import argparse
import csv
import sys
from pathlib import Path

import cv2

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.make_comparison import make_comparison


AUDIT_COLUMNS = [
    "name",
    "raw_video",
    "stabilized_video",
    "compare_video",
    "sr_residual_pose",
    "improve_residual_trans_std",
    "improve_second_diff_top5_mean",
    "stab_p95_black_border_ratio",
    "layered_acceptance",
    "scene_role",
    "subjective_veto",
    "notes",
]


def load_eval_rows(eval_csv: Path | None) -> dict[str, dict[str, str]]:
    if eval_csv is None:
        return {}
    with eval_csv.open("r", newline="", encoding="utf-8") as f:
        return {row["name"]: row for row in csv.DictReader(f)}


def read_frame_at(video_path: Path, fraction: float):
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    target = int(max(0, min(frame_count - 1, round(frame_count * fraction))))
    cap.set(cv2.CAP_PROP_POS_FRAMES, target)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise RuntimeError(f"Cannot read frame {target} from {video_path}")
    return frame


def resize_to_height(frame, height: int):
    h, w = frame.shape[:2]
    scale = height / float(h)
    return cv2.resize(frame, (int(round(w * scale)), height), interpolation=cv2.INTER_AREA)


def draw_text(frame, text: str, origin: tuple[int, int], scale: float = 0.5):
    x, y = origin
    cv2.putText(frame, text, (x + 1, y + 1), cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 255), 1, cv2.LINE_AA)


def make_contact_sheet(entries: list[dict[str, str]], output_path: Path, thumb_height: int):
    rows = []
    fractions = [0.20, 0.50, 0.80]
    for entry in entries:
        raw = Path(entry["raw_video"])
        stabilized = Path(entry["stabilized_video"])
        thumbs = []
        for fraction in fractions:
            raw_thumb = resize_to_height(read_frame_at(raw, fraction), thumb_height)
            stab_thumb = resize_to_height(read_frame_at(stabilized, fraction), thumb_height)
            thumbs.extend([raw_thumb, stab_thumb])
        row = cv2.hconcat(thumbs)
        label_bar = row.copy()
        label_bar[:] = (30, 30, 30)
        label = (
            f"{entry['name']} | SR={entry['sr_residual_pose']} "
            f"res={entry['improve_residual_trans_std']} "
            f"acc={entry['improve_second_diff_top5_mean']} "
            f"{entry['layered_acceptance']}"
        )
        draw_text(label_bar, label[:180], (12, 26), scale=0.55)
        rows.append(cv2.vconcat([label_bar[:36, :, :], row]))

    max_width = max(row.shape[1] for row in rows)
    padded = []
    for row in rows:
        if row.shape[1] == max_width:
            padded.append(row)
            continue
        pad = cv2.copyMakeBorder(row, 0, 0, 0, max_width - row.shape[1], cv2.BORDER_CONSTANT, value=(30, 30, 30))
        padded.append(pad)
    sheet = cv2.vconcat(padded)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), sheet):
        raise RuntimeError(f"Cannot write contact sheet: {output_path}")


def format_metric(row: dict[str, str], key: str) -> str:
    value = row.get(key, "")
    if value == "":
        return ""
    try:
        return f"{float(value):.3f}"
    except ValueError:
        return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Create review assets for gate-matrix scene audit.")
    parser.add_argument("--raw-dir", type=Path, default=Path("results/gate_matrix/raw_clips"))
    parser.add_argument("--stab-dir", type=Path, required=True)
    parser.add_argument("--suffix", required=True)
    parser.add_argument("--eval-csv", type=Path)
    parser.add_argument("--out-dir", type=Path, default=Path("results/gate_matrix/audit"))
    parser.add_argument("--thumb-height", type=int, default=120)
    parser.add_argument("--no-guides", action="store_true")
    parser.add_argument("--pattern", default="gate*.mp4", help="Glob pattern for raw clips under --raw-dir")
    args = parser.parse_args()

    eval_rows = load_eval_rows(args.eval_csv)
    compare_dir = args.out_dir / "compare"
    compare_dir.mkdir(parents=True, exist_ok=True)

    audit_rows = []
    for raw in sorted(args.raw_dir.glob(args.pattern)):
        name = raw.stem
        stabilized = args.stab_dir / f"{name}_{args.suffix}.mp4"
        if not stabilized.exists():
            print(f"SKIP missing stabilized video: {stabilized}")
            continue
        compare = compare_dir / f"{name}_compare.mp4"
        make_comparison(raw, stabilized, compare, draw_guides=not args.no_guides)

        eval_row = eval_rows.get(name, {})
        audit_rows.append(
            {
                "name": name,
                "raw_video": str(raw),
                "stabilized_video": str(stabilized),
                "compare_video": str(compare),
                "sr_residual_pose": format_metric(eval_row, "sr_residual_pose"),
                "improve_residual_trans_std": format_metric(eval_row, "improve_residual_trans_std"),
                "improve_second_diff_top5_mean": format_metric(eval_row, "improve_second_diff_top5_mean"),
                "stab_p95_black_border_ratio": format_metric(eval_row, "stab_p95_black_border_ratio"),
                "layered_acceptance": eval_row.get("layered_acceptance", ""),
                "scene_role": "",
                "subjective_veto": "",
                "notes": "",
            }
        )

    if not audit_rows:
        raise RuntimeError("No gate audit rows were generated")

    csv_path = args.out_dir / "gate_audit_template.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=AUDIT_COLUMNS)
        writer.writeheader()
        writer.writerows(audit_rows)

    sheet_path = args.out_dir / "gate_audit_contact_sheet.jpg"
    make_contact_sheet(audit_rows, sheet_path, args.thumb_height)
    print(f"Wrote audit CSV: {csv_path}")
    print(f"Wrote contact sheet: {sheet_path}")
    print(f"Wrote compare videos: {compare_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
