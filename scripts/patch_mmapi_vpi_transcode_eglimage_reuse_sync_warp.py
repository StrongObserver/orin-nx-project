from __future__ import annotations

import argparse
from pathlib import Path

from patch_mmapi_vpi_transcode_eglimage_reuse_warp import patch_reuse
from patch_mmapi_vpi_transcode_eglimage_warp import patch_main as patch_eglimage_main
from patch_mmapi_vpi_transcode_eglimage_warp import patch_makefile


def patch_sync(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "VPI_EGLIMAGE_REUSE_SYNC_WARP" in text:
        print(f"already sync-reuse patched: {path}")
        return

    old_call = """            ret = vpi_warp_egl_images(input_scratch_surf->surfaceList[0].mappedAddr.eglImage,
                                      output_scratch_surf->surfaceList[0].mappedAddr.eglImage);
            auto egl_stage_t3 = std::chrono::high_resolution_clock::now();
"""
    new_call = """            if (NvBufSurfaceSyncForDevice(input_scratch_surf, 0, -1) != 0)
            {
                abort(ctx);
                cerr << "Unable to sync VPI input scratch for device" << endl;
                break;
            }
            if (NvBufSurfaceSyncForDevice(output_scratch_surf, 0, -1) != 0)
            {
                abort(ctx);
                cerr << "Unable to sync VPI output scratch for device before warp" << endl;
                break;
            }
            ret = vpi_warp_egl_images(input_scratch_surf->surfaceList[0].mappedAddr.eglImage,
                                      output_scratch_surf->surfaceList[0].mappedAddr.eglImage);
            if (NvBufSurfaceSyncForDevice(output_scratch_surf, 0, -1) != 0)
            {
                abort(ctx);
                cerr << "Unable to sync VPI output scratch for device after warp" << endl;
                break;
            }
            auto egl_stage_t3 = std::chrono::high_resolution_clock::now();
"""
    if old_call not in text:
        raise RuntimeError("vpi_warp_egl_images timing block not found")
    text = text.replace(old_call, new_call, 1)
    text = text.replace("VPI_EGLIMAGE_REUSE_WARP frame=", "VPI_EGLIMAGE_REUSE_SYNC_WARP frame=", 1)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Patch MMAPI transcode sample to test full wrapper reuse with explicit NvBufSurfaceSyncForDevice calls.")
    parser.add_argument("--sample-dir", type=Path, required=True)
    args = parser.parse_args()
    path = args.sample_dir / "multivideo_transcode_main.cpp"
    patch_eglimage_main(path)
    patch_reuse(path)
    patch_sync(path)
    patch_makefile(args.sample_dir / "Makefile")
    print(f"patched EGLImage full wrapper reuse with sync: {args.sample_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
