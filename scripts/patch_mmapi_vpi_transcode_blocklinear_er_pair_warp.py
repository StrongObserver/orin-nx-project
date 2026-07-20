from __future__ import annotations

import argparse
from pathlib import Path

from patch_mmapi_vpi_transcode_eglimage_warp import patch_main as patch_eglimage_main
from patch_mmapi_vpi_transcode_eglimage_warp import patch_makefile


def patch_blocklinear_er_pair(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "VPI_BLOCKLINEAR_ER_PAIR_PROBE" in text:
        print(f"already block-linear ER pair patched: {path}")
        return

    text = text.replace(
        "scratchParams.layout = NVBUF_LAYOUT_PITCH;\n"
        "            scratchParams.colorFormat = NVBUF_COLOR_FORMAT_NV12_ER;",
        "scratchParams.layout = NVBUF_LAYOUT_BLOCK_LINEAR;\n"
        "            scratchParams.colorFormat = NVBUF_COLOR_FORMAT_NV12_ER;",
        1,
    )
    text = text.replace("VPI_EGLIMAGE_WARP frame=", "VPI_BLOCKLINEAR_ER_PAIR_PROBE frame=", 1)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Patch MMAPI sample to test VPI warp on block-linear NV12_ER matched scratch buffers.")
    parser.add_argument("--sample-dir", type=Path, required=True)
    args = parser.parse_args()
    path = args.sample_dir / "multivideo_transcode_main.cpp"
    patch_eglimage_main(path)
    patch_blocklinear_er_pair(path)
    patch_makefile(args.sample_dir / "Makefile")
    print(f"patched block-linear ER pair VPI warp sample: {args.sample_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
