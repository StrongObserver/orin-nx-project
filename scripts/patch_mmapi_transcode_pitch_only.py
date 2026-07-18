from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Patch MMAPI 16_multivideo_transcode to allocate pitch-linear decoder capture buffers only.")
    parser.add_argument("--sample-dir", type=Path, required=True)
    args = parser.parse_args()
    path = args.sample_dir / "multivideo_transcode_main.cpp"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "            cParams.layout = NVBUF_LAYOUT_BLOCK_LINEAR;",
        "            cParams.layout = NVBUF_LAYOUT_PITCH;",
        1,
    )
    path.write_text(text, encoding="utf-8")
    print(f"patched pitch-only: {args.sample_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
