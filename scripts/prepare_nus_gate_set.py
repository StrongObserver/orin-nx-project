import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from evaluate_baseline_v1 import analyze_video, safe_ratio  # noqa: E402


@dataclass(frozen=True)
class ClipSpec:
    name: str
    category: str
    index: int
    role: str
    notes: str


DEFAULT_SELECTION = [
    ClipSpec("nus01_regular_0", "Regular", 0, "gate", "ordinary handheld shake"),
    ClipSpec("nus02_regular_14", "Regular", 14, "gate", "ordinary handheld shake, short clip"),
    ClipSpec("nus03_running_0", "Running", 0, "challenge", "high-frequency running shake"),
    ClipSpec("nus04_running_4", "Running", 4, "challenge", "running shake with stronger translation"),
    ClipSpec("nus05_quickrot_0", "QuickRotation", 0, "challenge", "fast rotation stress case"),
    ClipSpec("nus06_quickrot_1", "QuickRotation", 1, "challenge", "fast rotation stress case"),
    ClipSpec("nus07_zooming_0", "Zooming", 0, "diagnostic", "intentional zoom, not a pure hard gate"),
    ClipSpec("nus08_zooming_1", "Zooming", 1, "diagnostic", "intentional zoom, not a pure hard gate"),
    ClipSpec("nus09_parallax_0", "Parallax", 0, "challenge", "depth variation and parallax"),
    ClipSpec("nus10_crowd_0", "Crowd", 0, "diagnostic", "foreground/crowd motion stress case"),
]

KNOWN_CATEGORIES = ["Regular", "Running", "QuickRotation", "Zooming", "Parallax", "Crowd", "Driving"]

MANIFEST_COLUMNS = [
    "name",
    "category",
    "index",
    "scenario_role",
    "raw_clip",
    "stable_reference_clip",
    "source_input_video",
    "source_stable_video",
    "source_url",
    "source_dataset",
    "source_citation",
    "license",
    "start_s",
    "target_duration_s",
    "notes",
]

METADATA_COLUMNS = [
    "name",
    "category",
    "scenario_role",
    "width",
    "height",
    "fps",
    "frames",
    "duration_s",
    "raw_avg_tracked_features",
    "raw_valid_motion_frames",
    "raw_motion_p95",
    "raw_residual_pose_energy",
    "stable_reference_residual_pose_energy",
    "reference_sr_residual_pose",
    "mean_luma",
    "laplacian_var_mean",
    "quality_pass",
    "quality_reasons",
]


def resize_to_max_side(frame, max_side: int):
    h, w = frame.shape[:2]
    scale = min(1.0, float(max_side) / float(max(w, h)))
    if scale >= 0.999:
        return frame
    return cv2.resize(frame, (int(round(w * scale)), int(round(h * scale))), interpolation=cv2.INTER_AREA)


def open_video(path: Path):
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {path}")
    return cap


def read_video_info(path: Path) -> dict:
    cap = open_video(path)
    info = {
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "fps": float(cap.get(cv2.CAP_PROP_FPS) or 0.0),
        "frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
    }
    cap.release()
    info["duration_s"] = info["frames"] / info["fps"] if info["fps"] > 0 else 0.0
    return info


def draw_text(frame, text: str, origin: tuple[int, int], scale: float = 0.5):
    x, y = origin
    cv2.putText(frame, text, (x + 1, y + 1), cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 255), 1, cv2.LINE_AA)


def read_frame_at(video_path: Path, fraction: float):
    cap = open_video(video_path)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    target = int(max(0, min(frame_count - 1, round(frame_count * fraction))))
    cap.set(cv2.CAP_PROP_POS_FRAMES, target)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise RuntimeError(f"Cannot read frame {target} from {video_path}")
    return frame


def make_contact_sheet(rows: list[dict[str, str]], output_path: Path, thumb_height: int):
    sheet_rows = []
    for row in rows:
        frames = []
        for fraction in (0.20, 0.50, 0.80):
            raw = resize_to_height(read_frame_at(Path(row["raw_clip"]), fraction), thumb_height)
            stable = resize_to_height(read_frame_at(Path(row["stable_reference_clip"]), fraction), thumb_height)
            frames.extend([raw, stable])
        images = cv2.hconcat(frames)
        label = images.copy()
        label[:] = (30, 30, 30)
        draw_text(label, f"{row['name']} | {row['category']} | {row['scenario_role']} | {row['quality_reasons']}"[:180], (12, 24))
        sheet_rows.append(cv2.vconcat([label[:34, :, :], images]))

    max_width = max(r.shape[1] for r in sheet_rows)
    padded = []
    for row in sheet_rows:
        if row.shape[1] < max_width:
            row = cv2.copyMakeBorder(row, 0, 0, 0, max_width - row.shape[1], cv2.BORDER_CONSTANT, value=(30, 30, 30))
        padded.append(row)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), cv2.vconcat(padded)):
        raise RuntimeError(f"Cannot write contact sheet: {output_path}")


def resize_to_height(frame, height: int):
    h, w = frame.shape[:2]
    scale = height / float(h)
    return cv2.resize(frame, (int(round(w * scale)), height), interpolation=cv2.INTER_AREA)


def copy_clip(src: Path, dst: Path, start_s: float, duration_s: float, max_side: int):
    cap = open_video(src)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    start_frame = max(0, int(round(start_s * fps)))
    max_frames = max(1, int(round(duration_s * fps)))
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    ok, first = cap.read()
    if not ok:
        cap.release()
        raise RuntimeError(f"Cannot read first selected frame from {src}")
    first = resize_to_max_side(first, max_side)
    h, w = first.shape[:2]

    dst.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(dst), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    if not writer.isOpened():
        cap.release()
        raise RuntimeError(f"Cannot open writer: {dst}")

    writer.write(first)
    frames_written = 1
    while frames_written < max_frames:
        ok, frame = cap.read()
        if not ok:
            break
        writer.write(resize_to_max_side(frame, max_side))
        frames_written += 1

    cap.release()
    writer.release()
    return frames_written, fps


def luma_and_texture(video_path: Path, max_samples: int = 24) -> tuple[float, float]:
    cap = open_video(video_path)
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if frames <= 0:
        cap.release()
        return 0.0, 0.0
    indices = np.linspace(0, max(0, frames - 1), min(max_samples, frames), dtype=int)
    lumas = []
    lap_vars = []
    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
        ok, frame = cap.read()
        if not ok:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        lumas.append(float(np.mean(gray)))
        lap_vars.append(float(cv2.Laplacian(gray, cv2.CV_64F).var()))
    cap.release()
    return (float(np.mean(lumas)) if lumas else 0.0, float(np.mean(lap_vars)) if lap_vars else 0.0)


def qualify_clip(row: dict, args) -> tuple[bool, str]:
    reasons = []
    if row["duration_s"] < args.min_duration_s:
        reasons.append(f"duration<{args.min_duration_s:g}s")
    if row["duration_s"] > args.max_duration_s:
        reasons.append(f"duration>{args.max_duration_s:g}s")
    if row["raw_avg_tracked_features"] < args.min_tracked_features:
        reasons.append(f"tracked<{args.min_tracked_features:g}")
    if row["raw_motion_p95"] < args.min_motion_p95:
        reasons.append(f"motion_p95<{args.min_motion_p95:g}")
    if row["laplacian_var_mean"] < args.min_laplacian_var:
        reasons.append(f"texture<{args.min_laplacian_var:g}")
    if row["reference_sr_residual_pose"] < args.min_reference_sr:
        reasons.append(f"stable_ref_sr<{args.min_reference_sr:g}")
    return not reasons, "; ".join(reasons) if reasons else "ok"


def prepare_one(spec: ClipSpec, args) -> tuple[dict[str, str], dict[str, str]]:
    src_dir = args.extracted_root / spec.category
    source_raw = src_dir / f"{spec.index}.avi"
    source_stable = src_dir / f"{spec.index}stb.avi"
    if not source_raw.exists():
        raise FileNotFoundError(f"Missing NUS input video: {source_raw}")
    if not source_stable.exists():
        raise FileNotFoundError(f"Missing NUS stable reference video: {source_stable}")

    raw_clip = args.out_dir / "raw_clips" / f"{spec.name}.mp4"
    stable_clip = args.out_dir / "stable_reference" / f"{spec.name}_stable.mp4"
    copy_clip(source_raw, raw_clip, args.start_s, args.duration_s, args.max_side)
    copy_clip(source_stable, stable_clip, args.start_s, args.duration_s, args.max_side)

    info = read_video_info(raw_clip)
    raw_metrics = analyze_video(raw_clip, estimate_scale=1.0, max_frames=0, black_threshold=8, residual_radius=45, angle_scale=0.0)
    stable_metrics = analyze_video(stable_clip, estimate_scale=1.0, max_frames=0, black_threshold=8, residual_radius=45, angle_scale=0.0)
    mean_luma, laplacian_var = luma_and_texture(raw_clip)
    reference_sr = safe_ratio(raw_metrics["residual_pose_energy"], stable_metrics["residual_pose_energy"]) or 0.0

    metadata = {
        "name": spec.name,
        "category": spec.category,
        "scenario_role": spec.role,
        "width": info["width"],
        "height": info["height"],
        "fps": f"{info['fps']:.3f}",
        "frames": info["frames"],
        "duration_s": f"{info['duration_s']:.3f}",
        "raw_avg_tracked_features": f"{raw_metrics['avg_tracked_features']:.3f}",
        "raw_valid_motion_frames": raw_metrics["valid_motion_frames"],
        "raw_motion_p95": f"{raw_metrics['motion_p95']:.3f}",
        "raw_residual_pose_energy": f"{raw_metrics['residual_pose_energy']:.3f}",
        "stable_reference_residual_pose_energy": f"{stable_metrics['residual_pose_energy']:.3f}",
        "reference_sr_residual_pose": f"{reference_sr:.3f}",
        "mean_luma": f"{mean_luma:.3f}",
        "laplacian_var_mean": f"{laplacian_var:.3f}",
    }
    quality_pass, quality_reasons = qualify_clip(
        {
            "duration_s": info["duration_s"],
            "raw_avg_tracked_features": raw_metrics["avg_tracked_features"],
            "raw_motion_p95": raw_metrics["motion_p95"],
            "laplacian_var_mean": laplacian_var,
            "reference_sr_residual_pose": reference_sr,
        },
        args,
    )
    metadata["quality_pass"] = str(quality_pass)
    metadata["quality_reasons"] = quality_reasons

    manifest = {
        "name": spec.name,
        "category": spec.category,
        "index": spec.index,
        "scenario_role": spec.role,
        "raw_clip": str(raw_clip),
        "stable_reference_clip": str(stable_clip),
        "source_input_video": str(source_raw),
        "source_stable_video": str(source_stable),
        "source_url": f"http://liushuaicheng.org/SIGGRAPH2013/data/{spec.category}.zip",
        "source_dataset": "NUS video stabilization dataset / Bundled Camera Paths for Video Stabilization",
        "source_citation": "Liu, Yuan, Tan, Sun, Bundled Camera Paths for Video Stabilization, ACM TOG/SIGGRAPH 2013",
        "license": "Apache License 2.0 as declared by ModelScope mirror zcmaas/NUS_video-stabilization",
        "start_s": f"{args.start_s:.3f}",
        "target_duration_s": f"{args.duration_s:.3f}",
        "notes": spec.notes,
    }
    return manifest, metadata


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def copy_review_assets(out_dir: Path, review_dir: Path):
    if review_dir is None:
        return
    review_dir.mkdir(parents=True, exist_ok=True)
    for src in [
        out_dir / "nus_gate_manifest.csv",
        out_dir / "nus_gate_metadata.csv",
        out_dir / "nus_gate_contact_sheet.jpg",
    ]:
        if src.exists():
            dst = review_dir / src.name
            dst.write_bytes(src.read_bytes())
    for subdir in ("raw_clips", "stable_reference"):
        target = review_dir / subdir
        target.mkdir(parents=True, exist_ok=True)
        for src in sorted((out_dir / subdir).glob("*.mp4")):
            (target / src.name).write_bytes(src.read_bytes())


def parse_indices(value: str) -> list[int]:
    indices = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start = int(start_s)
            end = int(end_s)
            step = 1 if end >= start else -1
            indices.extend(range(start, end + step, step))
        else:
            indices.append(int(part))
    return indices


def available_indices(extracted_root: Path, category: str) -> list[int]:
    source_dir = extracted_root / category
    if not source_dir.exists():
        raise FileNotFoundError(f"Missing NUS category directory: {source_dir}")
    indices = []
    for path in sorted(source_dir.glob("*.avi")):
        if path.stem.endswith("stb"):
            continue
        if path.stem.isdigit():
            indices.append(int(path.stem))
    return sorted(indices)


def build_selection(args) -> list[ClipSpec]:
    if not args.category:
        return DEFAULT_SELECTION

    indices = parse_indices(args.indices) if args.indices else available_indices(args.extracted_root, args.category)
    if not indices:
        raise ValueError(f"No indices selected for category {args.category}")

    category_slug = args.category.lower()
    selection = []
    for ordinal, index in enumerate(indices, start=1):
        name = f"{args.name_prefix}{ordinal:02d}_{category_slug}_{index}"
        notes = args.notes or f"{args.category} NUS clip {index}"
        selection.append(ClipSpec(name, args.category, index, args.role, notes))
    return selection


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a 10-clip NUS EIS gate set with validation metadata.")
    parser.add_argument("--extracted-root", type=Path, default=Path("data/sources/NUS_extracted"))
    parser.add_argument("--out-dir", type=Path, default=Path("results/nus_gate_matrix"))
    parser.add_argument("--review-dir", type=Path, default=Path.home() / "Videos" / "orin nx" / "nus_gate_v1")
    parser.add_argument("--duration-s", type=float, default=8.0)
    parser.add_argument("--start-s", type=float, default=0.0)
    parser.add_argument("--max-side", type=int, default=720)
    parser.add_argument("--thumb-height", type=int, default=110)
    parser.add_argument("--category", choices=KNOWN_CATEGORIES, help="Prepare a single NUS category instead of the default mixed set")
    parser.add_argument("--indices", default="", help="Comma/range list such as 0,4,7-9. If omitted with --category, all available indices are used")
    parser.add_argument("--role", choices=["gate", "challenge", "diagnostic"], default="gate")
    parser.add_argument("--name-prefix", default="gate")
    parser.add_argument("--notes", default="")
    parser.add_argument("--min-duration-s", type=float, default=7.5)
    parser.add_argument("--max-duration-s", type=float, default=8.2)
    parser.add_argument("--min-tracked-features", type=float, default=60.0)
    parser.add_argument("--min-motion-p95", type=float, default=0.4)
    parser.add_argument("--min-laplacian-var", type=float, default=15.0)
    parser.add_argument("--min-reference-sr", type=float, default=0.8)
    args = parser.parse_args()

    manifests = []
    metadata_rows = []
    selection = build_selection(args)
    for spec in selection:
        manifest, metadata = prepare_one(spec, args)
        manifests.append(manifest)
        metadata_rows.append(metadata)
        print(f"{spec.name}: {metadata['quality_pass']} {metadata['quality_reasons']}")

    write_csv(args.out_dir / "nus_gate_manifest.csv", MANIFEST_COLUMNS, manifests)
    write_csv(args.out_dir / "nus_gate_metadata.csv", METADATA_COLUMNS, metadata_rows)
    sheet_rows = []
    for manifest, metadata in zip(manifests, metadata_rows):
        row = dict(manifest)
        row.update(metadata)
        sheet_rows.append(row)
    make_contact_sheet(sheet_rows, args.out_dir / "nus_gate_contact_sheet.jpg", args.thumb_height)
    copy_review_assets(args.out_dir, args.review_dir)

    failed = [row for row in metadata_rows if row["quality_pass"] != "True"]
    print(f"Wrote manifest: {args.out_dir / 'nus_gate_manifest.csv'}")
    print(f"Wrote metadata: {args.out_dir / 'nus_gate_metadata.csv'}")
    print(f"Wrote contact sheet: {args.out_dir / 'nus_gate_contact_sheet.jpg'}")
    print(f"Copied review assets: {args.review_dir}")
    if failed:
        print("Quality validation failures:")
        for row in failed:
            print(f"  {row['name']}: {row['quality_reasons']}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
