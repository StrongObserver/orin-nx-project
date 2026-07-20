from __future__ import annotations

import argparse
from pathlib import Path


HELPERS = r'''
static int g_wrapper_probe_input_scratch_fd[MAX_BUFFERS];
static int g_wrapper_probe_output_scratch_fd[MAX_BUFFERS];
static bool g_wrapper_probe_scratch_fd_ready = false;

static void
init_wrapper_probe_scratch_fd_array()
{
    if (!g_wrapper_probe_scratch_fd_ready)
    {
        for (int i = 0; i < MAX_BUFFERS; ++i)
        {
            g_wrapper_probe_input_scratch_fd[i] = -1;
            g_wrapper_probe_output_scratch_fd[i] = -1;
        }
        g_wrapper_probe_scratch_fd_ready = true;
    }
}

static int
wrapper_probe_transform_fd(int src_fd, int dst_fd, uint32_t width, uint32_t height)
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
    if "VPI_WRAPPER_CREATE_PROBE_STAGE" in text:
        print(f"already wrapper-create probe patched: {path}")
        return

    text = text.replace(
        '#include "NvUtils.h"\n#include "multivideo_transcode.h"\n',
        '#include "NvUtils.h"\n#include "multivideo_transcode.h"\n'
        "#include <chrono>\n"
        "#include <vpi/Image.h>\n"
        "#include <vpi/Status.h>\n",
    )
    marker = "static void\nabort(context_t *ctx)\n{"
    if marker not in text:
        raise RuntimeError(f"abort marker not found in {path}")
    text = text.replace(marker, HELPERS + "\n" + marker, 1)

    query_marker = "    NvBufSurf::NvCommonAllocateParams cParams = {0};\n"
    if "init_wrapper_probe_scratch_fd_array();" not in text:
        text = text.replace(query_marker, query_marker + "\n    init_wrapper_probe_scratch_fd_array();\n", 1)

    alloc_marker = """            ret = NvBufSurf::NvAllocate(&cParams, 1, &ctx->dmabuff_fd[index]);
            TEST_ERROR(ret < 0, "Failed to create buffers", error);
"""
    alloc_insert = alloc_marker + """            NvBufSurf::NvCommonAllocateParams scratchParams = cParams;
            scratchParams.layout = NVBUF_LAYOUT_PITCH;
            scratchParams.colorFormat = NVBUF_COLOR_FORMAT_NV12_ER;
            if (g_wrapper_probe_input_scratch_fd[index] != -1)
            {
                NvBufSurf::NvDestroy(g_wrapper_probe_input_scratch_fd[index]);
                g_wrapper_probe_input_scratch_fd[index] = -1;
            }
            if (g_wrapper_probe_output_scratch_fd[index] != -1)
            {
                NvBufSurf::NvDestroy(g_wrapper_probe_output_scratch_fd[index]);
                g_wrapper_probe_output_scratch_fd[index] = -1;
            }
            ret = NvBufSurf::NvAllocate(&scratchParams, 1, &g_wrapper_probe_input_scratch_fd[index]);
            TEST_ERROR(ret < 0, "Failed to create wrapper probe input scratch buffers", error);
            ret = NvBufSurf::NvAllocate(&scratchParams, 1, &g_wrapper_probe_output_scratch_fd[index]);
            TEST_ERROR(ret < 0, "Failed to create wrapper probe output scratch buffers", error);
"""
    if "g_wrapper_probe_input_scratch_fd[index]" not in text:
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

            if (g_wrapper_probe_input_scratch_fd[v4l2_buf.index] < 0 || g_wrapper_probe_output_scratch_fd[v4l2_buf.index] < 0)
            {
                abort(ctx);
                cerr << "Wrapper probe scratch buffers are not allocated" << endl;
                break;
            }
            auto probe_t0 = std::chrono::high_resolution_clock::now();
            ret = wrapper_probe_transform_fd(ctx->dmabuff_fd[v4l2_buf.index], g_wrapper_probe_input_scratch_fd[v4l2_buf.index], ctx->width, ctx->height);
            auto probe_t1 = std::chrono::high_resolution_clock::now();
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while wrapper-probing input transform" << endl;
                break;
            }
            NvBufSurface *input_scratch_surf = 0;
            ret = NvBufSurfaceFromFd(g_wrapper_probe_input_scratch_fd[v4l2_buf.index], (void**)(&input_scratch_surf));
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while calling NvBufSurfaceFromFd for wrapper input scratch" << endl;
                break;
            }
            NvBufSurface *output_scratch_surf = 0;
            ret = NvBufSurfaceFromFd(g_wrapper_probe_output_scratch_fd[v4l2_buf.index], (void**)(&output_scratch_surf));
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while calling NvBufSurfaceFromFd for wrapper output scratch" << endl;
                break;
            }
            auto probe_t2 = std::chrono::high_resolution_clock::now();
            if (NvBufSurfaceMapEglImage(input_scratch_surf, 0) != 0)
            {
                abort(ctx);
                cerr << "Unable to map input scratch EGLImage in wrapper probe" << endl;
                break;
            }
            if (NvBufSurfaceMapEglImage(output_scratch_surf, 0) != 0)
            {
                abort(ctx);
                cerr << "Unable to map output scratch EGLImage in wrapper probe" << endl;
                break;
            }
            auto probe_t3 = std::chrono::high_resolution_clock::now();

            VPIImageData input_data;
            memset(&input_data, 0, sizeof(input_data));
            input_data.bufferType = VPI_IMAGE_BUFFER_EGLIMAGE;
            input_data.buffer.egl = input_scratch_surf->surfaceList[0].mappedAddr.eglImage;
            VPIImageData output_data;
            memset(&output_data, 0, sizeof(output_data));
            output_data.bufferType = VPI_IMAGE_BUFFER_EGLIMAGE;
            output_data.buffer.egl = output_scratch_surf->surfaceList[0].mappedAddr.eglImage;
            VPIImage input = NULL;
            VPIImage output = NULL;
            VPIStatus status = vpiImageCreateWrapper(&input_data, NULL, VPI_BACKEND_CUDA, &input);
            if (status != VPI_SUCCESS)
            {
                abort(ctx);
                cerr << "vpiImageCreateWrapper input failed status=" << status << endl;
                break;
            }
            status = vpiImageCreateWrapper(&output_data, NULL, VPI_BACKEND_CUDA, &output);
            if (status != VPI_SUCCESS)
            {
                abort(ctx);
                cerr << "vpiImageCreateWrapper output failed status=" << status << endl;
                break;
            }
            auto probe_t4 = std::chrono::high_resolution_clock::now();
            vpiImageDestroy(output);
            vpiImageDestroy(input);
            auto probe_t5 = std::chrono::high_resolution_clock::now();

            if (NvBufSurfaceUnMapEglImage(input_scratch_surf, 0) != 0)
            {
                abort(ctx);
                cerr << "Unable to unmap input scratch EGLImage in wrapper probe" << endl;
                break;
            }
            if (NvBufSurfaceUnMapEglImage(output_scratch_surf, 0) != 0)
            {
                abort(ctx);
                cerr << "Unable to unmap output scratch EGLImage in wrapper probe" << endl;
                break;
            }
            auto probe_t6 = std::chrono::high_resolution_clock::now();
            ret = wrapper_probe_transform_fd(g_wrapper_probe_input_scratch_fd[v4l2_buf.index], g_wrapper_probe_output_scratch_fd[v4l2_buf.index], ctx->width, ctx->height);
            auto probe_t7 = std::chrono::high_resolution_clock::now();
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while wrapper-probing scratch copy" << endl;
                break;
            }
            ret = wrapper_probe_transform_fd(g_wrapper_probe_output_scratch_fd[v4l2_buf.index], ctx->dmabuff_fd[v4l2_buf.index], ctx->width, ctx->height);
            auto probe_t8 = std::chrono::high_resolution_clock::now();
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while wrapper-probing output transform" << endl;
                break;
            }

            static int wrapper_probe_frame = 0;
            static double wrapper_probe_total_ms = 0.0;
            wrapper_probe_frame++;
            double input_transform_ms = std::chrono::duration<double, std::milli>(probe_t1 - probe_t0).count();
            double fromfd_ms = std::chrono::duration<double, std::milli>(probe_t2 - probe_t1).count();
            double map_ms = std::chrono::duration<double, std::milli>(probe_t3 - probe_t2).count();
            double wrapper_create_ms = std::chrono::duration<double, std::milli>(probe_t4 - probe_t3).count();
            double wrapper_destroy_ms = std::chrono::duration<double, std::milli>(probe_t5 - probe_t4).count();
            double unmap_ms = std::chrono::duration<double, std::milli>(probe_t6 - probe_t5).count();
            double scratch_copy_ms = std::chrono::duration<double, std::milli>(probe_t7 - probe_t6).count();
            double output_transform_ms = std::chrono::duration<double, std::milli>(probe_t8 - probe_t7).count();
            double total_ms = std::chrono::duration<double, std::milli>(probe_t8 - probe_t0).count();
            wrapper_probe_total_ms += total_ms;
            if (wrapper_probe_frame <= 5 || wrapper_probe_frame % 100 == 0)
            {
                cerr << "VPI_WRAPPER_CREATE_PROBE_STAGE frame=" << wrapper_probe_frame
                     << " input_transform_ms=" << input_transform_ms
                     << " fromfd_ms=" << fromfd_ms
                     << " map_ms=" << map_ms
                     << " wrapper_create_ms=" << wrapper_create_ms
                     << " wrapper_destroy_ms=" << wrapper_destroy_ms
                     << " unmap_ms=" << unmap_ms
                     << " scratch_copy_ms=" << scratch_copy_ms
                     << " output_transform_ms=" << output_transform_ms
                     << " total_ms=" << total_ms
                     << " avg_total_ms=" << (wrapper_probe_total_ms / wrapper_probe_frame)
                     << endl;
            }

            if (ctx->enc_output_memory_type == V4L2_MEMORY_DMABUF)
"""
    if "VPI_WRAPPER_CREATE_PROBE_STAGE frame=" not in text:
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
    parser = argparse.ArgumentParser(description="Patch MMAPI transcode sample to measure VPI EGLImage wrapper create/destroy cost.")
    parser.add_argument("--sample-dir", type=Path, required=True)
    args = parser.parse_args()
    patch_main(args.sample_dir / "multivideo_transcode_main.cpp")
    patch_makefile(args.sample_dir / "Makefile")
    print(f"patched VPI wrapper-create probe: {args.sample_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
