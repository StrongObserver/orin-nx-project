from pathlib import Path

import cv2


CLIPS = [
    ("gate01_525_bag4", Path(r"C:\Users\Admin\Desktop\5_25_test\bag4\4.mp4")),
    ("gate02_525_bag5", Path(r"C:\Users\Admin\Desktop\5_25_test\bag5\5.mp4")),
    ("gate03_525_bag6", Path(r"C:\Users\Admin\Desktop\5_25_test\bag6\6.mp4")),
    ("gate04_62_main", Path(r"C:\Users\Admin\Desktop\6.2test\1.mp4")),
    ("gate05_62_warm2", Path(r"C:\Users\Admin\Desktop\6.2test\Open Warmstart\2.mp4")),
    ("gate06_62_warm3", Path(r"C:\Users\Admin\Desktop\6.2test\Open Warmstart\3.mp4")),
    ("gate07_62_warm4", Path(r"C:\Users\Admin\Desktop\6.2test\Open Warmstart\4.mp4")),
    ("gate08_log_bag1", Path(r"C:\Users\Admin\Desktop\log_new\bag1\1.mp4")),
    ("gate09_log_bag2", Path(r"C:\Users\Admin\Desktop\log_new\bag2\2.mp4")),
    ("gate10_log_bag3", Path(r"C:\Users\Admin\Desktop\log_new\bag3\3.mp4")),
]


def resize_to_max_side(frame, max_side: int):
    h, w = frame.shape[:2]
    scale = min(1.0, float(max_side) / float(max(w, h)))
    if scale >= 0.999:
        return frame
    return cv2.resize(frame, (int(round(w * scale)), int(round(h * scale))), interpolation=cv2.INTER_AREA)


def main() -> int:
    out_dir = Path("results/gate_matrix/raw_clips")
    out_dir.mkdir(parents=True, exist_ok=True)
    max_frames = 240
    max_side = 720
    for name, src in CLIPS:
        cap = cv2.VideoCapture(str(src))
        if not cap.isOpened():
            print(f"SKIP cannot open: {src}")
            continue
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 20.0)
        ok, frame = cap.read()
        if not ok:
            print(f"SKIP cannot read: {src}")
            cap.release()
            continue
        frame = resize_to_max_side(frame, max_side)
        h, w = frame.shape[:2]
        out_path = out_dir / f"{name}.mp4"
        writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
        if not writer.isOpened():
            raise RuntimeError(f"Cannot open writer: {out_path}")
        writer.write(frame)
        written = 1
        while written < max_frames:
            ok, frame = cap.read()
            if not ok:
                break
            writer.write(resize_to_max_side(frame, max_side))
            written += 1
        cap.release()
        writer.release()
        print(f"WROTE\t{name}\t{w}x{h}\t{fps:.3f}fps\t{written}f\t{out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
