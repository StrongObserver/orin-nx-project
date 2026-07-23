from __future__ import annotations

import argparse
from pathlib import Path


CUDA_KERNEL = r'''
#include <cuda_runtime.h>
#include <stdint.h>

__global__ void copy_y_kernel(const unsigned char *src, size_t src_pitch,
                              unsigned char *dst, size_t dst_pitch,
                              int width, int height)
{
    int x = blockIdx.x * blockDim.x + threadIdx.x;
    int y = blockIdx.y * blockDim.y + threadIdx.y;
    if (x >= width || y >= height) return;
    dst[y * dst_pitch + x] = src[y * src_pitch + x];
}

__global__ void copy_uv_kernel(const unsigned char *src, size_t src_pitch,
                               unsigned char *dst, size_t dst_pitch,
                               int width, int height)
{
    int uvx = (blockIdx.x * blockDim.x + threadIdx.x) * 2;
    int uvy = blockIdx.y * blockDim.y + threadIdx.y;
    if (uvx >= width || uvy >= height / 2) return;
    const unsigned char *s = src + uvy * src_pitch + uvx;
    unsigned char *d = dst + uvy * dst_pitch + uvx;
    d[0] = s[0];
    d[1] = s[1];
}

__global__ void translate_y_kernel(const unsigned char *src, size_t src_pitch,
                                   unsigned char *dst, size_t dst_pitch,
                                   int width, int height, int dx, int dy)
{
    int x = blockIdx.x * blockDim.x + threadIdx.x;
    int y = blockIdx.y * blockDim.y + threadIdx.y;
    if (x >= width || y >= height) return;
    int sx = x - dx;
    int sy = y - dy;
    unsigned char out = 16;
    if (sx >= 0 && sy >= 0 && sx < width && sy < height)
    {
        out = src[sy * src_pitch + sx];
    }
    dst[y * dst_pitch + x] = out;
}

__global__ void translate_uv_kernel(const unsigned char *src, size_t src_pitch,
                                    unsigned char *dst, size_t dst_pitch,
                                    int width, int height, int dx, int dy)
{
    int uvx = (blockIdx.x * blockDim.x + threadIdx.x) * 2;
    int uvy = blockIdx.y * blockDim.y + threadIdx.y;
    int uv_height = height / 2;
    if (uvx >= width || uvy >= uv_height) return;
    int s_uvx = uvx - ((dx / 2) * 2);
    int s_uvy = uvy - (dy / 2);
    unsigned char c0 = 128;
    unsigned char c1 = 128;
    if (s_uvx >= 0 && s_uvy >= 0 && s_uvx + 1 < width && s_uvy < uv_height)
    {
        const unsigned char *s = src + s_uvy * src_pitch + s_uvx;
        c0 = s[0];
        c1 = s[1];
    }
    unsigned char *d = dst + uvy * dst_pitch + uvx;
    d[0] = c0;
    d[1] = c1;
}

extern "C" cudaError_t cuda_double_surface_process_nv12(
    const unsigned char *src_y, const unsigned char *src_uv, size_t src_pitch,
    unsigned char *dst_y, unsigned char *dst_uv, size_t dst_pitch,
    int width, int height, int mode, int dx, int dy, cudaStream_t stream)
{
    cudaError_t err = cudaMemset2DAsync(dst_y, dst_pitch, 0, dst_pitch, height, stream);
    if (err != cudaSuccess) return err;
    err = cudaMemset2DAsync(dst_uv, dst_pitch, 128, dst_pitch, height / 2, stream);
    if (err != cudaSuccess) return err;

    dim3 block(16, 16);
    dim3 grid_y((width + block.x - 1) / block.x, (height + block.y - 1) / block.y);
    dim3 grid_uv(((width / 2) + block.x - 1) / block.x, ((height / 2) + block.y - 1) / block.y);
    if (mode == 0)
    {
        copy_y_kernel<<<grid_y, block, 0, stream>>>(src_y, src_pitch, dst_y, dst_pitch, width, height);
        err = cudaGetLastError();
        if (err != cudaSuccess) return err;
        copy_uv_kernel<<<grid_uv, block, 0, stream>>>(src_uv, src_pitch, dst_uv, dst_pitch, width, height);
        err = cudaGetLastError();
    }
    else if (mode == 1)
    {
        translate_y_kernel<<<grid_y, block, 0, stream>>>(src_y, src_pitch, dst_y, dst_pitch, width, height, dx, dy);
        err = cudaGetLastError();
        if (err != cudaSuccess) return err;
        translate_uv_kernel<<<grid_uv, block, 0, stream>>>(src_uv, src_pitch, dst_uv, dst_pitch, width, height, dx, dy);
        err = cudaGetLastError();
    }
    else
    {
        return cudaErrorInvalidValue;
    }
    if (err != cudaSuccess) return err;
    return cudaStreamSynchronize(stream);
}
'''


HELPERS = r'''
extern "C" cudaError_t cuda_double_surface_process_nv12(
    const unsigned char *src_y, const unsigned char *src_uv, size_t src_pitch,
    unsigned char *dst_y, unsigned char *dst_uv, size_t dst_pitch,
    int width, int height, int mode, int dx, int dy, cudaStream_t stream);

static int g_double_surface_input_scratch_fd[MAX_BUFFERS];
static int g_double_surface_output_scratch_fd[MAX_BUFFERS];
static bool g_double_surface_scratch_fd_ready = false;
static std::string g_double_surface_mode = "vic_roundtrip";

static void
init_double_surface_scratch_fd_array()
{
    if (!g_double_surface_scratch_fd_ready)
    {
        for (int i = 0; i < MAX_BUFFERS; ++i)
        {
            g_double_surface_input_scratch_fd[i] = -1;
            g_double_surface_output_scratch_fd[i] = -1;
        }
        g_double_surface_scratch_fd_ready = true;
    }
}

static int
double_surface_transform_fd(int src_fd, int dst_fd, uint32_t width, uint32_t height)
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
cuda_check(cudaError_t err, const char *what)
{
    if (err != cudaSuccess)
    {
        cerr << "CUDA_DOUBLE_SURFACE_ERROR what=" << what
             << " err=" << cudaGetErrorString(err) << endl;
        return -1;
    }
    return 0;
}

static int
driver_check(CUresult err, const char *what)
{
    if (err != CUDA_SUCCESS)
    {
        const char *name = NULL;
        const char *message = NULL;
        cuGetErrorName(err, &name);
        cuGetErrorString(err, &message);
        cerr << "CUDA_DOUBLE_SURFACE_ERROR what=" << what
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
    if (ready) return 0;
    CUdevice device;
    if (driver_check(cuInit(0), "cuInit") != 0) return -1;
    if (driver_check(cuDeviceGet(&device, 0), "cuDeviceGet") != 0) return -1;
    if (driver_check(cuDevicePrimaryCtxRetain(&primary_ctx, device), "cuDevicePrimaryCtxRetain") != 0) return -1;
    if (driver_check(cuCtxSetCurrent(primary_ctx), "cuCtxSetCurrent") != 0) return -1;
    ready = true;
    return 0;
}

static int
double_surface_cuda_egl(EGLImageKHR input_egl, EGLImageKHR output_egl,
                        uint32_t width, uint32_t height)
{
    static int frame_count = 0;
    int current_frame = frame_count + 1;
    const char *mode_env = getenv("CUDA_DOUBLE_SURFACE_MODE");
    if (mode_env && mode_env[0] != '\0')
    {
        g_double_surface_mode = mode_env;
    }
    int mode = -1;
    int dx = 0;
    int dy = 0;
    if (g_double_surface_mode == "cuda_copy")
    {
        mode = 0;
    }
    else if (g_double_surface_mode == "cuda_translate")
    {
        mode = 1;
        const char *dx_env = getenv("CUDA_DOUBLE_SURFACE_DX");
        const char *dy_env = getenv("CUDA_DOUBLE_SURFACE_DY");
        dx = dx_env ? atoi(dx_env) : 8;
        dy = dy_env ? atoi(dy_env) : 0;
    }
    else
    {
        cerr << "CUDA_DOUBLE_SURFACE_ERROR unsupported_cuda_mode=" << g_double_surface_mode << endl;
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

    auto t0 = std::chrono::high_resolution_clock::now();
    if (driver_check(cuGraphicsEGLRegisterImage(&input_resource, input_egl, CU_GRAPHICS_MAP_RESOURCE_FLAGS_NONE),
                     "cuGraphicsEGLRegisterImage_input") != 0)
    {
        return -1;
    }
    if (driver_check(cuGraphicsEGLRegisterImage(&output_resource, output_egl, CU_GRAPHICS_MAP_RESOURCE_FLAGS_NONE),
                     "cuGraphicsEGLRegisterImage_output") != 0)
    {
        cuGraphicsUnregisterResource(input_resource);
        return -1;
    }
    if (driver_check(cuGraphicsResourceGetMappedEglFrame(&input_frame, input_resource, 0, 0),
                     "cuGraphicsResourceGetMappedEglFrame_input") != 0 ||
        driver_check(cuGraphicsResourceGetMappedEglFrame(&output_frame, output_resource, 0, 0),
                     "cuGraphicsResourceGetMappedEglFrame_output") != 0)
    {
        cuGraphicsUnregisterResource(output_resource);
        cuGraphicsUnregisterResource(input_resource);
        return -1;
    }
    if (driver_check(cuCtxSynchronize(), "cuCtxSynchronize_after_map") != 0)
    {
        cuGraphicsUnregisterResource(output_resource);
        cuGraphicsUnregisterResource(input_resource);
        return -1;
    }
    auto t1 = std::chrono::high_resolution_clock::now();

    if (input_frame.frameType != CU_EGL_FRAME_TYPE_PITCH ||
        output_frame.frameType != CU_EGL_FRAME_TYPE_PITCH ||
        input_frame.planeCount < 2 || output_frame.planeCount < 2)
    {
        cerr << "CUDA_DOUBLE_SURFACE_ERROR unsupported_layout"
             << " input_type=" << input_frame.frameType
             << " output_type=" << output_frame.frameType
             << " input_planes=" << input_frame.planeCount
             << " output_planes=" << output_frame.planeCount << endl;
        cuGraphicsUnregisterResource(output_resource);
        cuGraphicsUnregisterResource(input_resource);
        return -1;
    }

    cudaError_t cuda_status = cuda_double_surface_process_nv12(
        (const unsigned char *)input_frame.frame.pPitch[0],
        (const unsigned char *)input_frame.frame.pPitch[1],
        input_frame.pitch,
        (unsigned char *)output_frame.frame.pPitch[0],
        (unsigned char *)output_frame.frame.pPitch[1],
        output_frame.pitch,
        width,
        height,
        mode,
        dx,
        dy,
        0);
    if (cuda_check(cuda_status, "cuda_double_surface_process_nv12") != 0)
    {
        cuGraphicsUnregisterResource(output_resource);
        cuGraphicsUnregisterResource(input_resource);
        return -1;
    }
    if (driver_check(cuCtxSynchronize(), "cuCtxSynchronize_before_unregister") != 0)
    {
        cuGraphicsUnregisterResource(output_resource);
        cuGraphicsUnregisterResource(input_resource);
        return -1;
    }
    auto t2 = std::chrono::high_resolution_clock::now();
    CUresult unregister_output = cuGraphicsUnregisterResource(output_resource);
    CUresult unregister_input = cuGraphicsUnregisterResource(input_resource);
    auto t3 = std::chrono::high_resolution_clock::now();
    if (unregister_output != CUDA_SUCCESS || unregister_input != CUDA_SUCCESS)
    {
        cerr << "CUDA_DOUBLE_SURFACE_ERROR unregister output=" << unregister_output
             << " input=" << unregister_input << endl;
        return -1;
    }

    frame_count++;
    static double total_ms = 0.0;
    double map_ms = std::chrono::duration<double, std::milli>(t1 - t0).count();
    double process_ms = std::chrono::duration<double, std::milli>(t2 - t1).count();
    double unregister_ms = std::chrono::duration<double, std::milli>(t3 - t2).count();
    double elapsed_ms = std::chrono::duration<double, std::milli>(t3 - t0).count();
    total_ms += elapsed_ms;
    if (frame_count <= 5 || frame_count % 100 == 0)
    {
        cerr << "CUDA_DOUBLE_SURFACE_FRAME frame=" << frame_count
             << " mode=" << g_double_surface_mode
             << " dx=" << dx
             << " dy=" << dy
             << " width=" << width
             << " height=" << height
             << " input_pitch=" << input_frame.pitch
             << " output_pitch=" << output_frame.pitch
             << " input_color=" << input_frame.eglColorFormat
             << " output_color=" << output_frame.eglColorFormat
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


def write_kernel(sample_dir: Path) -> None:
    (sample_dir / "cuda_double_surface_kernel.cu").write_text(CUDA_KERNEL, encoding="utf-8")


def patch_main(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "CUDA_DOUBLE_SURFACE_FRAME" in text:
        print(f"already CUDA double-surface patched: {path}")
        return

    text = text.replace(
        '#include "NvUtils.h"\n#include "multivideo_transcode.h"\n',
        '#include "NvUtils.h"\n#include "multivideo_transcode.h"\n'
        "#include <algorithm>\n"
        "#include <chrono>\n"
        "#include <cstdlib>\n"
        "#include <string>\n"
        "#include <cuda.h>\n"
        "#include <cudaEGL.h>\n"
        "#include <cuda_runtime.h>\n",
        1,
    )
    marker = "static void\nabort(context_t *ctx)\n{"
    if marker not in text:
        raise RuntimeError(f"abort marker not found in {path}")
    text = text.replace(marker, HELPERS + "\n" + marker, 1)

    query_marker = "    NvBufSurf::NvCommonAllocateParams cParams = {0};\n"
    if "init_double_surface_scratch_fd_array();" not in text:
        text = text.replace(query_marker, query_marker + "\n    init_double_surface_scratch_fd_array();\n", 1)

    alloc_marker = """            ret = NvBufSurf::NvAllocate(&cParams, 1, &ctx->dmabuff_fd[index]);
            TEST_ERROR(ret < 0, "Failed to create buffers", error);
"""
    alloc_insert = alloc_marker + """            NvBufSurf::NvCommonAllocateParams scratchParams = cParams;
            scratchParams.layout = NVBUF_LAYOUT_PITCH;
            scratchParams.colorFormat = NVBUF_COLOR_FORMAT_NV12_ER;
            if (g_double_surface_input_scratch_fd[index] != -1)
            {
                NvBufSurf::NvDestroy(g_double_surface_input_scratch_fd[index]);
                g_double_surface_input_scratch_fd[index] = -1;
            }
            if (g_double_surface_output_scratch_fd[index] != -1)
            {
                NvBufSurf::NvDestroy(g_double_surface_output_scratch_fd[index]);
                g_double_surface_output_scratch_fd[index] = -1;
            }
            ret = NvBufSurf::NvAllocate(&scratchParams, 1, &g_double_surface_input_scratch_fd[index]);
            TEST_ERROR(ret < 0, "Failed to create double-surface input scratch buffers", error);
            ret = NvBufSurf::NvAllocate(&scratchParams, 1, &g_double_surface_output_scratch_fd[index]);
            TEST_ERROR(ret < 0, "Failed to create double-surface output scratch buffers", error);
"""
    if "g_double_surface_input_scratch_fd[index]" not in text:
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

            const char *mode_env = getenv("CUDA_DOUBLE_SURFACE_MODE");
            if (mode_env != NULL && mode_env[0] != '\\0')
            {
                g_double_surface_mode = mode_env;
            }
            if (g_double_surface_input_scratch_fd[v4l2_buf.index] < 0 || g_double_surface_output_scratch_fd[v4l2_buf.index] < 0)
            {
                abort(ctx);
                cerr << "Double-surface scratch buffers are not allocated" << endl;
                break;
            }
            auto double_stage_t0 = std::chrono::high_resolution_clock::now();
            ret = double_surface_transform_fd(ctx->dmabuff_fd[v4l2_buf.index],
                                              g_double_surface_input_scratch_fd[v4l2_buf.index],
                                              ctx->width, ctx->height);
            auto double_stage_t1 = std::chrono::high_resolution_clock::now();
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while transforming main DMABUF to input scratch" << endl;
                break;
            }
            if (g_double_surface_mode == "vic_roundtrip")
            {
                ret = double_surface_transform_fd(g_double_surface_input_scratch_fd[v4l2_buf.index],
                                                  ctx->dmabuff_fd[v4l2_buf.index],
                                                  ctx->width, ctx->height);
                auto double_stage_t5 = std::chrono::high_resolution_clock::now();
                if (ret < 0)
                {
                    abort(ctx);
                    cerr << "Error while VIC round-trip output transform" << endl;
                    break;
                }
                static int vic_stage_frame = 0;
                static double vic_stage_total_ms = 0.0;
                vic_stage_frame++;
                double total_stage_ms = std::chrono::duration<double, std::milli>(double_stage_t5 - double_stage_t0).count();
                vic_stage_total_ms += total_stage_ms;
                if (vic_stage_frame <= 5 || vic_stage_frame % 100 == 0)
                {
                    cerr << "VIC_ROUNDTRIP_STAGE_TIMING frame=" << vic_stage_frame
                         << " input_transform_ms=" << std::chrono::duration<double, std::milli>(double_stage_t1 - double_stage_t0).count()
                         << " total_stage_ms=" << total_stage_ms
                         << " avg_total_stage_ms=" << (vic_stage_total_ms / vic_stage_frame)
                         << endl;
                }
            }
            else
            {
                NvBufSurface *input_scratch_surf = 0;
                ret = NvBufSurfaceFromFd(g_double_surface_input_scratch_fd[v4l2_buf.index], (void**)(&input_scratch_surf));
                if (ret < 0)
                {
                    abort(ctx);
                    cerr << "Error while calling NvBufSurfaceFromFd for input scratch" << endl;
                    break;
                }
                NvBufSurface *output_scratch_surf = 0;
                ret = NvBufSurfaceFromFd(g_double_surface_output_scratch_fd[v4l2_buf.index], (void**)(&output_scratch_surf));
                if (ret < 0)
                {
                    abort(ctx);
                    cerr << "Error while calling NvBufSurfaceFromFd for output scratch" << endl;
                    break;
                }
                if (input_scratch_surf->surfaceList[0].mappedAddr.eglImage == NULL)
                {
                    if (NvBufSurfaceMapEglImage(input_scratch_surf, 0) != 0)
                    {
                        abort(ctx);
                        cerr << "Unable to map input scratch fd to EGLImage" << endl;
                        break;
                    }
                }
                if (output_scratch_surf->surfaceList[0].mappedAddr.eglImage == NULL)
                {
                    if (NvBufSurfaceMapEglImage(output_scratch_surf, 0) != 0)
                    {
                        abort(ctx);
                        cerr << "Unable to map output scratch fd to EGLImage" << endl;
                        break;
                    }
                }
                auto double_stage_t2 = std::chrono::high_resolution_clock::now();
                ret = double_surface_cuda_egl(input_scratch_surf->surfaceList[0].mappedAddr.eglImage,
                                              output_scratch_surf->surfaceList[0].mappedAddr.eglImage,
                                              ctx->width, ctx->height);
                auto double_stage_t3 = std::chrono::high_resolution_clock::now();
                if (ret < 0)
                {
                    abort(ctx);
                    cerr << "Error while double-surface CUDA processing" << endl;
                    break;
                }
                if (NvBufSurfaceUnMapEglImage(input_scratch_surf, 0) != 0)
                {
                    abort(ctx);
                    cerr << "Unable to unmap input scratch EGLImage" << endl;
                    break;
                }
                if (NvBufSurfaceUnMapEglImage(output_scratch_surf, 0) != 0)
                {
                    abort(ctx);
                    cerr << "Unable to unmap output scratch EGLImage" << endl;
                    break;
                }
                auto double_stage_t4 = std::chrono::high_resolution_clock::now();
                ret = double_surface_transform_fd(g_double_surface_output_scratch_fd[v4l2_buf.index],
                                                  ctx->dmabuff_fd[v4l2_buf.index],
                                                  ctx->width, ctx->height);
                auto double_stage_t5 = std::chrono::high_resolution_clock::now();
                if (ret < 0)
                {
                    abort(ctx);
                    cerr << "Error while transforming output scratch back to main DMABUF" << endl;
                    break;
                }
                static int cuda_stage_frame = 0;
                static double cuda_stage_total_ms = 0.0;
                cuda_stage_frame++;
                double total_stage_ms = std::chrono::duration<double, std::milli>(double_stage_t5 - double_stage_t0).count();
                cuda_stage_total_ms += total_stage_ms;
                if (cuda_stage_frame <= 5 || cuda_stage_frame % 100 == 0)
                {
                    cerr << "CUDA_DOUBLE_SURFACE_STAGE_TIMING frame=" << cuda_stage_frame
                         << " mode=" << g_double_surface_mode
                         << " input_transform_ms=" << std::chrono::duration<double, std::milli>(double_stage_t1 - double_stage_t0).count()
                         << " cuda_call_ms=" << std::chrono::duration<double, std::milli>(double_stage_t3 - double_stage_t2).count()
                         << " output_transform_ms=" << std::chrono::duration<double, std::milli>(double_stage_t5 - double_stage_t4).count()
                         << " total_stage_ms=" << total_stage_ms
                         << " avg_total_stage_ms=" << (cuda_stage_total_ms / cuda_stage_frame)
                         << endl;
                }
            }

            if (ctx->enc_output_memory_type == V4L2_MEMORY_DMABUF)
"""
    if "Double-surface scratch buffers are not allocated" not in text:
        if insert_marker not in text:
            raise RuntimeError("NvBufSurfaceFromFd insertion block not found")
        text = text.replace(insert_marker, insert_replacement, 1)

    path.write_text(text, encoding="utf-8")


def patch_makefile(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "cuda_double_surface_kernel.o" not in text:
        text = text.replace(
            "OBJS := $(SRCS:.cpp=.o)\n",
            "OBJS := $(SRCS:.cpp=.o) cuda_double_surface_kernel.o\n",
            1,
        )
        text = text.replace(
            "%.o: %.cpp\n\t@echo \"Compiling: $<\"\n\t$(CPP) $(CPPFLAGS) -c $<\n",
            "%.o: %.cpp\n\t@echo \"Compiling: $<\"\n\t$(CPP) $(CPPFLAGS) -c $<\n\n"
            "cuda_double_surface_kernel.o: cuda_double_surface_kernel.cu\n"
            "\t@echo \"Compiling CUDA: $<\"\n"
            "\t/usr/local/cuda/bin/nvcc -std=c++14 -c $< -o $@\n",
            1,
        )
        text = text.replace(
            "include ../Rules.mk\n",
            "include ../Rules.mk\n\nCPPFLAGS += -I/usr/local/cuda/include\nLDFLAGS += -L/usr/local/cuda/lib64 -lcudart -lcuda\n",
            1,
        )
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Patch MMAPI sample for Test0-Test2 CUDA double-surface debugging.")
    parser.add_argument("--sample-dir", type=Path, required=True)
    args = parser.parse_args()
    write_kernel(args.sample_dir)
    patch_main(args.sample_dir / "multivideo_transcode_main.cpp")
    patch_makefile(args.sample_dir / "Makefile")
    print(f"patched CUDA double-surface debug transcode: {args.sample_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
