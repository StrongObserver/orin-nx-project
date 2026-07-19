from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Patch a copied MMAPI VPI sample to use a different VPI interpolation mode.")
    parser.add_argument("--sample-dir", type=Path, required=True)
    parser.add_argument("--interp", choices=["linear", "catmull_rom", "nearest"], required=True)
    args = parser.parse_args()

    path = args.sample_dir / "multivideo_transcode_main.cpp"
    text = path.read_text(encoding="utf-8")
    mapping = {
        "linear": "VPI_INTERP_LINEAR",
        "catmull_rom": "VPI_INTERP_CATMULL_ROM",
        "nearest": "VPI_INTERP_NEAREST",
    }
    target = mapping[args.interp]
    replaced = False
    for value in mapping.values():
        if value in text:
            text = text.replace(value, target)
            replaced = True
    if not replaced:
        raise RuntimeError(f"No VPI interpolation token found in {path}")
    path.write_text(text, encoding="utf-8")
    print(f"patched {path} to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
