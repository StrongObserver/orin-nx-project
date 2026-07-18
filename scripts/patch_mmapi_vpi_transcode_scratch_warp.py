from __future__ import annotations

import argparse
from pathlib import Path

from patch_mmapi_vpi_encode_warp import VPI_INSERT


HELPERS = r'''
static int g_vpi_scratch_fd[MAX_BUFFERS];
static bool g_vpi_scratch_fd_ready = false;

static void
init_vpi_scratch_fd_array()
{
    if (!g_vpi_scratch_fd_ready)
    {
        for (int i = 0; i < MAX_BUFFERS; ++i)
        {
            g_vpi_scratch_fd[i] = -1;
        }
        g_vpi_scratch_fd_ready = true;
    }
}

static int
vpi_transform_fd(int src_fd, int dst_fd, uint32_t width, uint32_t height)
{
    NvBufSurf::NvCommonTransformParams transform_params;
    memset(&transform_params, 0, sizeof(transform_params));
    transform_params.src_top = 0;
    transform_params.src_left = 0;
    transform_params.src_width = width;
    transform_params.src_height = height;
    transform_params.dst_top = 0;
    transform_params.dst_left = 0;
    transform_params.dst_width = width;
    transform_params.dst_height = height;
    transform_params.flag = NVBUFSURF_TRANSFORM_FILTER;
    transform_params.flip = NvBufSurfTransform_None;
    transform_params.filter = NvBufSurfTransformInter_Nearest;
    return NvBufSurf::NvTransform(&transform_params, src_fd, dst_fd);
}
'''


def patch_main(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "VPI_TRANSCODE_WARP" not in text:
        text = text.replace(
            '#include "NvUtils.h"\n#include "multivideo_transcode.h"\n',
            '#include "NvUtils.h"\n#include "multivideo_transcode.h"\n'
            "#include <chrono>\n"
            "#include <cstdlib>\n"
            "#include <cuda.h>\n"
            "#include <cuda_runtime.h>\n"
            "#include <fstream>\n"
            "#include <sstream>\n"
            "#include <string>\n"
            "#include <vector>\n"
            '#include "cudaEGL.h"\n'
            "#include <vpi/Image.h>\n"
            "#include <vpi/Status.h>\n"
            "#include <vpi/Stream.h>\n"
            "#include <vpi/algo/PerspectiveWarp.h>\n",
        )
        marker = "static void\nabort(context_t *ctx)\n{"
        if marker not in text:
            raise RuntimeError(f"abort marker not found in {path}")
        insert = HELPERS + "\n" + VPI_INSERT.replace("VPI_ENC_WARP", "VPI_TRANSCODE_WARP")
        text = text.replace(marker, insert + "\n" + marker, 1)

    query_marker = "    NvBufSurf::NvCommonAllocateParams cParams = {0};\n"
    if "init_vpi_scratch_fd_array();" not in text:
        text = text.replace(query_marker, query_marker + "\n    init_vpi_scratch_fd_array();\n", 1)

    alloc_marker = """            ret = NvBufSurf::NvAllocate(&cParams, 1, &ctx->dmabuff_fd[index]);
            TEST_ERROR(ret < 0, "Failed to create buffers", error);
"""
    alloc_insert = alloc_marker + """            NvBufSurf::NvCommonAllocateParams scratchParams = cParams;
            scratchParams.layout = NVBUF_LAYOUT_PITCH;
            scratchParams.colorFormat = NVBUF_COLOR_FORMAT_NV12_ER;
            if (g_vpi_scratch_fd[index] != -1)
            {
                NvBufSurf::NvDestroy(g_vpi_scratch_fd[index]);
                g_vpi_scratch_fd[index] = -1;
            }
            ret = NvBufSurf::NvAllocate(&scratchParams, 1, &g_vpi_scratch_fd[index]);
            TEST_ERROR(ret < 0, "Failed to create VPI scratch buffers", error);
"""
    if "scratchParams.layout = NVBUF_LAYOUT_PITCH;" not in text:
        if alloc_marker not in text:
            raise RuntimeError("dmabuf allocation marker not found")
        text = text.replace(alloc_marker, alloc_insert, 1)

    insert_marker = """            ret = NvBufSurfaceFromFd(ctx->dmabuff_fd[v4l2_buf.index], (void**)(&nvbuf_surf));
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while calling NvBufSurfaceFromFd" << endl;
                break;
            }

            if (ctx->enc_output_memory_type == V4L2_MEMORY_DMABUF)
"""
    insert_replacement = """            ret = NvBufSurfaceFromFd(ctx->dmabuff_fd[v4l2_buf.index], (void**)(&nvbuf_surf));
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while calling NvBufSurfaceFromFd" << endl;
                break;
            }

            if (g_vpi_scratch_fd[v4l2_buf.index] < 0)
            {
                abort(ctx);
                cerr << "VPI scratch buffer is not allocated" << endl;
                break;
            }
            ret = vpi_transform_fd(ctx->dmabuff_fd[v4l2_buf.index], g_vpi_scratch_fd[v4l2_buf.index], ctx->width, ctx->height);
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while transforming transcode DMABUF to VPI scratch" << endl;
                break;
            }
            NvBufSurface *scratch_surf = 0;
            ret = NvBufSurfaceFromFd(g_vpi_scratch_fd[v4l2_buf.index], (void**)(&scratch_surf));
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while calling NvBufSurfaceFromFd for VPI scratch" << endl;
                break;
            }
            if (scratch_surf->surfaceList[0].mappedAddr.eglImage == NULL)
            {
                if (NvBufSurfaceMapEglImage(scratch_surf, 0) != 0)
                {
                    abort(ctx);
                    cerr << "Unable to map VPI scratch fd to EGLImage" << endl;
                    break;
                }
            }
            ret = vpi_warp_egl_image(scratch_surf->surfaceList[0].mappedAddr.eglImage);
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while VPI warp on transcode scratch" << endl;
                break;
            }
            if (NvBufSurfaceUnMapEglImage(scratch_surf, 0) != 0)
            {
                abort(ctx);
                cerr << "Unable to unmap VPI scratch EGLImage" << endl;
                break;
            }
            ret = vpi_transform_fd(g_vpi_scratch_fd[v4l2_buf.index], ctx->dmabuff_fd[v4l2_buf.index], ctx->width, ctx->height);
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while transforming VPI scratch back to transcode DMABUF" << endl;
                break;
            }

            if (ctx->enc_output_memory_type == V4L2_MEMORY_DMABUF)
"""
    if "VPI scratch buffer is not allocated" not in text:
        if insert_marker not in text:
            raise RuntimeError("NvBufSurfaceFromFd insertion block not found")
        text = text.replace(insert_marker, insert_replacement, 1)

    path.write_text(text, encoding="utf-8")


def patch_makefile(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "/opt/nvidia/vpi2/include" not in text:
        text = text.replace(
            "include ../Rules.mk\n",
            "include ../Rules.mk\n\nCPPFLAGS += -I/opt/nvidia/vpi2/include\nLDFLAGS += -L/opt/nvidia/vpi2/lib/aarch64-linux-gnu -lnvvpi\n",
        )
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Patch MMAPI transcode sample to use a pitch-linear VPI scratch buffer and preserve the block-linear encoder path.")
    parser.add_argument("--sample-dir", type=Path, required=True)
    args = parser.parse_args()
    patch_main(args.sample_dir / "multivideo_transcode_main.cpp")
    patch_makefile(args.sample_dir / "Makefile")
    print(f"patched scratch transcode: {args.sample_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
