from __future__ import annotations

import argparse
from pathlib import Path


CUDA_KERNEL = r'''
#include <cuda_runtime.h>
#include <stdint.h>

static __device__ unsigned char clamp_u8(float value)
{
    value = fminf(fmaxf(value, 0.0f), 255.0f);
    return static_cast<unsigned char>(value + 0.5f);
}

__global__ void affine_y_kernel(const unsigned char *src, size_t src_pitch,
                                unsigned char *dst, size_t dst_pitch,
                                int width, int height,
                                float m00, float m01, float m02,
                                float m10, float m11, float m12,
                                float m20, float m21, float m22)
{
    int x = blockIdx.x * blockDim.x + threadIdx.x;
    int y = blockIdx.y * blockDim.y + threadIdx.y;
    if (x >= width || y >= height)
    {
        return;
    }

    float sx = m00 * x + m01 * y + m02;
    float sy = m10 * x + m11 * y + m12;
    float sw = m20 * x + m21 * y + m22;
    sx /= sw;
    sy /= sw;

    unsigned char out = 0;
    if (sx >= 0.0f && sy >= 0.0f && sx <= width - 1 && sy <= height - 1)
    {
        int x0 = min(static_cast<int>(floorf(sx)), width - 1);
        int y0 = min(static_cast<int>(floorf(sy)), height - 1);
        int x1 = min(x0 + 1, width - 1);
        int y1 = min(y0 + 1, height - 1);
        float ax = sx - x0;
        float ay = sy - y0;
        unsigned char p00 = src[y0 * src_pitch + x0];
        unsigned char p01 = src[y0 * src_pitch + x1];
        unsigned char p10 = src[y1 * src_pitch + x0];
        unsigned char p11 = src[y1 * src_pitch + x1];
        float w00 = (1.0f - ax) * (1.0f - ay);
        float w01 = ax * (1.0f - ay);
        float w10 = (1.0f - ax) * ay;
        float w11 = ax * ay;
        out = clamp_u8(w00 * p00 + w01 * p01 + w10 * p10 + w11 * p11);
    }
    dst[y * dst_pitch + x] = out;
}

__global__ void affine_uv_kernel(const unsigned char *src, size_t src_pitch,
                                 unsigned char *dst, size_t dst_pitch,
                                 int width, int height,
                                 float m00, float m01, float m02,
                                 float m10, float m11, float m12,
                                 float m20, float m21, float m22)
{
    int uvx = (blockIdx.x * blockDim.x + threadIdx.x) * 2;
    int uvy = blockIdx.y * blockDim.y + threadIdx.y;
    int uv_height = height / 2;
    if (uvx >= width || uvy >= uv_height)
    {
        return;
    }

    float x = uvx + 0.5f;
    float y = uvy * 2.0f + 0.5f;
    float sx = m00 * x + m01 * y + m02;
    float sy = m10 * x + m11 * y + m12;
    float sw = m20 * x + m21 * y + m22;
    sx /= sw;
    sy /= sw;

    int src_uv_x = static_cast<int>(floorf(sx * 0.5f)) * 2;
    int src_uv_y = static_cast<int>(floorf(sy * 0.5f));
    unsigned char c0 = 128;
    unsigned char c1 = 128;
    if (src_uv_x >= 0 && src_uv_y >= 0 && src_uv_x + 1 < width && src_uv_y < uv_height)
    {
        const unsigned char *src_row = src + src_uv_y * src_pitch + src_uv_x;
        c0 = src_row[0];
        c1 = src_row[1];
    }
    unsigned char *dst_row = dst + uvy * dst_pitch + uvx;
    dst_row[0] = c0;
    dst_row[1] = c1;
}

__global__ void translate_y_kernel(const unsigned char *src, size_t src_pitch,
                                   unsigned char *dst, size_t dst_pitch,
                                   int width, int height, int dx, int dy)
{
    int x = blockIdx.x * blockDim.x + threadIdx.x;
    int y = blockIdx.y * blockDim.y + threadIdx.y;
    if (x >= width || y >= height)
    {
        return;
    }
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
    if (uvx >= width || uvy >= uv_height)
    {
        return;
    }
    int s_uvx = uvx - ((dx / 2) * 2);
    int s_uvy = uvy - (dy / 2);
    unsigned char c0 = 128;
    unsigned char c1 = 128;
    if (s_uvx >= 0 && s_uvy >= 0 && s_uvx + 1 < width && s_uvy < uv_height)
    {
        const unsigned char *src_row = src + s_uvy * src_pitch + s_uvx;
        c0 = src_row[0];
        c1 = src_row[1];
    }
    unsigned char *dst_row = dst + uvy * dst_pitch + uvx;
    dst_row[0] = c0;
    dst_row[1] = c1;
}

extern "C" cudaError_t cuda_affine_warp_nv12(const unsigned char *src_y, const unsigned char *src_uv,
                                             size_t src_pitch, unsigned char *dst_y,
                                             unsigned char *dst_uv, size_t dst_pitch,
                                             int width, int height, const float *host_dst_to_src,
                                             int plane_mode, cudaStream_t stream)
{
    unsigned char *tmp_src_y = nullptr;
    unsigned char *tmp_src_uv = nullptr;
    unsigned char *tmp_dst_y = nullptr;
    unsigned char *tmp_dst_uv = nullptr;
    size_t tmp_src_y_pitch = 0;
    size_t tmp_src_uv_pitch = 0;
    size_t tmp_dst_y_pitch = 0;
    size_t tmp_dst_uv_pitch = 0;
    dim3 block(16, 16);
    dim3 grid_y((width + block.x - 1) / block.x, (height + block.y - 1) / block.y);
    dim3 grid_uv(((width / 2) + block.x - 1) / block.x, ((height / 2) + block.y - 1) / block.y);

    cudaError_t err = cudaMallocPitch(reinterpret_cast<void **>(&tmp_src_y), &tmp_src_y_pitch, width, height);
    if (err != cudaSuccess) goto cleanup;
    err = cudaMallocPitch(reinterpret_cast<void **>(&tmp_src_uv), &tmp_src_uv_pitch, width, height / 2);
    if (err != cudaSuccess) goto cleanup;
    err = cudaMallocPitch(reinterpret_cast<void **>(&tmp_dst_y), &tmp_dst_y_pitch, width, height);
    if (err != cudaSuccess) goto cleanup;
    err = cudaMallocPitch(reinterpret_cast<void **>(&tmp_dst_uv), &tmp_dst_uv_pitch, width, height / 2);
    if (err != cudaSuccess) goto cleanup;

    err = cudaMemcpy2DAsync(tmp_src_y, tmp_src_y_pitch, src_y, src_pitch, width, height,
                            cudaMemcpyDeviceToDevice, stream);
    if (err != cudaSuccess) goto cleanup;
    err = cudaMemcpy2DAsync(tmp_src_uv, tmp_src_uv_pitch, src_uv, src_pitch, width, height / 2,
                            cudaMemcpyDeviceToDevice, stream);
    if (err != cudaSuccess) goto cleanup;
    err = cudaMemset2DAsync(dst_y, dst_pitch, 0, dst_pitch, height, stream);
    if (err != cudaSuccess) goto cleanup;
    err = cudaMemset2DAsync(dst_uv, dst_pitch, 128, dst_pitch, height / 2, stream);
    if (err != cudaSuccess) goto cleanup;
    err = cudaMemset2DAsync(tmp_dst_y, tmp_dst_y_pitch, 0, tmp_dst_y_pitch, height, stream);
    if (err != cudaSuccess) goto cleanup;
    err = cudaMemset2DAsync(tmp_dst_uv, tmp_dst_uv_pitch, 128, tmp_dst_uv_pitch, height / 2, stream);
    if (err != cudaSuccess) goto cleanup;

    if (plane_mode == 3)
    {
        translate_y_kernel<<<grid_y, block, 0, stream>>>(tmp_src_y, tmp_src_y_pitch, tmp_dst_y, tmp_dst_y_pitch, width, height, 8, 0);
        err = cudaGetLastError();
        if (err != cudaSuccess) goto cleanup;
    }
    else if (plane_mode == 2)
    {
        err = cudaMemcpy2DAsync(tmp_dst_y, tmp_dst_y_pitch, tmp_src_y, tmp_src_y_pitch, width, height,
                                cudaMemcpyDeviceToDevice, stream);
        if (err != cudaSuccess) goto cleanup;
    }
    else
    {
        affine_y_kernel<<<grid_y, block, 0, stream>>>(tmp_src_y, tmp_src_y_pitch, tmp_dst_y, tmp_dst_y_pitch, width, height,
                                                      host_dst_to_src[0], host_dst_to_src[1], host_dst_to_src[2],
                                                      host_dst_to_src[3], host_dst_to_src[4], host_dst_to_src[5],
                                                      host_dst_to_src[6], host_dst_to_src[7], host_dst_to_src[8]);
        err = cudaGetLastError();
        if (err != cudaSuccess)
        {
            goto cleanup;
        }
    }
    if (plane_mode == 3)
    {
        translate_uv_kernel<<<grid_uv, block, 0, stream>>>(tmp_src_uv, tmp_src_uv_pitch, tmp_dst_uv, tmp_dst_uv_pitch, width, height, 8, 0);
        err = cudaGetLastError();
        if (err != cudaSuccess) goto cleanup;
    }
    else if (plane_mode == 1)
    {
        err = cudaMemcpy2DAsync(tmp_dst_uv, tmp_dst_uv_pitch, tmp_src_uv, tmp_src_uv_pitch, width, height / 2,
                                cudaMemcpyDeviceToDevice, stream);
        if (err != cudaSuccess) goto cleanup;
    }
    else
    {
        affine_uv_kernel<<<grid_uv, block, 0, stream>>>(tmp_src_uv, tmp_src_uv_pitch, tmp_dst_uv, tmp_dst_uv_pitch, width, height,
                                                        host_dst_to_src[0], host_dst_to_src[1], host_dst_to_src[2],
                                                        host_dst_to_src[3], host_dst_to_src[4], host_dst_to_src[5],
                                                        host_dst_to_src[6], host_dst_to_src[7], host_dst_to_src[8]);
        err = cudaGetLastError();
        if (err != cudaSuccess) goto cleanup;
    }

    err = cudaMemcpy2DAsync(dst_y, dst_pitch, tmp_dst_y, tmp_dst_y_pitch, width, height,
                            cudaMemcpyDeviceToDevice, stream);
    if (err != cudaSuccess) goto cleanup;
    err = cudaMemcpy2DAsync(dst_uv, dst_pitch, tmp_dst_uv, tmp_dst_uv_pitch, width, height / 2,
                            cudaMemcpyDeviceToDevice, stream);
    if (err != cudaSuccess) goto cleanup;
    err = cudaStreamSynchronize(stream);

cleanup:
    cudaFree(tmp_dst_uv);
    cudaFree(tmp_dst_y);
    cudaFree(tmp_src_uv);
    cudaFree(tmp_src_y);
    return err;
}
'''


HELPERS = r'''
extern "C" cudaError_t cuda_affine_warp_nv12(const unsigned char *src_y, const unsigned char *src_uv,
                                             size_t src_pitch, unsigned char *dst_y,
                                             unsigned char *dst_uv, size_t dst_pitch,
                                             int width, int height, const float *host_dst_to_src,
                                             int plane_mode, cudaStream_t stream);

static int g_cuda_affine_input_scratch_fd[MAX_BUFFERS];
static int g_cuda_affine_output_scratch_fd[MAX_BUFFERS];
static bool g_cuda_affine_scratch_fd_ready = false;
static std::string g_cuda_affine_mode = "identity";

static void
init_cuda_affine_scratch_fd_array()
{
    if (!g_cuda_affine_scratch_fd_ready)
    {
        for (int i = 0; i < MAX_BUFFERS; ++i)
        {
            g_cuda_affine_input_scratch_fd[i] = -1;
            g_cuda_affine_output_scratch_fd[i] = -1;
        }
        g_cuda_affine_scratch_fd_ready = true;
    }
}

static int
cuda_affine_transform_fd(int src_fd, int dst_fd, uint32_t width, uint32_t height)
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
cuda_runtime_check(cudaError_t err, const char *what)
{
    if (err != cudaSuccess)
    {
        cerr << "CUDA_AFFINE_ERROR what=" << what
             << " err=" << cudaGetErrorString(err) << endl;
        return -1;
    }
    return 0;
}

static int
cuda_driver_check(CUresult err, const char *what)
{
    if (err != CUDA_SUCCESS)
    {
        const char *name = NULL;
        const char *message = NULL;
        cuGetErrorName(err, &name);
        cuGetErrorString(err, &message);
        cerr << "CUDA_AFFINE_ERROR what=" << what
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
    if (cuda_driver_check(cuInit(0), "cuInit") != 0)
    {
        return -1;
    }
    CUdevice device;
    if (cuda_driver_check(cuDeviceGet(&device, 0), "cuDeviceGet") != 0)
    {
        return -1;
    }
    if (cuda_driver_check(cuDevicePrimaryCtxRetain(&primary_ctx, device), "cuDevicePrimaryCtxRetain") != 0)
    {
        return -1;
    }
    if (cuda_driver_check(cuCtxSetCurrent(primary_ctx), "cuCtxSetCurrent") != 0)
    {
        return -1;
    }
    ready = true;
    return 0;
}

static float
det3(const float m[9])
{
    return m[0] * (m[4] * m[8] - m[5] * m[7])
         - m[1] * (m[3] * m[8] - m[5] * m[6])
         + m[2] * (m[3] * m[7] - m[4] * m[6]);
}

static bool
invert3(const float src[9], float dst[9])
{
    float d = det3(src);
    if (fabs(d) < 1.0e-8f)
    {
        return false;
    }
    float inv_d = 1.0f / d;
    dst[0] =  (src[4] * src[8] - src[5] * src[7]) * inv_d;
    dst[1] = -(src[1] * src[8] - src[2] * src[7]) * inv_d;
    dst[2] =  (src[1] * src[5] - src[2] * src[4]) * inv_d;
    dst[3] = -(src[3] * src[8] - src[5] * src[6]) * inv_d;
    dst[4] =  (src[0] * src[8] - src[2] * src[6]) * inv_d;
    dst[5] = -(src[0] * src[5] - src[2] * src[3]) * inv_d;
    dst[6] =  (src[3] * src[7] - src[4] * src[6]) * inv_d;
    dst[7] = -(src[0] * src[7] - src[1] * src[6]) * inv_d;
    dst[8] =  (src[0] * src[4] - src[1] * src[3]) * inv_d;
    return true;
}

static void
make_source_to_dest_matrix(std::string mode, int frame, int width, int height, float out[9])
{
    for (int i = 0; i < 9; ++i)
    {
        out[i] = 0.0f;
    }
    out[0] = 1.0f;
    out[4] = 1.0f;
    out[8] = 1.0f;
    if (mode == "identity")
    {
        return;
    }

    float tx = 8.0f;
    float ty = 0.0f;
    float angle_deg = 0.0f;
    float scale = 1.0f;
    if (mode == "translate")
    {
        tx = 8.0f;
        ty = 0.0f;
    }
    else if (mode == "static_affine")
    {
        tx = 10.0f;
        ty = -4.0f;
        angle_deg = 2.0f;
        scale = 1.01f;
    }
    else if (mode == "dynamic_affine")
    {
        tx = 8.0f + sinf(frame * 0.05f) * 4.0f;
        ty = cosf(frame * 0.04f) * 3.0f;
        angle_deg = sinf(frame * 0.03f) * 1.5f;
        scale = 1.01f;
    }
    else
    {
        return;
    }

    float angle = angle_deg * 3.14159265f / 180.0f;
    float c = cosf(angle) * scale;
    float s = sinf(angle) * scale;
    float cx = (width - 1) * 0.5f;
    float cy = (height - 1) * 0.5f;

    out[0] = c;
    out[1] = -s;
    out[2] = cx + tx - c * cx + s * cy;
    out[3] = s;
    out[4] = c;
    out[5] = cy + ty - s * cx - c * cy;
    out[6] = 0.0f;
    out[7] = 0.0f;
    out[8] = 1.0f;
}

static int
cuda_affine_process_egl_images(EGLImageKHR input_egl, EGLImageKHR output_egl,
                               uint32_t width, uint32_t height)
{
    static int frame_count = 0;
    int current_frame = frame_count + 1;
    const char *mode_env = getenv("CUDA_AFFINE_MODE");
    if (mode_env != NULL && mode_env[0] != '\0')
    {
        g_cuda_affine_mode = mode_env;
    }
    if (g_cuda_affine_mode != "identity" &&
        g_cuda_affine_mode != "translate" &&
        g_cuda_affine_mode != "translate_direct" &&
        g_cuda_affine_mode != "translate_y_copy_uv" &&
        g_cuda_affine_mode != "translate_uv_copy_y" &&
        g_cuda_affine_mode != "static_affine" &&
        g_cuda_affine_mode != "dynamic_affine")
    {
        cerr << "CUDA_AFFINE_ERROR unsupported_mode=" << g_cuda_affine_mode << endl;
        return -1;
    }

    CUgraphicsResource input_resource = NULL;
    CUgraphicsResource output_resource = NULL;
    CUeglFrame input_frame;
    CUeglFrame output_frame;
    memset(&input_frame, 0, sizeof(input_frame));
    memset(&output_frame, 0, sizeof(output_frame));

    if (init_cuda_driver_once() != 0)
    {
        return -1;
    }

    auto register_t0 = std::chrono::high_resolution_clock::now();
    CUresult cu_status = cuGraphicsEGLRegisterImage(&input_resource, input_egl,
                                                    CU_GRAPHICS_MAP_RESOURCE_FLAGS_READ_ONLY);
    if (cu_status != CUDA_SUCCESS)
    {
        cerr << "CUDA_AFFINE_ERROR register input status=" << cu_status << endl;
        return -1;
    }
    cu_status = cuGraphicsEGLRegisterImage(&output_resource, output_egl,
                                           CU_GRAPHICS_MAP_RESOURCE_FLAGS_WRITE_DISCARD);
    if (cu_status != CUDA_SUCCESS)
    {
        cerr << "CUDA_AFFINE_ERROR register output status=" << cu_status << endl;
        cuGraphicsUnregisterResource(input_resource);
        return -1;
    }
    auto register_t1 = std::chrono::high_resolution_clock::now();

    cu_status = cuGraphicsResourceGetMappedEglFrame(&input_frame, input_resource, 0, 0);
    if (cu_status != CUDA_SUCCESS)
    {
        cerr << "CUDA_AFFINE_ERROR map input status=" << cu_status << endl;
        cuGraphicsUnregisterResource(output_resource);
        cuGraphicsUnregisterResource(input_resource);
        return -1;
    }
    cu_status = cuGraphicsResourceGetMappedEglFrame(&output_frame, output_resource, 0, 0);
    if (cu_status != CUDA_SUCCESS)
    {
        cerr << "CUDA_AFFINE_ERROR map output status=" << cu_status << endl;
        cuGraphicsUnregisterResource(output_resource);
        cuGraphicsUnregisterResource(input_resource);
        return -1;
    }
    cu_status = cuCtxSynchronize();
    if (cu_status != CUDA_SUCCESS)
    {
        cerr << "CUDA_AFFINE_ERROR sync_after_map status=" << cu_status << endl;
        cuGraphicsUnregisterResource(output_resource);
        cuGraphicsUnregisterResource(input_resource);
        return -1;
    }
    auto map_t1 = std::chrono::high_resolution_clock::now();

    if (input_frame.frameType != CU_EGL_FRAME_TYPE_PITCH ||
        output_frame.frameType != CU_EGL_FRAME_TYPE_PITCH ||
        input_frame.planeCount < 2 || output_frame.planeCount < 2)
    {
        cerr << "CUDA_AFFINE_ERROR unsupported frame layout"
             << " input_frame_type=" << input_frame.frameType
             << " output_frame_type=" << output_frame.frameType
             << " input_planes=" << input_frame.planeCount
             << " output_planes=" << output_frame.planeCount << endl;
        cuGraphicsUnregisterResource(output_resource);
        cuGraphicsUnregisterResource(input_resource);
        return -1;
    }

    float src_to_dst[9];
    float dst_to_src[9];
    std::string matrix_mode = g_cuda_affine_mode;
    if (matrix_mode == "translate_y_copy_uv" || matrix_mode == "translate_uv_copy_y")
    {
        matrix_mode = "translate";
    }
    if (matrix_mode == "translate_direct")
    {
        matrix_mode = "translate";
    }
    make_source_to_dest_matrix(matrix_mode, current_frame, width, height, src_to_dst);
    if (!invert3(src_to_dst, dst_to_src))
    {
        cerr << "CUDA_AFFINE_ERROR matrix_inversion_failed frame=" << current_frame << endl;
        cuGraphicsUnregisterResource(output_resource);
        cuGraphicsUnregisterResource(input_resource);
        return -1;
    }

    auto process_t0 = std::chrono::high_resolution_clock::now();
    cudaError_t cuda_status = cuda_affine_warp_nv12(
        (const unsigned char *)input_frame.frame.pPitch[0],
        (const unsigned char *)input_frame.frame.pPitch[1],
        input_frame.pitch,
        (unsigned char *)output_frame.frame.pPitch[0],
        (unsigned char *)output_frame.frame.pPitch[1],
        output_frame.pitch,
        width,
        height,
        dst_to_src,
        g_cuda_affine_mode == "translate_y_copy_uv" ? 1 : (g_cuda_affine_mode == "translate_uv_copy_y" ? 2 : (g_cuda_affine_mode == "translate_direct" ? 3 : 0)),
        0);
    if (cuda_runtime_check(cuda_status, "cuda_affine_warp_nv12") != 0)
    {
        cuGraphicsUnregisterResource(output_resource);
        cuGraphicsUnregisterResource(input_resource);
        return -1;
    }
    if (cuda_runtime_check(cudaDeviceSynchronize(), "cudaDeviceSynchronize") != 0)
    {
        cuGraphicsUnregisterResource(output_resource);
        cuGraphicsUnregisterResource(input_resource);
        return -1;
    }
    cu_status = cuCtxSynchronize();
    if (cu_status != CUDA_SUCCESS)
    {
        cerr << "CUDA_AFFINE_ERROR sync_before_unregister status=" << cu_status << endl;
        cuGraphicsUnregisterResource(output_resource);
        cuGraphicsUnregisterResource(input_resource);
        return -1;
    }
    auto process_t1 = std::chrono::high_resolution_clock::now();

    CUresult unregister_output = cuGraphicsUnregisterResource(output_resource);
    CUresult unregister_input = cuGraphicsUnregisterResource(input_resource);
    auto unregister_t1 = std::chrono::high_resolution_clock::now();
    if (unregister_output != CUDA_SUCCESS || unregister_input != CUDA_SUCCESS)
    {
        cerr << "CUDA_AFFINE_ERROR unregister output=" << unregister_output
             << " input=" << unregister_input << endl;
        return -1;
    }

    frame_count++;
    static double total_ms = 0.0;
    double register_ms = std::chrono::duration<double, std::milli>(register_t1 - register_t0).count();
    double map_ms = std::chrono::duration<double, std::milli>(map_t1 - register_t1).count();
    double process_ms = std::chrono::duration<double, std::milli>(process_t1 - process_t0).count();
    double unregister_ms = std::chrono::duration<double, std::milli>(unregister_t1 - process_t1).count();
    double elapsed_ms = std::chrono::duration<double, std::milli>(unregister_t1 - register_t0).count();
    total_ms += elapsed_ms;
    if (frame_count <= 5 || frame_count % 100 == 0)
    {
        cerr << "CUDA_AFFINE_FRAME frame=" << frame_count
             << " mode=" << g_cuda_affine_mode
             << " width=" << width
             << " height=" << height
             << " input_pitch=" << input_frame.pitch
             << " output_pitch=" << output_frame.pitch
             << " input_frame_width=" << input_frame.width
             << " input_frame_height=" << input_frame.height
             << " output_frame_width=" << output_frame.width
             << " output_frame_height=" << output_frame.height
             << " input_color=" << input_frame.eglColorFormat
             << " output_color=" << output_frame.eglColorFormat
             << " input_y_ptr=" << input_frame.frame.pPitch[0]
             << " input_uv_ptr=" << input_frame.frame.pPitch[1]
             << " output_y_ptr=" << output_frame.frame.pPitch[0]
             << " output_uv_ptr=" << output_frame.frame.pPitch[1]
             << " register_ms=" << register_ms
             << " map_ms=" << map_ms
             << " process_ms=" << process_ms
             << " unregister_ms=" << unregister_ms
             << " elapsed_ms=" << elapsed_ms
             << " avg_ms=" << (total_ms / frame_count)
             << " m00=" << src_to_dst[0]
             << " m01=" << src_to_dst[1]
             << " m02=" << src_to_dst[2]
             << " m10=" << src_to_dst[3]
             << " m11=" << src_to_dst[4]
             << " m12=" << src_to_dst[5]
             << " inv00=" << dst_to_src[0]
             << " inv01=" << dst_to_src[1]
             << " inv02=" << dst_to_src[2]
             << " inv10=" << dst_to_src[3]
             << " inv11=" << dst_to_src[4]
             << " inv12=" << dst_to_src[5]
             << endl;
    }
    return 0;
}
'''


def write_kernel(sample_dir: Path) -> None:
    (sample_dir / "cuda_affine_kernel.cu").write_text(CUDA_KERNEL, encoding="utf-8")


def patch_main(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "CUDA_AFFINE_FRAME" in text:
        print(f"already CUDA affine patched: {path}")
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
        "#include <cudaEGL.h>\n"
        "#include <cuda_runtime.h>\n",
        1,
    )
    marker = "static void\nabort(context_t *ctx)\n{"
    if marker not in text:
        raise RuntimeError(f"abort marker not found in {path}")
    text = text.replace(marker, HELPERS + "\n" + marker, 1)

    query_marker = "    NvBufSurf::NvCommonAllocateParams cParams = {0};\n"
    if "init_cuda_affine_scratch_fd_array();" not in text:
        text = text.replace(query_marker, query_marker + "\n    init_cuda_affine_scratch_fd_array();\n", 1)

    alloc_marker = """            ret = NvBufSurf::NvAllocate(&cParams, 1, &ctx->dmabuff_fd[index]);
            TEST_ERROR(ret < 0, "Failed to create buffers", error);
"""
    alloc_insert = alloc_marker + """            NvBufSurf::NvCommonAllocateParams scratchParams = cParams;
            scratchParams.layout = NVBUF_LAYOUT_PITCH;
            scratchParams.colorFormat = NVBUF_COLOR_FORMAT_NV12_ER;
            if (g_cuda_affine_input_scratch_fd[index] != -1)
            {
                NvBufSurf::NvDestroy(g_cuda_affine_input_scratch_fd[index]);
                g_cuda_affine_input_scratch_fd[index] = -1;
            }
            if (g_cuda_affine_output_scratch_fd[index] != -1)
            {
                NvBufSurf::NvDestroy(g_cuda_affine_output_scratch_fd[index]);
                g_cuda_affine_output_scratch_fd[index] = -1;
            }
            ret = NvBufSurf::NvAllocate(&scratchParams, 1, &g_cuda_affine_input_scratch_fd[index]);
            TEST_ERROR(ret < 0, "Failed to create CUDA affine input scratch buffers", error);
            ret = NvBufSurf::NvAllocate(&scratchParams, 1, &g_cuda_affine_output_scratch_fd[index]);
            TEST_ERROR(ret < 0, "Failed to create CUDA affine output scratch buffers", error);
"""
    if "g_cuda_affine_input_scratch_fd[index]" not in text:
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

            if (g_cuda_affine_input_scratch_fd[v4l2_buf.index] < 0 || g_cuda_affine_output_scratch_fd[v4l2_buf.index] < 0)
            {
                abort(ctx);
                cerr << "CUDA affine scratch buffers are not allocated" << endl;
                break;
            }
            auto cuda_affine_stage_t0 = std::chrono::high_resolution_clock::now();
            ret = cuda_affine_transform_fd(ctx->dmabuff_fd[v4l2_buf.index],
                                           g_cuda_affine_input_scratch_fd[v4l2_buf.index],
                                           ctx->width, ctx->height);
            auto cuda_affine_stage_t1 = std::chrono::high_resolution_clock::now();
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while transforming main DMABUF to CUDA affine input scratch" << endl;
                break;
            }
            NvBufSurface *input_scratch_surf = 0;
            ret = NvBufSurfaceFromFd(g_cuda_affine_input_scratch_fd[v4l2_buf.index], (void**)(&input_scratch_surf));
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while calling NvBufSurfaceFromFd for CUDA affine input scratch" << endl;
                break;
            }
            NvBufSurface *output_scratch_surf = 0;
            ret = NvBufSurfaceFromFd(g_cuda_affine_output_scratch_fd[v4l2_buf.index], (void**)(&output_scratch_surf));
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while calling NvBufSurfaceFromFd for CUDA affine output scratch" << endl;
                break;
            }
            if (input_scratch_surf->surfaceList[0].mappedAddr.eglImage == NULL)
            {
                if (NvBufSurfaceMapEglImage(input_scratch_surf, 0) != 0)
                {
                    abort(ctx);
                    cerr << "Unable to map CUDA affine input scratch fd to EGLImage" << endl;
                    break;
                }
            }
            if (output_scratch_surf->surfaceList[0].mappedAddr.eglImage == NULL)
            {
                if (NvBufSurfaceMapEglImage(output_scratch_surf, 0) != 0)
                {
                    abort(ctx);
                    cerr << "Unable to map CUDA affine output scratch fd to EGLImage" << endl;
                    break;
                }
            }
            auto cuda_affine_stage_t2 = std::chrono::high_resolution_clock::now();
            ret = cuda_affine_process_egl_images(input_scratch_surf->surfaceList[0].mappedAddr.eglImage,
                                                 output_scratch_surf->surfaceList[0].mappedAddr.eglImage,
                                                 ctx->width, ctx->height);
            auto cuda_affine_stage_t3 = std::chrono::high_resolution_clock::now();
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while CUDA affine processing on EGLImage scratch buffers" << endl;
                break;
            }
            if (NvBufSurfaceSyncForDevice(output_scratch_surf, 0, -1) != 0)
            {
                abort(ctx);
                cerr << "Unable to sync CUDA affine output scratch for NvBufSurfTransform" << endl;
                break;
            }
            if (NvBufSurfaceUnMapEglImage(input_scratch_surf, 0) != 0)
            {
                abort(ctx);
                cerr << "Unable to unmap CUDA affine input scratch EGLImage" << endl;
                break;
            }
            if (NvBufSurfaceUnMapEglImage(output_scratch_surf, 0) != 0)
            {
                abort(ctx);
                cerr << "Unable to unmap CUDA affine output scratch EGLImage" << endl;
                break;
            }
            auto cuda_affine_stage_t4 = std::chrono::high_resolution_clock::now();
            ret = cuda_affine_transform_fd(g_cuda_affine_output_scratch_fd[v4l2_buf.index],
                                           ctx->dmabuff_fd[v4l2_buf.index],
                                           ctx->width, ctx->height);
            auto cuda_affine_stage_t5 = std::chrono::high_resolution_clock::now();
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while transforming CUDA affine output scratch back to main DMABUF" << endl;
                break;
            }
            static int cuda_affine_stage_frame = 0;
            static double cuda_affine_stage_total_ms = 0.0;
            cuda_affine_stage_frame++;
            double input_transform_ms = std::chrono::duration<double, std::milli>(cuda_affine_stage_t1 - cuda_affine_stage_t0).count();
            double cuda_call_ms = std::chrono::duration<double, std::milli>(cuda_affine_stage_t3 - cuda_affine_stage_t2).count();
            double output_transform_ms = std::chrono::duration<double, std::milli>(cuda_affine_stage_t5 - cuda_affine_stage_t4).count();
            double total_stage_ms = std::chrono::duration<double, std::milli>(cuda_affine_stage_t5 - cuda_affine_stage_t0).count();
            cuda_affine_stage_total_ms += total_stage_ms;
            if (cuda_affine_stage_frame <= 5 || cuda_affine_stage_frame % 100 == 0)
            {
                cerr << "CUDA_AFFINE_STAGE_TIMING frame=" << cuda_affine_stage_frame
                     << " input_transform_ms=" << input_transform_ms
                     << " cuda_call_ms=" << cuda_call_ms
                     << " output_transform_ms=" << output_transform_ms
                     << " total_stage_ms=" << total_stage_ms
                     << " avg_total_stage_ms=" << (cuda_affine_stage_total_ms / cuda_affine_stage_frame)
                     << endl;
            }

            if (ctx->enc_output_memory_type == V4L2_MEMORY_DMABUF)
"""
    if "CUDA affine scratch buffers are not allocated" not in text:
        if insert_marker not in text:
            raise RuntimeError("NvBufSurfaceFromFd insertion block not found")
        text = text.replace(insert_marker, insert_replacement, 1)

    path.write_text(text, encoding="utf-8")


def patch_makefile(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "cuda_affine_kernel.o" not in text:
        text = text.replace(
            "OBJS := $(SRCS:.cpp=.o)\n",
            "OBJS := $(SRCS:.cpp=.o) cuda_affine_kernel.o\n",
            1,
        )
        text = text.replace(
            "%.o: %.cpp\n\t@echo \"Compiling: $<\"\n\t$(CPP) $(CPPFLAGS) -c $<\n",
            "%.o: %.cpp\n\t@echo \"Compiling: $<\"\n\t$(CPP) $(CPPFLAGS) -c $<\n\n"
            "cuda_affine_kernel.o: cuda_affine_kernel.cu\n"
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
    parser = argparse.ArgumentParser(
        description="Patch MMAPI transcode sample with a custom CUDA affine kernel diagnostic."
    )
    parser.add_argument("--sample-dir", type=Path, required=True)
    args = parser.parse_args()
    write_kernel(args.sample_dir)
    patch_main(args.sample_dir / "multivideo_transcode_main.cpp")
    patch_makefile(args.sample_dir / "Makefile")
    print(f"patched CUDA affine diagnostic transcode: {args.sample_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
