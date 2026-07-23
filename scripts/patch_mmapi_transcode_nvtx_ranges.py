from __future__ import annotations

import argparse
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"marker not found: {label}")
    return text.replace(old, new, 1)


def ensure_include(text: str) -> str:
    if "#include <nvToolsExt.h>" in text:
        return text
    return text.replace(
        '#include "NvUtils.h"\n#include "multivideo_transcode.h"\n',
        '#include "NvUtils.h"\n#include "multivideo_transcode.h"\n'
        "#include <nvToolsExt.h>\n",
        1,
    )


def ensure_helper(text: str) -> str:
    if "struct NvtxScopedRange" in text:
        return text
    candidate_markers = [
        "struct VpiMatrix3x3\n{",
        "static bool g_wrapper_probe_scratch_fd_ready = false;",
        "static void\nabort(context_t *ctx)\n{",
    ]
    helper = r'''
struct NvtxScopedRange
{
    explicit NvtxScopedRange(const char *name) : active(true)
    {
        nvtxRangePushA(name);
    }
    ~NvtxScopedRange()
    {
        if (active)
        {
            nvtxRangePop();
        }
    }
    bool active;
};

'''
    marker = next((item for item in candidate_markers if item in text), None)
    if marker is None:
        raise RuntimeError("no safe marker found for NVTX helper insertion")
    return replace_once(text, marker, helper + marker, "abort helper insertion")


def add_egl_ranges(text: str) -> str:
    # Inner VPI submit/sync ranges.
    text = text.replace(
        "        status = vpiSubmitPerspectiveWarp(stream, VPI_BACKEND_CUDA, input, xform, output, NULL,\n",
        "        {\n"
        "            NvtxScopedRange nvtx_submit(\"vpi_submit_perspective_warp\");\n"
        "            status = vpiSubmitPerspectiveWarp(stream, VPI_BACKEND_CUDA, input, xform, output, NULL,\n",
        1,
    )
    text = text.replace(
        "                                          VPI_INTERP_LINEAR, VPI_BORDER_ZERO, 0);\n"
        "        if (status != VPI_SUCCESS) goto vpi_fail;\n"
        "        status = vpiStreamSync(stream);\n",
        "                                          VPI_INTERP_LINEAR, VPI_BORDER_ZERO, 0);\n"
        "        }\n"
        "        if (status != VPI_SUCCESS) goto vpi_fail;\n"
        "        {\n"
        "            NvtxScopedRange nvtx_sync(\"vpi_stream_sync\");\n"
        "            status = vpiStreamSync(stream);\n"
        "        }\n",
        1,
    )

    # Outer stage ranges in the transcode loop.
    text = text.replace(
        "            auto egl_stage_t0 = std::chrono::high_resolution_clock::now();\n"
        "            ret = vpi_transform_fd(ctx->dmabuff_fd[v4l2_buf.index], g_vpi_input_scratch_fd[v4l2_buf.index], ctx->width, ctx->height);\n"
        "            auto egl_stage_t1 = std::chrono::high_resolution_clock::now();\n",
        "            NvtxScopedRange nvtx_wall(\"wall_frame_device_stage\");\n"
        "            auto egl_stage_t0 = std::chrono::high_resolution_clock::now();\n"
        "            {\n"
        "                NvtxScopedRange nvtx_input_xform(\"input_transform_main_to_scratch\");\n"
        "                ret = vpi_transform_fd(ctx->dmabuff_fd[v4l2_buf.index], g_vpi_input_scratch_fd[v4l2_buf.index], ctx->width, ctx->height);\n"
        "            }\n"
        "            auto egl_stage_t1 = std::chrono::high_resolution_clock::now();\n",
        1,
    )
    text = text.replace(
        "            auto egl_stage_t2 = std::chrono::high_resolution_clock::now();\n"
        "            ret = vpi_warp_egl_images(input_scratch_surf->surfaceList[0].mappedAddr.eglImage,\n"
        "                                      output_scratch_surf->surfaceList[0].mappedAddr.eglImage);\n"
        "            auto egl_stage_t3 = std::chrono::high_resolution_clock::now();\n",
        "            auto egl_stage_t2 = std::chrono::high_resolution_clock::now();\n"
        "            {\n"
        "                NvtxScopedRange nvtx_wrap_warp(\"eglimage_wrap_submit_sync\");\n"
        "                ret = vpi_warp_egl_images(input_scratch_surf->surfaceList[0].mappedAddr.eglImage,\n"
        "                                          output_scratch_surf->surfaceList[0].mappedAddr.eglImage);\n"
        "            }\n"
        "            auto egl_stage_t3 = std::chrono::high_resolution_clock::now();\n",
        1,
    )
    text = text.replace(
        "            ret = vpi_transform_fd(g_vpi_output_scratch_fd[v4l2_buf.index], ctx->dmabuff_fd[v4l2_buf.index], ctx->width, ctx->height);\n"
        "            auto egl_stage_t5 = std::chrono::high_resolution_clock::now();\n",
        "            {\n"
        "                NvtxScopedRange nvtx_output_xform(\"output_transform_scratch_to_main\");\n"
        "                ret = vpi_transform_fd(g_vpi_output_scratch_fd[v4l2_buf.index], ctx->dmabuff_fd[v4l2_buf.index], ctx->width, ctx->height);\n"
        "            }\n"
        "            auto egl_stage_t5 = std::chrono::high_resolution_clock::now();\n",
        1,
    )
    return text


def add_nvbuffer_ranges(text: str) -> str:
    text = text.replace(
        "        status = vpiSubmitPerspectiveWarp(stream, VPI_BACKEND_CUDA, input, xform, output, NULL,\n",
        "        {\n"
        "            NvtxScopedRange nvtx_submit(\"vpi_submit_perspective_warp\");\n"
        "            status = vpiSubmitPerspectiveWarp(stream, VPI_BACKEND_CUDA, input, xform, output, NULL,\n",
        1,
    )
    text = text.replace(
        "                                          VPI_INTERP_LINEAR, VPI_BORDER_ZERO, 0);\n"
        "        if (status != VPI_SUCCESS) goto vpi_fail;\n"
        "        status = vpiStreamSync(stream);\n",
        "                                          VPI_INTERP_LINEAR, VPI_BORDER_ZERO, 0);\n"
        "        }\n"
        "        if (status != VPI_SUCCESS) goto vpi_fail;\n"
        "        {\n"
        "            NvtxScopedRange nvtx_sync(\"vpi_stream_sync\");\n"
        "            status = vpiStreamSync(stream);\n"
        "        }\n",
        1,
    )
    text = text.replace(
        "            auto nvbuf_pair_stage_t0 = std::chrono::high_resolution_clock::now();\n"
        "            ret = nvbuf_pair_transform_fd(ctx->dmabuff_fd[v4l2_buf.index], g_nvbuf_pair_input_scratch_fd[v4l2_buf.index], ctx->width, ctx->height);\n"
        "            auto nvbuf_pair_stage_t1 = std::chrono::high_resolution_clock::now();\n",
        "            NvtxScopedRange nvtx_wall(\"wall_frame_device_stage\");\n"
        "            auto nvbuf_pair_stage_t0 = std::chrono::high_resolution_clock::now();\n"
        "            {\n"
        "                NvtxScopedRange nvtx_input_xform(\"input_transform_main_to_scratch\");\n"
        "                ret = nvbuf_pair_transform_fd(ctx->dmabuff_fd[v4l2_buf.index], g_nvbuf_pair_input_scratch_fd[v4l2_buf.index], ctx->width, ctx->height);\n"
        "            }\n"
        "            auto nvbuf_pair_stage_t1 = std::chrono::high_resolution_clock::now();\n",
        1,
    )
    text = text.replace(
        "            ret = vpi_warp_nvbuffer_pair(g_nvbuf_pair_input_scratch_fd[v4l2_buf.index],\n"
        "                                         g_nvbuf_pair_output_scratch_fd[v4l2_buf.index]);\n"
        "            auto nvbuf_pair_stage_t2 = std::chrono::high_resolution_clock::now();\n",
        "            {\n"
        "                NvtxScopedRange nvtx_wrap_warp(\"nvbuffer_wrap_submit_sync\");\n"
        "                ret = vpi_warp_nvbuffer_pair(g_nvbuf_pair_input_scratch_fd[v4l2_buf.index],\n"
        "                                             g_nvbuf_pair_output_scratch_fd[v4l2_buf.index]);\n"
        "            }\n"
        "            auto nvbuf_pair_stage_t2 = std::chrono::high_resolution_clock::now();\n",
        1,
    )
    text = text.replace(
        "            ret = nvbuf_pair_transform_fd(g_nvbuf_pair_output_scratch_fd[v4l2_buf.index], ctx->dmabuff_fd[v4l2_buf.index], ctx->width, ctx->height);\n"
        "            auto nvbuf_pair_stage_t3 = std::chrono::high_resolution_clock::now();\n",
        "            {\n"
        "                NvtxScopedRange nvtx_output_xform(\"output_transform_scratch_to_main\");\n"
        "                ret = nvbuf_pair_transform_fd(g_nvbuf_pair_output_scratch_fd[v4l2_buf.index], ctx->dmabuff_fd[v4l2_buf.index], ctx->width, ctx->height);\n"
        "            }\n"
        "            auto nvbuf_pair_stage_t3 = std::chrono::high_resolution_clock::now();\n",
        1,
    )
    return text


def patch_makefile(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "-lnvToolsExt" not in text:
        text = text.replace(
            "LDFLAGS +=",
            "LDFLAGS += -lnvToolsExt ",
            1,
        )
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Add minimal NVTX ranges to patched MMAPI VPI transcode samples.")
    parser.add_argument("--sample-dir", type=Path, required=True)
    parser.add_argument("--mode", choices=["eglimage", "nvbuffer_pair"], required=True)
    args = parser.parse_args()
    cpp = args.sample_dir / "multivideo_transcode_main.cpp"
    text = cpp.read_text(encoding="utf-8")
    text = ensure_include(text)
    text = ensure_helper(text)
    if args.mode == "eglimage":
        text = add_egl_ranges(text)
    else:
        text = add_nvbuffer_ranges(text)
    cpp.write_text(text, encoding="utf-8")
    patch_makefile(args.sample_dir / "Makefile")
    print(f"patched NVTX ranges: {args.sample_dir} mode={args.mode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
