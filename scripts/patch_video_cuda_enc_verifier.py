from __future__ import annotations

import argparse
from pathlib import Path


LOCAL_NVANALYSIS_CU = r'''/*
 * Local verifier override for Jetson Multimedia API 03_video_cuda_enc.
 * Based on the sample's NvAnalysis.cu shape, but scoped to this project copy.
 */

#include <cuda.h>
#include <cuda_runtime.h>
#include <cstdlib>
#include <cstring>
#include "NvAnalysis.h"

#define TILE_W 16
#define TILE_H 16

__global__ void markerKernel(unsigned char *base, int pitch)
{
    int y = blockIdx.y * blockDim.y + threadIdx.y + 32;
    int x = blockIdx.x * blockDim.x + threadIdx.x + 32;
    base[y * pitch + x] = 0;
}

__global__ void translateKernel(const unsigned char *src, size_t srcPitch, unsigned char *dst, int dstPitch, int width, int height, int dx, int dy)
{
    int y = blockIdx.y * blockDim.y + threadIdx.y;
    int x = blockIdx.x * blockDim.x + threadIdx.x;
    if (x >= width || y >= height)
        return;

    int sx = x - dx;
    int sy = y - dy;
    unsigned char value = 0;
    if (sx >= 0 && sx < width && sy >= 0 && sy < height)
        value = src[sy * srcPitch + sx];
    dst[y * dstPitch + x] = value;
}

__global__ void affineKernel(const unsigned char *src, size_t srcPitch, unsigned char *dst, int dstPitch, int width, int height, float a00, float a01, float a02, float a10, float a11, float a12)
{
    int y = blockIdx.y * blockDim.y + threadIdx.y;
    int x = blockIdx.x * blockDim.x + threadIdx.x;
    if (x >= width || y >= height)
        return;

    float sx_f = a00 * x + a01 * y + a02;
    float sy_f = a10 * x + a11 * y + a12;
    int sx = (int)(sx_f + 0.5f);
    int sy = (int)(sy_f + 0.5f);
    unsigned char value = 0;
    if (sx >= 0 && sx < width && sy >= 0 && sy < height)
        value = src[sy * srcPitch + sx];
    dst[y * dstPitch + x] = value;
}

static unsigned char *copyYToTemporary(unsigned char *base, int pitch, size_t *tmpPitch)
{
    unsigned char *tmp = NULL;
    cudaError_t err = cudaMallocPitch((void **)&tmp, tmpPitch, 640, 360);
    if (err != cudaSuccess)
        return NULL;
    err = cudaMemcpy2D(tmp, *tmpPitch, base, pitch, 640, 360, cudaMemcpyDeviceToDevice);
    if (err != cudaSuccess)
    {
        cudaFree(tmp);
        return NULL;
    }
    return tmp;
}

int addLabels(CUdeviceptr pDevPtr, int pitch)
{
    unsigned char *base = (unsigned char *)pDevPtr;
    const char *mode = getenv("CUDA_VERIFIER_MODE");
    if (!mode)
        mode = "marker";

    if (!strcmp(mode, "translate"))
    {
        int dx = getenv("CUDA_VERIFIER_DX") ? atoi(getenv("CUDA_VERIFIER_DX")) : 8;
        int dy = getenv("CUDA_VERIFIER_DY") ? atoi(getenv("CUDA_VERIFIER_DY")) : 0;
        size_t tmpPitch = 0;
        unsigned char *tmp = copyYToTemporary(base, pitch, &tmpPitch);
        if (!tmp)
            return -1;
        dim3 threads(TILE_W, TILE_H);
        dim3 blocks((640 + TILE_W - 1) / TILE_W, (360 + TILE_H - 1) / TILE_H);
        translateKernel<<<blocks, threads>>>(tmp, tmpPitch, base, pitch, 640, 360, dx, dy);
        cudaDeviceSynchronize();
        cudaFree(tmp);
        return 0;
    }

    if (!strcmp(mode, "affine"))
    {
        float dx = getenv("CUDA_VERIFIER_DX") ? (float)atof(getenv("CUDA_VERIFIER_DX")) : 8.0f;
        float dy = getenv("CUDA_VERIFIER_DY") ? (float)atof(getenv("CUDA_VERIFIER_DY")) : 0.0f;
        size_t tmpPitch = 0;
        unsigned char *tmp = copyYToTemporary(base, pitch, &tmpPitch);
        if (!tmp)
            return -1;
        dim3 threads(TILE_W, TILE_H);
        dim3 blocks((640 + TILE_W - 1) / TILE_W, (360 + TILE_H - 1) / TILE_H);
        affineKernel<<<blocks, threads>>>(tmp, tmpPitch, base, pitch, 640, 360, 1.0f, 0.0f, -dx, 0.0f, 1.0f, -dy);
        cudaDeviceSynchronize();
        cudaFree(tmp);
        return 0;
    }

    dim3 threads(32, 32);
    dim3 blocks(1, 1);
    markerKernel<<<blocks, threads>>>(base, pitch);
    return 0;
}

__global__ void convertIntToFloatKernelRGB(CUdeviceptr pDevPtr, int width, int height,
                void* cuda_buf, int pitch, void* offsets_gpu, void* scales_gpu)
{
    float *pdata = (float *)cuda_buf;
    char *psrcdata = (char *)pDevPtr;
    int *offsets = (int *)offsets_gpu;
    float *scales = (float *)scales_gpu;
    int row = blockIdx.y * blockDim.y + threadIdx.y;
    int col = blockIdx.x * blockDim.x + threadIdx.x;
    if (col < width && row < height)
    {
        for (int k = 0; k < 3; k++)
        {
            pdata[width * height * k + row * width + col] =
                (float)(*(psrcdata + row * pitch + col * 4 + (3 - 1 - k)) - offsets[k]) * scales[k];
        }
    }
}

__global__ void convertIntToFloatKernelBGR(CUdeviceptr pDevPtr, int width, int height,
                void* cuda_buf, int pitch, void* offsets_gpu, void* scales_gpu)
{
    float *pdata = (float *)cuda_buf;
    char *psrcdata = (char *)pDevPtr;
    int *offsets = (int *)offsets_gpu;
    float *scales = (float *)scales_gpu;
    int row = blockIdx.y * blockDim.y + threadIdx.y;
    int col = blockIdx.x * blockDim.x + threadIdx.x;
    if (col < width && row < height)
    {
        for (int k = 0; k < 3; k++)
        {
            pdata[width * height * k + row * width + col] =
                (float)(*(psrcdata + row * pitch + col * 4 + k) - offsets[k]) * scales[k];
        }
    }
}

int convertIntToFloat(CUdeviceptr pDevPtr,
                      int width,
                      int height,
                      int pitch,
                      COLOR_FORMAT color_format,
                      void* offsets,
                      void* scales,
                      void* cuda_buf, void* pstream)
{
    dim3 threadsPerBlock(32, 32);
    dim3 blocks((width + threadsPerBlock.x - 1) / threadsPerBlock.x, (height +
          threadsPerBlock.y - 1) / threadsPerBlock.y);
    cudaStream_t stream;
    if (pstream!= NULL)
        stream = *(cudaStream_t*)pstream;
    else
        stream = 0;
    if (color_format == COLOR_FORMAT_RGB)
    {
        convertIntToFloatKernelRGB<<<blocks, threadsPerBlock, 0, stream>>>(pDevPtr, width,
                height, cuda_buf, pitch, offsets, scales);
    }
    else if (color_format == COLOR_FORMAT_BGR)
    {
        convertIntToFloatKernelBGR<<<blocks, threadsPerBlock, 0, stream>>>(pDevPtr, width,
                height, cuda_buf, pitch, offsets, scales);
    }
    return 0;
}
'''


def main() -> int:
    parser = argparse.ArgumentParser(description="Patch a copied 03_video_cuda_enc sample into a local CUDA verifier.")
    parser.add_argument("sample_dir", type=Path)
    args = parser.parse_args()
    sample_dir = args.sample_dir
    makefile = sample_dir / "Makefile"
    analysis = sample_dir / "NvAnalysis.cu"
    if not makefile.exists() or not analysis.exists():
        raise FileNotFoundError("sample_dir must contain Makefile and NvAnalysis.cu")

    text = makefile.read_text(encoding="utf-8")
    text = text.replace("$(ALGO_CUDA_DIR)/NvAnalysis.o", "NvAnalysis.o")
    text = text.replace("$(ALGO_CUDA_DIR)NvAnalysis.o", "NvAnalysis.o")
    if "NvAnalysis.o : NvAnalysis.cu" not in text:
        marker = "$(ALGO_CUDA_DIR)/%.o: $(ALGO_CUDA_DIR)/%.cu\n\t$(AT)$(MAKE) -C $(ALGO_CUDA_DIR)\n"
        replacement = marker + "\nNvAnalysis.o : NvAnalysis.cu\n\t@echo \"Compiling: $<\"\n\t$(NVCC) --shared -I$(ALGO_CUDA_DIR) -Xcompiler -fPIC -gencode arch=compute_87,code=sm_87 -o $@ -c $<\n"
        text = text.replace(marker, replacement)
    makefile.write_text(text, encoding="utf-8")
    analysis.write_text(LOCAL_NVANALYSIS_CU, encoding="utf-8")
    print(f"patched verifier sample: {sample_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
