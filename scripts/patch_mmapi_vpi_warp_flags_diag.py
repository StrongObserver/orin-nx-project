from __future__ import annotations

import argparse
from pathlib import Path


def patch_main(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "VPI_WARP_FLAGS_DIAG" in text:
        print(f"already patched: {path}")
        return

    old = """        status = vpiSubmitPerspectiveWarp(stream, VPI_BACKEND_CUDA, input, xform, output, NULL,
                                          VPI_INTERP_LINEAR, VPI_BORDER_ZERO, 0);
"""
    new = """        uint64_t warp_flags = 0;
        const char *inverse_env = getenv("VPI_FORCE_WARP_INVERSE");
        if (inverse_env != NULL && inverse_env[0] != '\\0' && inverse_env[0] != '0')
        {
            warp_flags |= VPI_WARP_INVERSE;
        }
        const char *precise_env = getenv("VPI_FORCE_PRECISE");
        if (precise_env != NULL && precise_env[0] != '\\0' && precise_env[0] != '0')
        {
            warp_flags |= VPI_PRECISE;
        }
        static bool printed_warp_flags = false;
        if (!printed_warp_flags)
        {
            cerr << "VPI_WARP_FLAGS_DIAG flags=" << warp_flags << endl;
            printed_warp_flags = true;
        }
        status = vpiSubmitPerspectiveWarp(stream, VPI_BACKEND_CUDA, input, xform, output, NULL,
                                          VPI_INTERP_LINEAR, VPI_BORDER_ZERO, warp_flags);
"""
    if old not in text:
        raise RuntimeError("vpiSubmitPerspectiveWarp call block not found")
    text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")
    print(f"patched warp flags diagnostic: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Patch MMAPI VPI sample to allow inverse/precise warp flags via env vars.")
    parser.add_argument("--sample-dir", type=Path, required=True)
    args = parser.parse_args()
    patch_main(args.sample_dir / "multivideo_transcode_main.cpp")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
