from __future__ import annotations

import argparse
from pathlib import Path


LOCAL_NVANALYSIS_H = r'''#ifndef ORIN_LOCAL_NVANALYSIS_H
#define ORIN_LOCAL_NVANALYSIS_H

#include <cudaEGL.h>

#ifdef __cplusplus
extern "C" {
#endif

int processYuv420Frame(CUeglFrame *frame, unsigned int visible_width,
                       unsigned int visible_height,
                       const unsigned int plane_pitches[3]);

#ifdef __cplusplus
}
#endif

#endif
'''


LOCAL_NVCUDAPROC_H = r'''#ifndef ORIN_LOCAL_NVCUDAPROC_H
#define ORIN_LOCAL_NVCUDAPROC_H

int HandleEGLImage(void *pEGLImage, unsigned int visible_width,
                   unsigned int visible_height, unsigned int pitch0,
                   unsigned int pitch1, unsigned int pitch2);

#endif
'''


LOCAL_NVANALYSIS_CU = r'''/*
 * Project-local chroma-aware CUDA verifier for copied 03_video_cuda_enc.
 * The source EGLImage remains owned by the official sample.
 */

#include <cuda.h>
#include <cuda_runtime.h>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>

#include "NvAnalysis.h"

static __device__ unsigned char clamp_u8(float value)
{
    value = fminf(fmaxf(value, 0.0f), 255.0f);
    return static_cast<unsigned char>(value + 0.5f);
}

__global__ void warp_plane_kernel(const unsigned char *src, size_t src_pitch,
                                  unsigned char *dst, size_t dst_pitch,
                                  int width, int height, float coordinate_scale,
                                  float m00, float m01, float m02,
                                  float m10, float m11, float m12,
                                  unsigned char border)
{
    int x = blockIdx.x * blockDim.x + threadIdx.x;
    int y = blockIdx.y * blockDim.y + threadIdx.y;
    if (x >= width || y >= height)
        return;

    float lx = (x + 0.5f) * coordinate_scale - 0.5f;
    float ly = (y + 0.5f) * coordinate_scale - 0.5f;
    float sx_luma = m00 * lx + m01 * ly + m02;
    float sy_luma = m10 * lx + m11 * ly + m12;
    float sx = (sx_luma + 0.5f) / coordinate_scale - 0.5f;
    float sy = (sy_luma + 0.5f) / coordinate_scale - 0.5f;

    unsigned char out = border;
    if (sx >= 0.0f && sy >= 0.0f && sx <= width - 1 && sy <= height - 1)
    {
        int x0 = min(static_cast<int>(floorf(sx)), width - 1);
        int y0 = min(static_cast<int>(floorf(sy)), height - 1);
        int x1 = min(x0 + 1, width - 1);
        int y1 = min(y0 + 1, height - 1);
        float ax = sx - x0;
        float ay = sy - y0;
        float p00 = src[y0 * src_pitch + x0];
        float p01 = src[y0 * src_pitch + x1];
        float p10 = src[y1 * src_pitch + x0];
        float p11 = src[y1 * src_pitch + x1];
        out = clamp_u8(
            (1.0f - ax) * (1.0f - ay) * p00 +
            ax * (1.0f - ay) * p01 +
            (1.0f - ax) * ay * p10 +
            ax * ay * p11);
    }
    dst[y * dst_pitch + x] = out;
}

__global__ void warp_semiplanar_kernel(const unsigned char *src, size_t src_pitch,
                                       unsigned char *dst, size_t dst_pitch,
                                       int width, int height,
                                       float m00, float m01, float m02,
                                       float m10, float m11, float m12)
{
    int cx = blockIdx.x * blockDim.x + threadIdx.x;
    int cy = blockIdx.y * blockDim.y + threadIdx.y;
    int chroma_width = width / 2;
    int chroma_height = height / 2;
    if (cx >= chroma_width || cy >= chroma_height)
        return;

    float lx = (cx + 0.5f) * 2.0f - 0.5f;
    float ly = (cy + 0.5f) * 2.0f - 0.5f;
    float sx_luma = m00 * lx + m01 * ly + m02;
    float sy_luma = m10 * lx + m11 * ly + m12;
    int sx = static_cast<int>(floorf((sx_luma + 0.5f) * 0.5f));
    int sy = static_cast<int>(floorf((sy_luma + 0.5f) * 0.5f));
    unsigned char c0 = 128;
    unsigned char c1 = 128;
    if (sx >= 0 && sy >= 0 && sx < chroma_width && sy < chroma_height)
    {
        const unsigned char *row = src + sy * src_pitch + sx * 2;
        c0 = row[0];
        c1 = row[1];
    }
    unsigned char *row = dst + cy * dst_pitch + cx * 2;
    row[0] = c0;
    row[1] = c1;
}

static float env_float(const char *name, float fallback)
{
    const char *value = getenv(name);
    return value && value[0] ? static_cast<float>(atof(value)) : fallback;
}

static int copy_plane_to_temp(const unsigned char *src, size_t src_pitch,
                              unsigned char **temp, size_t *temp_pitch,
                              int width, int height)
{
    cudaError_t err = cudaMallocPitch(reinterpret_cast<void **>(temp), temp_pitch, width, height);
    if (err != cudaSuccess)
        return static_cast<int>(err);
    err = cudaMemcpy2D(*temp, *temp_pitch, src, src_pitch, width, height,
                       cudaMemcpyDeviceToDevice);
    return static_cast<int>(err);
}

static size_t bytes_per_component(CUarray_format format)
{
    switch (format)
    {
        case CU_AD_FORMAT_UNSIGNED_INT8:
        case CU_AD_FORMAT_SIGNED_INT8:
            return 1;
        case CU_AD_FORMAT_UNSIGNED_INT16:
        case CU_AD_FORMAT_SIGNED_INT16:
        case CU_AD_FORMAT_HALF:
            return 2;
        case CU_AD_FORMAT_UNSIGNED_INT32:
        case CU_AD_FORMAT_SIGNED_INT32:
        case CU_AD_FORMAT_FLOAT:
            return 4;
        default:
            return 0;
    }
}

static cudaError_t copy_array_to_temp(CUarray array, unsigned char **temp,
                                      size_t *temp_pitch, size_t *row_bytes,
                                      size_t *rows, int plane)
{
    CUDA_ARRAY3D_DESCRIPTOR desc;
    CUresult cu_status = cuArray3DGetDescriptor(&desc, array);
    if (cu_status != CUDA_SUCCESS)
        return cudaErrorInvalidValue;
    size_t component_bytes = bytes_per_component(desc.Format);
    if (component_bytes == 0 || desc.Width == 0 || desc.Height == 0 || desc.NumChannels == 0)
        return cudaErrorInvalidValue;
    *row_bytes = desc.Width * desc.NumChannels * component_bytes;
    *rows = desc.Height;
    cudaError_t err = cudaMallocPitch(
        reinterpret_cast<void **>(temp), temp_pitch, *row_bytes, *rows);
    if (err != cudaSuccess)
        return err;
    CUDA_MEMCPY2D copy;
    memset(&copy, 0, sizeof(copy));
    copy.srcMemoryType = CU_MEMORYTYPE_ARRAY;
    copy.srcArray = array;
    copy.dstMemoryType = CU_MEMORYTYPE_DEVICE;
    copy.dstDevice = reinterpret_cast<CUdeviceptr>(*temp);
    copy.dstPitch = *temp_pitch;
    copy.WidthInBytes = *row_bytes;
    copy.Height = *rows;
    cu_status = cuMemcpy2D(&copy);
    if (cu_status != CUDA_SUCCESS)
        return cudaErrorInvalidValue;
    static bool printed_plane[3] = {false, false, false};
    if (plane >= 0 && plane < 3 && !printed_plane[plane])
    {
        fprintf(stderr,
                "CUDA_YUV420_ARRAY plane=%d width_elements=%zu height=%zu "
                "channels=%u format=%d row_bytes=%zu temp_pitch=%zu\n",
                plane, desc.Width, desc.Height, desc.NumChannels,
                static_cast<int>(desc.Format), *row_bytes, *temp_pitch);
        printed_plane[plane] = true;
    }
    return cudaSuccess;
}

static cudaError_t copy_temp_to_array(const unsigned char *temp, size_t temp_pitch,
                                      CUarray array, size_t row_bytes, size_t rows)
{
    CUDA_MEMCPY2D copy;
    memset(&copy, 0, sizeof(copy));
    copy.srcMemoryType = CU_MEMORYTYPE_DEVICE;
    copy.srcDevice = reinterpret_cast<CUdeviceptr>(temp);
    copy.srcPitch = temp_pitch;
    copy.dstMemoryType = CU_MEMORYTYPE_ARRAY;
    copy.dstArray = array;
    copy.WidthInBytes = row_bytes;
    copy.Height = rows;
    CUresult cu_status = cuMemcpy2D(&copy);
    return cu_status == CUDA_SUCCESS ? cudaSuccess : cudaErrorInvalidValue;
}

extern "C" int processYuv420Frame(CUeglFrame *frame, unsigned int visible_width,
                                  unsigned int visible_height,
                                  const unsigned int plane_pitches[3])
{
    if (frame == nullptr)
        return static_cast<int>(cudaErrorInvalidValue);

    const char *mode = getenv("CUDA_YUV_MODE");
    if (mode == nullptr)
        mode = "copy";

    if (!strcmp(mode, "noop"))
    {
        static int noop_frame_count = 0;
        noop_frame_count++;
        if (noop_frame_count <= 5 || noop_frame_count % 100 == 0)
        {
            fprintf(stderr,
                    "CUDA_YUV420_FRAME frame=%d mode=noop width=%u height=%u "
                    "planes=%u pitches=%u,%u,%u color=%d elapsed_ms=0.000000 "
                    "avg_ms=0.000000 status=0\n",
                    noop_frame_count, visible_width, visible_height,
                    frame->planeCount, plane_pitches[0], plane_pitches[1],
                    plane_pitches[2], static_cast<int>(frame->eglColorFormat));
        }
        return static_cast<int>(cudaSuccess);
    }
    if (frame->frameType != CU_EGL_FRAME_TYPE_PITCH &&
        frame->frameType != CU_EGL_FRAME_TYPE_ARRAY)
        return static_cast<int>(cudaErrorInvalidValue);
    if (frame->planeCount != 2 && frame->planeCount != 3)
        return static_cast<int>(cudaErrorInvalidValue);

    float m00 = 1.0f;
    float m01 = 0.0f;
    float m02 = 0.0f;
    float m10 = 0.0f;
    float m11 = 1.0f;
    float m12 = 0.0f;
    if (!strcmp(mode, "translate"))
    {
        int dx = getenv("CUDA_YUV_DX") ? atoi(getenv("CUDA_YUV_DX")) : 8;
        int dy = getenv("CUDA_YUV_DY") ? atoi(getenv("CUDA_YUV_DY")) : 0;
        if ((dx & 1) || (dy & 1))
            return static_cast<int>(cudaErrorInvalidValue);
        m02 = -static_cast<float>(dx);
        m12 = -static_cast<float>(dy);
    }
    else if (!strcmp(mode, "affine"))
    {
        m00 = env_float("CUDA_YUV_M00", 1.0f);
        m01 = env_float("CUDA_YUV_M01", 0.0f);
        m02 = env_float("CUDA_YUV_M02", -8.0f);
        m10 = env_float("CUDA_YUV_M10", 0.0f);
        m11 = env_float("CUDA_YUV_M11", 1.0f);
        m12 = env_float("CUDA_YUV_M12", 0.0f);
    }
    else if (strcmp(mode, "copy") && strcmp(mode, "identity"))
    {
        return static_cast<int>(cudaErrorInvalidValue);
    }

    int width = static_cast<int>(visible_width);
    int height = static_cast<int>(visible_height);
    size_t frame_pitches[3] = {
        static_cast<size_t>(plane_pitches[0]),
        static_cast<size_t>(plane_pitches[1]),
        static_cast<size_t>(plane_pitches[2]),
    };
    if (width <= 0 || height <= 0)
        return static_cast<int>(cudaErrorInvalidValue);
    if (frame->frameType == CU_EGL_FRAME_TYPE_PITCH)
    {
        if (frame_pitches[0] < static_cast<size_t>(width))
            return static_cast<int>(cudaErrorInvalidValue);
        if (frame->planeCount == 3 &&
            (frame_pitches[1] < static_cast<size_t>(width / 2) ||
             frame_pitches[2] < static_cast<size_t>(width / 2)))
            return static_cast<int>(cudaErrorInvalidValue);
        if (frame->planeCount == 2 && frame_pitches[1] < static_cast<size_t>(width))
            return static_cast<int>(cudaErrorInvalidValue);
    }
    unsigned char *temp[3] = {nullptr, nullptr, nullptr};
    size_t temp_pitch[3] = {0, 0, 0};
    unsigned char *warp_input[3] = {nullptr, nullptr, nullptr};
    size_t warp_input_pitch[3] = {0, 0, 0};
    size_t row_bytes[3] = {0, 0, 0};
    size_t array_rows[3] = {0, 0, 0};
    int plane_width[3] = {width, width / 2, width / 2};
    int plane_height[3] = {height, height / 2, height / 2};
    int plane_count = frame->planeCount == 3 ? 3 : 2;

    cudaEvent_t start = nullptr;
    cudaEvent_t stop = nullptr;
    cudaEventCreate(&start);
    cudaEventCreate(&stop);
    cudaEventRecord(start);

    cudaError_t err = cudaSuccess;
    for (int plane = 0; plane < plane_count; ++plane)
    {
        int copy_width = frame->planeCount == 2 && plane == 1 ? width : plane_width[plane];
        if (frame->frameType == CU_EGL_FRAME_TYPE_ARRAY)
        {
            err = copy_array_to_temp(
                frame->frame.pArray[plane], &temp[plane], &temp_pitch[plane],
                &row_bytes[plane], &array_rows[plane], plane);
            if (err == cudaSuccess &&
                (row_bytes[plane] != static_cast<size_t>(copy_width) ||
                 array_rows[plane] < static_cast<size_t>(plane_height[plane])))
                err = cudaErrorInvalidValue;
        }
        else
        {
            row_bytes[plane] = copy_width;
            array_rows[plane] = plane_height[plane];
            err = static_cast<cudaError_t>(
                copy_plane_to_temp(
                    reinterpret_cast<unsigned char *>(frame->frame.pPitch[plane]),
                    frame_pitches[plane], &temp[plane], &temp_pitch[plane],
                    copy_width, plane_height[plane]));
        }
        if (err != cudaSuccess)
            goto cleanup;
    }

    if (!strcmp(mode, "copy") || !strcmp(mode, "identity"))
    {
        for (int plane = 0; plane < plane_count; ++plane)
        {
            int copy_width = frame->planeCount == 2 && plane == 1 ? width : plane_width[plane];
            if (frame->frameType == CU_EGL_FRAME_TYPE_ARRAY)
                err = copy_temp_to_array(
                    temp[plane], temp_pitch[plane], frame->frame.pArray[plane],
                    row_bytes[plane], plane_height[plane]);
            else
                err = cudaMemcpy2D(
                    frame->frame.pPitch[plane], frame_pitches[plane],
                    temp[plane], temp_pitch[plane], copy_width,
                    plane_height[plane], cudaMemcpyDeviceToDevice);
            if (err != cudaSuccess)
                goto cleanup;
        }
    }
    else
    {
        dim3 block(16, 16);
        unsigned char *dst_y = frame->frameType == CU_EGL_FRAME_TYPE_ARRAY
                                   ? temp[0]
                                   : reinterpret_cast<unsigned char *>(frame->frame.pPitch[0]);
        size_t dst_y_pitch = frame->frameType == CU_EGL_FRAME_TYPE_ARRAY
                                 ? temp_pitch[0]
                                 : frame_pitches[0];
        for (int plane = 0; plane < plane_count; ++plane)
        {
            err = cudaMallocPitch(
                reinterpret_cast<void **>(&warp_input[plane]),
                &warp_input_pitch[plane], row_bytes[plane], plane_height[plane]);
            if (err != cudaSuccess)
                goto cleanup;
            err = cudaMemcpy2D(
                warp_input[plane], warp_input_pitch[plane],
                temp[plane], temp_pitch[plane],
                row_bytes[plane], plane_height[plane],
                cudaMemcpyDeviceToDevice);
            if (err != cudaSuccess)
                goto cleanup;
        }
        dim3 grid_y((width + block.x - 1) / block.x, (height + block.y - 1) / block.y);
        warp_plane_kernel<<<grid_y, block>>>(
            warp_input[0], warp_input_pitch[0], dst_y, dst_y_pitch,
            width, height, 1.0f, m00, m01, m02, m10, m11, m12, 16);
        err = cudaGetLastError();
        if (err != cudaSuccess)
            goto cleanup;

        if (frame->planeCount == 3)
        {
            dim3 grid_c(((width / 2) + block.x - 1) / block.x,
                        ((height / 2) + block.y - 1) / block.y);
            for (int plane = 1; plane < 3; ++plane)
            {
                unsigned char *dst = frame->frameType == CU_EGL_FRAME_TYPE_ARRAY
                                         ? temp[plane]
                                         : reinterpret_cast<unsigned char *>(frame->frame.pPitch[plane]);
                size_t dst_pitch = frame->frameType == CU_EGL_FRAME_TYPE_ARRAY
                                       ? temp_pitch[plane]
                                       : frame_pitches[plane];
                warp_plane_kernel<<<grid_c, block>>>(
                    warp_input[plane], warp_input_pitch[plane], dst, dst_pitch,
                    width / 2, height / 2, 2.0f,
                    m00, m01, m02, m10, m11, m12, 128);
                err = cudaGetLastError();
                if (err != cudaSuccess)
                    goto cleanup;
            }
        }
        else
        {
            unsigned char *dst = frame->frameType == CU_EGL_FRAME_TYPE_ARRAY
                                     ? temp[1]
                                     : reinterpret_cast<unsigned char *>(frame->frame.pPitch[1]);
            size_t dst_pitch = frame->frameType == CU_EGL_FRAME_TYPE_ARRAY
                                   ? temp_pitch[1]
                                   : frame_pitches[1];
            dim3 grid_uv(((width / 2) + block.x - 1) / block.x,
                         ((height / 2) + block.y - 1) / block.y);
            warp_semiplanar_kernel<<<grid_uv, block>>>(
                warp_input[1], warp_input_pitch[1], dst, dst_pitch,
                width, height, m00, m01, m02, m10, m11, m12);
            err = cudaGetLastError();
            if (err != cudaSuccess)
                goto cleanup;
        }
        err = cudaDeviceSynchronize();
        if (err == cudaSuccess && frame->frameType == CU_EGL_FRAME_TYPE_ARRAY)
        {
            for (int plane = 0; plane < plane_count; ++plane)
            {
                err = copy_temp_to_array(
                    temp[plane], temp_pitch[plane], frame->frame.pArray[plane],
                    row_bytes[plane], plane_height[plane]);
                if (err != cudaSuccess)
                    break;
            }
        }
    }

cleanup:
    cudaEventRecord(stop);
    cudaEventSynchronize(stop);
    float elapsed_ms = 0.0f;
    cudaEventElapsedTime(&elapsed_ms, start, stop);
    static int frame_count = 0;
    static double total_ms = 0.0;
    frame_count++;
    total_ms += elapsed_ms;
    if (frame_count <= 5 || frame_count % 100 == 0 || err != cudaSuccess)
    {
        fprintf(stderr,
                "CUDA_YUV420_FRAME frame=%d mode=%s width=%d height=%d planes=%u "
                "pitches=%zu,%zu,%zu color=%d elapsed_ms=%.6f avg_ms=%.6f status=%d\n",
                frame_count, mode, width, height, frame->planeCount,
                frame_pitches[0], frame_pitches[1], frame_pitches[2],
                static_cast<int>(frame->eglColorFormat), elapsed_ms,
                total_ms / frame_count, static_cast<int>(err));
    }
    for (int plane = 0; plane < 3; ++plane)
        cudaFree(warp_input[plane]);
    for (int plane = 0; plane < 3; ++plane)
        cudaFree(temp[plane]);
    cudaEventDestroy(stop);
    cudaEventDestroy(start);
    return static_cast<int>(err);
}
'''


LOCAL_NVCUDAPROC_CPP = r'''/*
 * Project-local EGLImage ownership wrapper for copied 03_video_cuda_enc.
 */

#include <cstdio>
#include <cuda.h>
#include <cuda_runtime.h>
#include <cudaEGL.h>
#include <EGL/egl.h>

#include "NvAnalysis.h"
#include "NvCudaProc.h"

int HandleEGLImage(void *pEGLImage, unsigned int visible_width,
                   unsigned int visible_height, unsigned int pitch0,
                   unsigned int pitch1, unsigned int pitch2)
{
    EGLImageKHR image = *reinterpret_cast<EGLImageKHR *>(pEGLImage);
    CUgraphicsResource resource = nullptr;
    CUeglFrame frame;
    cudaFree(0);
    CUresult status = cuGraphicsEGLRegisterImage(
        &resource, image, CU_GRAPHICS_MAP_RESOURCE_FLAGS_NONE);
    if (status != CUDA_SUCCESS)
    {
        fprintf(stderr, "CUDA_YUV420_ERROR register=%d\n", status);
        return -1;
    }
    status = cuGraphicsResourceGetMappedEglFrame(&frame, resource, 0, 0);
    if (status != CUDA_SUCCESS)
    {
        fprintf(stderr, "CUDA_YUV420_ERROR map=%d\n", status);
        cuGraphicsUnregisterResource(resource);
        return -1;
    }
    status = cuCtxSynchronize();
    if (status != CUDA_SUCCESS)
    {
        fprintf(stderr, "CUDA_YUV420_ERROR pre_sync=%d\n", status);
        cuGraphicsUnregisterResource(resource);
        return -1;
    }

    static bool printed = false;
    if (!printed)
    {
        fprintf(stderr,
                "CUDA_YUV420_INFO egl_width=%u egl_height=%u visible_width=%u "
                "visible_height=%u first_pitch=%u pitches=%u,%u,%u planes=%u "
                "frame_type=%d color=%d channels=%u\n",
                frame.width, frame.height, visible_width, visible_height,
                frame.pitch, pitch0, pitch1, pitch2, frame.planeCount,
                static_cast<int>(frame.frameType),
                static_cast<int>(frame.eglColorFormat), frame.numChannels);
        printed = true;
    }

    unsigned int plane_pitches[3] = {pitch0, pitch1, pitch2};
    int result = processYuv420Frame(
        &frame, visible_width, visible_height, plane_pitches);
    status = cuCtxSynchronize();
    if (status != CUDA_SUCCESS)
    {
        fprintf(stderr, "CUDA_YUV420_ERROR post_sync=%d\n", status);
        result = -1;
    }
    status = cuGraphicsUnregisterResource(resource);
    if (status != CUDA_SUCCESS)
    {
        fprintf(stderr, "CUDA_YUV420_ERROR unregister=%d\n", status);
        result = -1;
    }
    return result;
}
'''


def patch_makefile(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = text.replace("$(ALGO_CUDA_DIR)/NvAnalysis.o", "NvAnalysis.o")
    text = text.replace("$(ALGO_CUDA_DIR)/NvCudaProc.o", "NvCudaProc.o")
    if "NvAnalysis.o: NvAnalysis.cu" not in text:
        marker = "%.o: %.cpp\n\t@echo \"Compiling: $<\"\n\t$(CPP) $(CPPFLAGS) -c $<\n"
        replacement = (
            marker
            + "\nNvAnalysis.o: NvAnalysis.cu\n"
            + "\t@echo \"Compiling: $<\"\n"
            + "\t$(NVCC) -I$(ALGO_CUDA_DIR) -Xcompiler -fPIC "
            + "-gencode arch=compute_87,code=sm_87 -o $@ -c $<\n"
        )
        if marker not in text:
            raise RuntimeError("local C++ compile rule not found")
        text = text.replace(marker, replacement, 1)
    path.write_text(text, encoding="utf-8")


def patch_main(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "CUDA_YUV420_HANDLE_FAILURE" in text:
        return
    old = "    HandleEGLImage(&ctx->eglimg);\n"
    new = (
        "    if (HandleEGLImage(&ctx->eglimg, ctx->width, ctx->height,\n"
        "                       nvbuf_surf->surfaceList[0].planeParams.pitch[0],\n"
        "                       nvbuf_surf->surfaceList[0].planeParams.pitch[1],\n"
        "                       nvbuf_surf->surfaceList[0].planeParams.pitch[2]) != 0)\n"
        "    {\n"
        "        cerr << \"CUDA_YUV420_HANDLE_FAILURE\" << endl;\n"
        "        return -1;\n"
        "    }\n"
    )
    if old not in text:
        raise RuntimeError("official HandleEGLImage call not found")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_sample(sample_dir: Path) -> None:
    required = [
        sample_dir / "Makefile",
        sample_dir / "video_cuda_enc_main.cpp",
    ]
    if not all(path.exists() for path in required):
        raise FileNotFoundError("sample_dir must be a copied 03_video_cuda_enc sample")
    patch_makefile(sample_dir / "Makefile")
    patch_main(sample_dir / "video_cuda_enc_main.cpp")
    (sample_dir / "NvAnalysis.h").write_text(LOCAL_NVANALYSIS_H, encoding="utf-8")
    (sample_dir / "NvAnalysis.cu").write_text(LOCAL_NVANALYSIS_CU, encoding="utf-8")
    (sample_dir / "NvCudaProc.h").write_text(LOCAL_NVCUDAPROC_H, encoding="utf-8")
    (sample_dir / "NvCudaProc.cpp").write_text(LOCAL_NVCUDAPROC_CPP, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Patch a copied 03_video_cuda_enc sample with a chroma-aware YUV420 CUDA verifier."
    )
    parser.add_argument("sample_dir", type=Path)
    args = parser.parse_args()
    patch_sample(args.sample_dir)
    print(f"patched chroma-aware CUDA verifier: {args.sample_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
