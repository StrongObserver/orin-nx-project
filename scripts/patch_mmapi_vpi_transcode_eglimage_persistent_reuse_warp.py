from __future__ import annotations

import argparse
from pathlib import Path

from patch_mmapi_vpi_transcode_eglimage_per_buffer_reuse_warp import patch_per_buffer_reuse
from patch_mmapi_vpi_transcode_eglimage_warp import patch_main as patch_eglimage_main
from patch_mmapi_vpi_transcode_eglimage_warp import patch_makefile


def patch_persistent_mapping(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "VPI_EGLIMAGE_PERSISTENT_REUSE_WARP" in text:
        print(f"already persistent-reuse patched: {path}")
        return

    # Keep EGLImage mappings alive for the lifetime of the process. This tests
    # whether repeated unmap/remap invalidates VPI wrappers that were updated via
    # vpiImageSetWrapper.
    text = text.replace(
        """            if (NvBufSurfaceUnMapEglImage(input_scratch_surf, 0) != 0)
            {
                abort(ctx);
                cerr << "Unable to unmap VPI input scratch EGLImage" << endl;
                break;
            }
            if (NvBufSurfaceUnMapEglImage(output_scratch_surf, 0) != 0)
            {
                abort(ctx);
                cerr << "Unable to unmap VPI output scratch EGLImage" << endl;
                break;
            }
            auto egl_stage_t4 = std::chrono::high_resolution_clock::now();
""",
        """            auto egl_stage_t4 = std::chrono::high_resolution_clock::now();
""",
        1,
    )
    text = text.replace("VPI_EGLIMAGE_PER_BUFFER_REUSE_WARP frame=", "VPI_EGLIMAGE_PERSISTENT_REUSE_WARP frame=", 1)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Patch MMAPI sample to test persistent EGLImage mappings with per-buffer VPI wrapper reuse.")
    parser.add_argument("--sample-dir", type=Path, required=True)
    args = parser.parse_args()
    path = args.sample_dir / "multivideo_transcode_main.cpp"
    patch_eglimage_main(path)
    patch_per_buffer_reuse(path)
    patch_persistent_mapping(path)
    patch_makefile(args.sample_dir / "Makefile")
    print(f"patched EGLImage persistent per-buffer wrapper reuse transcode: {args.sample_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
