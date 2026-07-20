from __future__ import annotations

import argparse
from pathlib import Path

from patch_mmapi_vpi_transcode_eglimage_warp import patch_main as patch_eglimage_main
from patch_mmapi_vpi_transcode_eglimage_warp import patch_makefile


def patch_per_buffer_reuse(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "VPI_EGLIMAGE_PER_BUFFER_REUSE_WARP" in text:
        print(f"already per-buffer-reuse patched: {path}")
        return

    old_decl = """    VPIImage input = NULL;
    VPIImage output = NULL;
    VPIStream stream = NULL;
    VPIStatus status = VPI_SUCCESS;
    static int frame_count = 0;
"""
    new_decl = """    static VPIImage input_wrappers[MAX_BUFFERS];
    static VPIImage output_wrappers[MAX_BUFFERS];
    static bool wrapper_ready[MAX_BUFFERS];
    static bool wrapper_arrays_ready = false;
    static VPIStream stream = NULL;
    static bool stream_ready = false;
    VPIImage input = NULL;
    VPIImage output = NULL;
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
    new_create = """    if (!wrapper_arrays_ready)
    {
        for (int i = 0; i < MAX_BUFFERS; ++i)
        {
            input_wrappers[i] = NULL;
            output_wrappers[i] = NULL;
            wrapper_ready[i] = false;
        }
        wrapper_arrays_ready = true;
    }
    int wrapper_index = current_v4l2_buffer_index;
    if (wrapper_index < 0 || wrapper_index >= MAX_BUFFERS)
    {
        cerr << "Invalid VPI wrapper buffer index: " << wrapper_index << endl;
        goto vpi_fail;
    }
    if (!stream_ready)
    {
        status = vpiStreamCreate(VPI_BACKEND_CUDA, &stream);
        if (status != VPI_SUCCESS) goto vpi_fail;
        stream_ready = true;
    }
    if (!wrapper_ready[wrapper_index])
    {
        status = vpiImageCreateWrapper(&input_data, NULL, VPI_BACKEND_CUDA, &input_wrappers[wrapper_index]);
        if (status != VPI_SUCCESS) goto vpi_fail;
        status = vpiImageCreateWrapper(&output_data, NULL, VPI_BACKEND_CUDA, &output_wrappers[wrapper_index]);
        if (status != VPI_SUCCESS) goto vpi_fail;
        wrapper_ready[wrapper_index] = true;
    }
    else
    {
        status = vpiImageSetWrapper(input_wrappers[wrapper_index], &input_data);
        if (status != VPI_SUCCESS) goto vpi_fail;
        status = vpiImageSetWrapper(output_wrappers[wrapper_index], &output_data);
        if (status != VPI_SUCCESS) goto vpi_fail;
    }
    input = input_wrappers[wrapper_index];
    output = output_wrappers[wrapper_index];
"""
    if old_create not in text:
        raise RuntimeError("VPI create wrapper block not found")
    text = text.replace(old_create, new_create, 1)

    old_destroy = """    vpiImageDestroy(output);
    vpiImageDestroy(input);
    vpiStreamDestroy(stream);
    return 0;
"""
    if old_destroy not in text:
        raise RuntimeError("VPI success destroy block not found")
    text = text.replace(old_destroy, "    return 0;\n", 1)

    old_fail = """    if (output) vpiImageDestroy(output);
    if (input) vpiImageDestroy(input);
    if (stream) vpiStreamDestroy(stream);
    return -1;
}
"""
    new_fail = """    for (int i = 0; i < MAX_BUFFERS; ++i)
    {
        if (output_wrappers[i])
        {
            vpiImageDestroy(output_wrappers[i]);
            output_wrappers[i] = NULL;
        }
        if (input_wrappers[i])
        {
            vpiImageDestroy(input_wrappers[i]);
            input_wrappers[i] = NULL;
        }
        wrapper_ready[i] = false;
    }
    if (stream)
    {
        vpiStreamDestroy(stream);
        stream = NULL;
    }
    stream_ready = false;
    wrapper_arrays_ready = false;
    return -1;
}
"""
    if old_fail not in text:
        raise RuntimeError("VPI fail cleanup block not found")
    text = text.replace(old_fail, new_fail, 1)

    old_call = """            ret = vpi_warp_egl_images(input_scratch_surf->surfaceList[0].mappedAddr.eglImage,
                                      output_scratch_surf->surfaceList[0].mappedAddr.eglImage);
"""
    new_call = """            current_v4l2_buffer_index = static_cast<int>(v4l2_buf.index);
            ret = vpi_warp_egl_images(input_scratch_surf->surfaceList[0].mappedAddr.eglImage,
                                      output_scratch_surf->surfaceList[0].mappedAddr.eglImage);
            current_v4l2_buffer_index = -1;
"""
    if old_call not in text:
        raise RuntimeError("vpi_warp_egl_images call block not found")
    text = text.replace(old_call, new_call, 1)

    global_marker = "static int g_vpi_scratch_fd[MAX_BUFFERS];\n"
    if global_marker in text:
        text = text.replace(global_marker, global_marker + "static int current_v4l2_buffer_index = -1;\n", 1)
    else:
        alt_marker = "static int g_vpi_input_scratch_fd[MAX_BUFFERS];\n"
        if alt_marker not in text:
            raise RuntimeError("scratch fd global marker not found")
        text = text.replace(alt_marker, alt_marker + "static int current_v4l2_buffer_index = -1;\n", 1)

    text = text.replace("VPI_EGLIMAGE_WARP frame=", "VPI_EGLIMAGE_PER_BUFFER_REUSE_WARP frame=", 1)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Patch MMAPI transcode sample to reuse VPI EGLImage wrappers per V4L2 buffer index.")
    parser.add_argument("--sample-dir", type=Path, required=True)
    args = parser.parse_args()
    path = args.sample_dir / "multivideo_transcode_main.cpp"
    patch_eglimage_main(path)
    patch_per_buffer_reuse(path)
    patch_makefile(args.sample_dir / "Makefile")
    print(f"patched EGLImage per-buffer wrapper reuse transcode: {args.sample_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
