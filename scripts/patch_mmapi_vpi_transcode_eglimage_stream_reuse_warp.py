from __future__ import annotations

import argparse
from pathlib import Path

from patch_mmapi_vpi_transcode_eglimage_warp import patch_main as patch_eglimage_main
from patch_mmapi_vpi_transcode_eglimage_warp import patch_makefile


def patch_stream_reuse(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "VPI_EGLIMAGE_STREAM_REUSE_WARP" in text:
        print(f"already stream-reuse patched: {path}")
        return

    old_decl = """    VPIImage input = NULL;
    VPIImage output = NULL;
    VPIStream stream = NULL;
    VPIStatus status = VPI_SUCCESS;
    static int frame_count = 0;
"""
    new_decl = """    VPIImage input = NULL;
    VPIImage output = NULL;
    static VPIStream stream = NULL;
    static bool stream_ready = false;
    VPIStatus status = VPI_SUCCESS;
    static int frame_count = 0;
"""
    if old_decl not in text:
        raise RuntimeError("VPI local declaration block not found")
    text = text.replace(old_decl, new_decl, 1)

    old_create = """    status = vpiStreamCreate(VPI_BACKEND_CUDA, &stream);
    if (status != VPI_SUCCESS) goto vpi_fail;
    status = vpiImageCreateWrapper(&input_data, NULL, VPI_BACKEND_CUDA, &input);
    if (status != VPI_SUCCESS) goto vpi_fail;
    status = vpiImageCreateWrapper(&output_data, NULL, VPI_BACKEND_CUDA, &output);
    if (status != VPI_SUCCESS) goto vpi_fail;
"""
    new_create = """    if (!stream_ready)
    {
        status = vpiStreamCreate(VPI_BACKEND_CUDA, &stream);
        if (status != VPI_SUCCESS) goto vpi_fail;
        stream_ready = true;
    }
    status = vpiImageCreateWrapper(&input_data, NULL, VPI_BACKEND_CUDA, &input);
    if (status != VPI_SUCCESS) goto vpi_fail;
    status = vpiImageCreateWrapper(&output_data, NULL, VPI_BACKEND_CUDA, &output);
    if (status != VPI_SUCCESS) goto vpi_fail;
"""
    if old_create not in text:
        raise RuntimeError("VPI create wrapper block not found")
    text = text.replace(old_create, new_create, 1)

    old_destroy = """    vpiImageDestroy(output);
    vpiImageDestroy(input);
    vpiStreamDestroy(stream);
    return 0;
"""
    new_destroy = """    vpiImageDestroy(output);
    vpiImageDestroy(input);
    return 0;
"""
    if old_destroy not in text:
        raise RuntimeError("VPI success destroy block not found")
    text = text.replace(old_destroy, new_destroy, 1)

    old_fail = """    if (output) vpiImageDestroy(output);
    if (input) vpiImageDestroy(input);
    if (stream) vpiStreamDestroy(stream);
    return -1;
}
"""
    new_fail = """    if (output) vpiImageDestroy(output);
    if (input) vpiImageDestroy(input);
    if (stream)
    {
        vpiStreamDestroy(stream);
        stream = NULL;
    }
    stream_ready = false;
    return -1;
}
"""
    if old_fail not in text:
        raise RuntimeError("VPI fail cleanup block not found")
    text = text.replace(old_fail, new_fail, 1)

    text = text.replace("VPI_EGLIMAGE_WARP frame=", "VPI_EGLIMAGE_STREAM_REUSE_WARP frame=", 1)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Patch MMAPI transcode sample to reuse only the VPI stream while recreating EGLImage wrappers per frame.")
    parser.add_argument("--sample-dir", type=Path, required=True)
    args = parser.parse_args()
    path = args.sample_dir / "multivideo_transcode_main.cpp"
    patch_eglimage_main(path)
    patch_stream_reuse(path)
    patch_makefile(args.sample_dir / "Makefile")
    print(f"patched EGLImage stream-reuse transcode: {args.sample_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
