import sys
from pathlib import Path

import cv2


def main() -> int:
    inputs = sys.argv[1:]
    if not inputs:
        roots = [Path.home() / "Desktop", Path.home() / "Downloads"]
        paths = []
        for root in roots:
            if root.exists():
                paths.extend(root.rglob("*.mp4"))
        inputs = [str(path) for path in sorted(paths)]

    for text in inputs:
        text = text.strip().strip('"').strip("'")
        path = Path(text)
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            print(f"FAIL\t{path}")
            continue
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frames / fps if fps > 0 else 0.0
        cap.release()
        size_mb = path.stat().st_size / (1024 * 1024) if path.exists() else 0.0
        print(f"OK\t{width}x{height}\t{fps:.3f}fps\t{frames}f\t{duration:.2f}s\t{size_mb:.1f}MB\t{path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
