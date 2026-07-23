from __future__ import annotations

import argparse
from pathlib import Path


HELPERS = r'''
static int g_cuda_interop_input_scratch_fd[MAX_BUFFERS];
static int g_cuda_interop_output_scratch_fd[MAX_BUFFERS];
static bool g_cuda_interop_scratch_fd_ready = false;
static std::string g_cuda_interop_mode = "identity";

static void
init_cuda_interop_scratch_fd_array()
{
    if (!g_cuda_interop_scratch_fd_ready)
    {
        for (int i = 0; i < MAX_BUFFERS; ++i)
        {
            g_cuda_interop_input_scratch_fd[i] = -1;
            g_cuda_interop_output_scratch_fd[i] = -1;
        }
        g_cuda_interop_scratch_fd_ready = true;
    }
}

static int
cuda_interop_transform_fd(int src_fd, int dst_fd, uint32_t width, uint32_t height)
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

static int
cuda_check(CUresult err, const char *what)
{
    if (err != CUDA_SUCCESS)
    {
        const char *name = NULL;
        const char *message = NULL;
        cuGetErrorName(err, &name);
        cuGetErrorString(err, &message);
        cerr << "CUDA_INTEROP_ERROR what=" << what
             << " err=" << (name ? name : "unknown")
             << " msg=" << (message ? message : "unknown") << endl;
        return -1;
    }
    return 0;
}

static int
init_cuda_driver_once()
{
    static bool ready = false;
    static CUcontext primary_ctx = NULL;
    if (ready)
    {
        return 0;
    }
    if (cuda_check(cuInit(0), "cuInit") != 0)
    {
        return -1;
    }
    CUdevice device;
    if (cuda_check(cuDeviceGet(&device, 0), "cuDeviceGet") != 0)
    {
        return -1;
    }
    if (cuda_check(cuDevicePrimaryCtxRetain(&primary_ctx, device), "cuDevicePrimaryCtxRetain") != 0)
    {
        return -1;
    }
    if (cuda_check(cuCtxSetCurrent(primary_ctx), "cuCtxSetCurrent") != 0)
    {
        return -1;
    }
    ready = true;
    return 0;
}

static int
cuda_copy_plane_2d(CUdeviceptr dst, size_t dst_pitch, CUdeviceptr src, size_t src_pitch,
                   size_t width_bytes, size_t height_rows)
{
    if (width_bytes == 0 || height_rows == 0)
    {
        return 0;
    }
    CUDA_MEMCPY2D copy;
    memset(&copy, 0, sizeof(copy));
    copy.srcMemoryType = CU_MEMORYTYPE_DEVICE;
    copy.srcDevice = src;
    copy.srcPitch = src_pitch;
    copy.dstMemoryType = CU_MEMORYTYPE_DEVICE;
    copy.dstDevice = dst;
    copy.dstPitch = dst_pitch;
    copy.WidthInBytes = width_bytes;
    copy.Height = height_rows;
    return cuda_check(cuMemcpy2D(&copy), "cuMemcpy2D");
}

static int
cuda_copy_nv12_with_optional_marker(CUeglFrame &input_frame, CUeglFrame &output_frame,
                                    uint32_t width, uint32_t height,
                                    bool draw_marker, int marker_x, int marker_y)
{
    if (input_frame.frameType != CU_EGL_FRAME_TYPE_PITCH ||
        output_frame.frameType != CU_EGL_FRAME_TYPE_PITCH)
    {
        cerr << "CUDA_INTEROP_ERROR unsupported_frame_type input=" << input_frame.frameType
             << " output=" << output_frame.frameType << endl;
        return -1;
    }
    if (input_frame.planeCount < 2 || output_frame.planeCount < 2)
    {
        cerr << "CUDA_INTEROP_ERROR unsupported_plane_count input=" << input_frame.planeCount
             << " output=" << output_frame.planeCount << endl;
        return -1;
    }

    CUdeviceptr in_y = (CUdeviceptr)(uintptr_t)input_frame.frame.pPitch[0];
    CUdeviceptr in_uv = (CUdeviceptr)(uintptr_t)input_frame.frame.pPitch[1];
    CUdeviceptr out_y = (CUdeviceptr)(uintptr_t)output_frame.frame.pPitch[0];
    CUdeviceptr out_uv = (CUdeviceptr)(uintptr_t)output_frame.frame.pPitch[1];
    size_t in_pitch = input_frame.pitch;
    size_t out_pitch = output_frame.pitch;

    if (cuda_copy_plane_2d(out_y, out_pitch, in_y, in_pitch, width, height) != 0)
    {
        return -1;
    }
    if (cuda_copy_plane_2d(out_uv, out_pitch, in_uv, in_pitch, width, height / 2) != 0)
    {
        return -1;
    }

    if (draw_marker)
    {
        int x0 = std::max(0, std::min(marker_x, (int)width - 1));
        int y0 = std::max(0, std::min(marker_y, (int)height - 1));
        int marker_w = std::min(64, (int)width - x0);
        int marker_h = std::min(36, (int)height - y0);
        marker_w = marker_w & ~1;
        marker_h = marker_h & ~1;
        if (marker_w > 0 && marker_h > 0)
        {
            if (cuda_check(cuMemsetD2D8(out_y + y0 * out_pitch + x0,
                                        out_pitch, 235, marker_w, marker_h),
                           "cuMemsetD2D8_marker_y") != 0)
            {
                return -1;
            }
            int uv_y = y0 / 2;
            if (cuda_check(cuMemsetD2D8(out_uv + uv_y * out_pitch + x0,
                                        out_pitch, 128, marker_w, marker_h / 2),
                           "cuMemsetD2D8_marker_uv") != 0)
            {
                return -1;
            }
        }
    }

    return cuda_check(cuCtxSynchronize(), "cuCtxSynchronize");
}

static int
cuda_process_egl_images(EGLImageKHR input_egl, EGLImageKHR output_egl,
                        uint32_t width, uint32_t height)
{
    static int frame_count = 0;
    int current_frame = frame_count + 1;
    const char *mode_env = getenv("CUDA_INTEROP_MODE");
    if (mode_env != NULL && mode_env[0] != '\0')
    {
        g_cuda_interop_mode = mode_env;
    }

    int marker_x = 0;
    int marker_y = 0;
    bool draw_marker = false;
    if (g_cuda_interop_mode == "identity")
    {
        marker_x = 0;
        marker_y = 0;
        draw_marker = false;
    }
    else if (g_cuda_interop_mode == "marker")
    {
        const char *x_env = getenv("CUDA_INTEROP_MARKER_X");
        const char *y_env = getenv("CUDA_INTEROP_MARKER_Y");
        marker_x = x_env ? atoi(x_env) : 16;
        marker_y = y_env ? atoi(y_env) : 16;
        draw_marker = true;
    }
    else if (g_cuda_interop_mode == "dynamic_marker")
    {
        marker_x = 16 + (int)lrintf((sinf(current_frame * 0.05f) + 1.0f) * 24.0f);
        marker_y = 16 + (int)lrintf((cosf(current_frame * 0.04f) + 1.0f) * 12.0f);
        draw_marker = true;
    }
    else if (g_cuda_interop_mode == "shift" || g_cuda_interop_mode == "dynamic_shift")
    {
        cerr << "CUDA_INTEROP_ERROR mode_rejected=" << g_cuda_interop_mode
             << " reason=large-plane-shift-caused-visible-tearing; use marker or dynamic_marker" << endl;
        return -1;
    }
    else
    {
        cerr << "CUDA_INTEROP_ERROR unsupported_mode=" << g_cuda_interop_mode << endl;
        return -1;
    }

    if (init_cuda_driver_once() != 0)
    {
        return -1;
    }

    CUgraphicsResource input_resource = NULL;
    CUgraphicsResource output_resource = NULL;
    CUeglFrame input_frame;
    CUeglFrame output_frame;
    memset(&input_frame, 0, sizeof(input_frame));
    memset(&output_frame, 0, sizeof(output_frame));

    auto register_t0 = std::chrono::high_resolution_clock::now();
    if (cuda_check(cuGraphicsEGLRegisterImage(&input_resource, input_egl,
                                              CU_GRAPHICS_MAP_RESOURCE_FLAGS_READ_ONLY),
                   "cuGraphicsEGLRegisterImage_input") != 0)
    {
        return -1;
    }
    if (cuda_check(cuGraphicsEGLRegisterImage(&output_resource, output_egl,
                                              CU_GRAPHICS_MAP_RESOURCE_FLAGS_WRITE_DISCARD),
                   "cuGraphicsEGLRegisterImage_output") != 0)
    {
        cuGraphicsUnregisterResource(input_resource);
        return -1;
    }
    auto register_t1 = std::chrono::high_resolution_clock::now();

    if (cuda_check(cuGraphicsResourceGetMappedEglFrame(&input_frame, input_resource, 0, 0),
                   "cuGraphicsResourceGetMappedEglFrame_input") != 0)
    {
        cuGraphicsUnregisterResource(output_resource);
        cuGraphicsUnregisterResource(input_resource);
        return -1;
    }
    if (cuda_check(cuGraphicsResourceGetMappedEglFrame(&output_frame, output_resource, 0, 0),
                   "cuGraphicsResourceGetMappedEglFrame_output") != 0)
    {
        cuGraphicsUnregisterResource(output_resource);
        cuGraphicsUnregisterResource(input_resource);
        return -1;
    }
    auto mapped_t1 = std::chrono::high_resolution_clock::now();

    int rc = cuda_copy_nv12_with_optional_marker(input_frame, output_frame, width, height,
                                                 draw_marker, marker_x, marker_y);
    auto process_t1 = std::chrono::high_resolution_clock::now();

    CUresult unregister_output = cuGraphicsUnregisterResource(output_resource);
    CUresult unregister_input = cuGraphicsUnregisterResource(input_resource);
    auto unregister_t1 = std::chrono::high_resolution_clock::now();
    if (rc != 0)
    {
        return -1;
    }
    if (cuda_check(unregister_output, "cudaGraphicsUnregisterResource_output") != 0 ||
        cuda_check(unregister_input, "cudaGraphicsUnregisterResource_input") != 0)
    {
        return -1;
    }

    frame_count++;
    static double total_ms = 0.0;
    double register_ms = std::chrono::duration<double, std::milli>(register_t1 - register_t0).count();
    double map_ms = std::chrono::duration<double, std::milli>(mapped_t1 - register_t1).count();
    double process_ms = std::chrono::duration<double, std::milli>(process_t1 - mapped_t1).count();
    double unregister_ms = std::chrono::duration<double, std::milli>(unregister_t1 - process_t1).count();
    double elapsed_ms = std::chrono::duration<double, std::milli>(unregister_t1 - register_t0).count();
    total_ms += elapsed_ms;
    if (frame_count <= 5 || frame_count % 100 == 0)
    {
        cerr << "CUDA_INTEROP_FRAME frame=" << frame_count
             << " mode=" << g_cuda_interop_mode
             << " marker_x=" << marker_x
             << " marker_y=" << marker_y
             << " marker=" << (draw_marker ? 1 : 0)
             << " width=" << width
             << " height=" << height
             << " input_pitch=" << input_frame.pitch
             << " output_pitch=" << output_frame.pitch
             << " input_planes=" << input_frame.planeCount
             << " output_planes=" << output_frame.planeCount
             << " register_ms=" << register_ms
             << " map_ms=" << map_ms
             << " process_ms=" << process_ms
             << " unregister_ms=" << unregister_ms
             << " elapsed_ms=" << elapsed_ms
             << " avg_ms=" << (total_ms / frame_count)
             << endl;
    }
    return 0;
}
'''


def patch_main(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "CUDA_INTEROP_FRAME" in text:
        print(f"already CUDA interop patched: {path}")
        return

    text = text.replace(
        '#include "NvUtils.h"\n#include "multivideo_transcode.h"\n',
        '#include "NvUtils.h"\n#include "multivideo_transcode.h"\n'
        "#include <algorithm>\n"
        "#include <chrono>\n"
        "#include <cmath>\n"
        "#include <cstdlib>\n"
        "#include <string>\n"
        "#include <cuda.h>\n"
        "#include <cudaEGL.h>\n",
        1,
    )
    marker = "static void\nabort(context_t *ctx)\n{"
    if marker not in text:
        raise RuntimeError(f"abort marker not found in {path}")
    text = text.replace(marker, HELPERS + "\n" + marker, 1)

    query_marker = "    NvBufSurf::NvCommonAllocateParams cParams = {0};\n"
    if "init_cuda_interop_scratch_fd_array();" not in text:
        text = text.replace(query_marker, query_marker + "\n    init_cuda_interop_scratch_fd_array();\n", 1)

    alloc_marker = """            ret = NvBufSurf::NvAllocate(&cParams, 1, &ctx->dmabuff_fd[index]);
            TEST_ERROR(ret < 0, "Failed to create buffers", error);
"""
    alloc_insert = alloc_marker + """            NvBufSurf::NvCommonAllocateParams scratchParams = cParams;
            scratchParams.layout = NVBUF_LAYOUT_PITCH;
            scratchParams.colorFormat = NVBUF_COLOR_FORMAT_NV12_ER;
            if (g_cuda_interop_input_scratch_fd[index] != -1)
            {
                NvBufSurf::NvDestroy(g_cuda_interop_input_scratch_fd[index]);
                g_cuda_interop_input_scratch_fd[index] = -1;
            }
            if (g_cuda_interop_output_scratch_fd[index] != -1)
            {
                NvBufSurf::NvDestroy(g_cuda_interop_output_scratch_fd[index]);
                g_cuda_interop_output_scratch_fd[index] = -1;
            }
            ret = NvBufSurf::NvAllocate(&scratchParams, 1, &g_cuda_interop_input_scratch_fd[index]);
            TEST_ERROR(ret < 0, "Failed to create CUDA interop input scratch buffers", error);
            ret = NvBufSurf::NvAllocate(&scratchParams, 1, &g_cuda_interop_output_scratch_fd[index]);
            TEST_ERROR(ret < 0, "Failed to create CUDA interop output scratch buffers", error);
"""
    if "g_cuda_interop_input_scratch_fd[index]" not in text:
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

            if (g_cuda_interop_input_scratch_fd[v4l2_buf.index] < 0 || g_cuda_interop_output_scratch_fd[v4l2_buf.index] < 0)
            {
                abort(ctx);
                cerr << "CUDA interop scratch buffers are not allocated" << endl;
                break;
            }
            auto cuda_interop_stage_t0 = std::chrono::high_resolution_clock::now();
            ret = cuda_interop_transform_fd(ctx->dmabuff_fd[v4l2_buf.index],
                                            g_cuda_interop_input_scratch_fd[v4l2_buf.index],
                                            ctx->width, ctx->height);
            auto cuda_interop_stage_t1 = std::chrono::high_resolution_clock::now();
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while transforming main DMABUF to CUDA interop input scratch" << endl;
                break;
            }
            NvBufSurface *input_scratch_surf = 0;
            ret = NvBufSurfaceFromFd(g_cuda_interop_input_scratch_fd[v4l2_buf.index], (void**)(&input_scratch_surf));
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while calling NvBufSurfaceFromFd for CUDA interop input scratch" << endl;
                break;
            }
            NvBufSurface *output_scratch_surf = 0;
            ret = NvBufSurfaceFromFd(g_cuda_interop_output_scratch_fd[v4l2_buf.index], (void**)(&output_scratch_surf));
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while calling NvBufSurfaceFromFd for CUDA interop output scratch" << endl;
                break;
            }
            if (input_scratch_surf->surfaceList[0].mappedAddr.eglImage == NULL)
            {
                if (NvBufSurfaceMapEglImage(input_scratch_surf, 0) != 0)
                {
                    abort(ctx);
                    cerr << "Unable to map CUDA interop input scratch fd to EGLImage" << endl;
                    break;
                }
            }
            if (output_scratch_surf->surfaceList[0].mappedAddr.eglImage == NULL)
            {
                if (NvBufSurfaceMapEglImage(output_scratch_surf, 0) != 0)
                {
                    abort(ctx);
                    cerr << "Unable to map CUDA interop output scratch fd to EGLImage" << endl;
                    break;
                }
            }
            auto cuda_interop_stage_t2 = std::chrono::high_resolution_clock::now();
            ret = cuda_process_egl_images(input_scratch_surf->surfaceList[0].mappedAddr.eglImage,
                                          output_scratch_surf->surfaceList[0].mappedAddr.eglImage,
                                          ctx->width, ctx->height);
            auto cuda_interop_stage_t3 = std::chrono::high_resolution_clock::now();
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while CUDA interop processing on EGLImage scratch buffers" << endl;
                break;
            }
            if (NvBufSurfaceUnMapEglImage(input_scratch_surf, 0) != 0)
            {
                abort(ctx);
                cerr << "Unable to unmap CUDA interop input scratch EGLImage" << endl;
                break;
            }
            if (NvBufSurfaceUnMapEglImage(output_scratch_surf, 0) != 0)
            {
                abort(ctx);
                cerr << "Unable to unmap CUDA interop output scratch EGLImage" << endl;
                break;
            }
            auto cuda_interop_stage_t4 = std::chrono::high_resolution_clock::now();
            ret = cuda_interop_transform_fd(g_cuda_interop_output_scratch_fd[v4l2_buf.index],
                                            ctx->dmabuff_fd[v4l2_buf.index],
                                            ctx->width, ctx->height);
            auto cuda_interop_stage_t5 = std::chrono::high_resolution_clock::now();
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while transforming CUDA interop output scratch back to main DMABUF" << endl;
                break;
            }
            static int cuda_interop_stage_frame = 0;
            static double cuda_interop_stage_total_ms = 0.0;
            cuda_interop_stage_frame++;
            double input_transform_ms = std::chrono::duration<double, std::milli>(cuda_interop_stage_t1 - cuda_interop_stage_t0).count();
            double cuda_call_ms = std::chrono::duration<double, std::milli>(cuda_interop_stage_t3 - cuda_interop_stage_t2).count();
            double output_transform_ms = std::chrono::duration<double, std::milli>(cuda_interop_stage_t5 - cuda_interop_stage_t4).count();
            double total_stage_ms = std::chrono::duration<double, std::milli>(cuda_interop_stage_t5 - cuda_interop_stage_t0).count();
            cuda_interop_stage_total_ms += total_stage_ms;
            if (cuda_interop_stage_frame <= 5 || cuda_interop_stage_frame % 100 == 0)
            {
                cerr << "CUDA_INTEROP_STAGE_TIMING frame=" << cuda_interop_stage_frame
                     << " input_transform_ms=" << input_transform_ms
                     << " cuda_call_ms=" << cuda_call_ms
                     << " output_transform_ms=" << output_transform_ms
                     << " total_stage_ms=" << total_stage_ms
                     << " avg_total_stage_ms=" << (cuda_interop_stage_total_ms / cuda_interop_stage_frame)
                     << endl;
            }

            if (ctx->enc_output_memory_type == V4L2_MEMORY_DMABUF)
"""
    if "CUDA interop scratch buffers are not allocated" not in text:
        if insert_marker not in text:
            raise RuntimeError("NvBufSurfaceFromFd insertion block not found")
        text = text.replace(insert_marker, insert_replacement, 1)

    path.write_text(text, encoding="utf-8")


def patch_makefile(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "/usr/local/cuda/include" not in text:
        text = text.replace(
            "include ../Rules.mk\n",
            "include ../Rules.mk\n\nCPPFLAGS += -I/usr/local/cuda/include\nLDFLAGS += -L/usr/local/cuda/lib64 -lcuda\n",
            1,
        )
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Patch MMAPI transcode sample with a CUDA/EGLImage scratch interop "
            "safety verifier. Default mode is identity; set CUDA_INTEROP_MODE "
            "to marker or dynamic_marker only after identity passes."
        )
    )
    parser.add_argument("--sample-dir", type=Path, required=True)
    args = parser.parse_args()
    patch_main(args.sample_dir / "multivideo_transcode_main.cpp")
    patch_makefile(args.sample_dir / "Makefile")
    print(f"patched CUDA interop safety verifier transcode: {args.sample_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
