from __future__ import annotations

import argparse
from pathlib import Path


VPI_INSERT = r'''
struct VpiMatrix3x3
{
    float m[3][3];
};

static bool g_vpi_matrices_loaded = false;
static std::vector<VpiMatrix3x3> g_vpi_matrices;

static void
load_vpi_matrices_once()
{
    if (g_vpi_matrices_loaded)
    {
        return;
    }
    g_vpi_matrices_loaded = true;
    const char *path = getenv("VPI_MATRIX_CSV");
    if (path == NULL || path[0] == '\0')
    {
        return;
    }
    std::ifstream file(path);
    if (!file.is_open())
    {
        cerr << "VPI matrix CSV could not be opened: " << path << endl;
        return;
    }
    std::string line;
    std::getline(file, line); // header
    while (std::getline(file, line))
    {
        std::stringstream ss(line);
        std::string cell;
        std::vector<std::string> cells;
        while (std::getline(ss, cell, ','))
        {
            cells.push_back(cell);
        }
        if (cells.size() < 10)
        {
            continue;
        }
        VpiMatrix3x3 mat = {};
        mat.m[0][0] = std::stof(cells[1]);
        mat.m[0][1] = std::stof(cells[2]);
        mat.m[0][2] = std::stof(cells[3]);
        mat.m[1][0] = std::stof(cells[4]);
        mat.m[1][1] = std::stof(cells[5]);
        mat.m[1][2] = std::stof(cells[6]);
        mat.m[2][0] = std::stof(cells[7]);
        mat.m[2][1] = std::stof(cells[8]);
        mat.m[2][2] = std::stof(cells[9]);
        g_vpi_matrices.push_back(mat);
    }
    cerr << "VPI_MATRIX_LOADED path=" << path << " count=" << g_vpi_matrices.size() << endl;
}

static int
vpi_warp_egl_image(EGLImageKHR image)
{
    CUresult cu_status;
    CUeglFrame eglFrame;
    CUgraphicsResource resource = NULL;
    cudaFree(0);
    cu_status = cuGraphicsEGLRegisterImage(&resource, image, CU_GRAPHICS_MAP_RESOURCE_FLAGS_NONE);
    if (cu_status != CUDA_SUCCESS)
    {
        cerr << "cuGraphicsEGLRegisterImage failed for VPI path: " << cu_status << endl;
        return -1;
    }
    cu_status = cuGraphicsResourceGetMappedEglFrame(&eglFrame, resource, 0, 0);
    if (cu_status != CUDA_SUCCESS)
    {
        cerr << "cuGraphicsResourceGetMappedEglFrame failed: " << cu_status << endl;
        cuGraphicsUnregisterResource(resource);
        return -1;
    }
    if (eglFrame.frameType != CU_EGL_FRAME_TYPE_PITCH)
    {
        cerr << "Unsupported EGL frame type for VPI path: " << eglFrame.frameType << endl;
        cuGraphicsUnregisterResource(resource);
        return -1;
    }
    static bool printed_egl_info = false;
    if (!printed_egl_info)
    {
        cerr << "VPI_EGL_INFO width=" << eglFrame.width
             << " height=" << eglFrame.height
             << " pitch=" << eglFrame.pitch
             << " planeCount=" << eglFrame.planeCount
             << " numChannels=" << eglFrame.numChannels
             << " frameType=" << eglFrame.frameType
             << " eglColorFormat=" << eglFrame.eglColorFormat
             << " cuFormat=" << eglFrame.cuFormat << endl;
        printed_egl_info = true;
    }

    VPIImageData input_data;
    memset(&input_data, 0, sizeof(input_data));
    input_data.bufferType = VPI_IMAGE_BUFFER_CUDA_PITCH_LINEAR;
    bool is_nv12_semiplanar = (eglFrame.planeCount == 2 &&
                               (eglFrame.eglColorFormat == CU_EGL_COLOR_FORMAT_YUV420_SEMIPLANAR ||
                                eglFrame.eglColorFormat == CU_EGL_COLOR_FORMAT_YUV420_SEMIPLANAR_ER ||
                                eglFrame.eglColorFormat == CU_EGL_COLOR_FORMAT_YUV420_SEMIPLANAR_709));
    input_data.buffer.pitch.format = is_nv12_semiplanar ? VPI_IMAGE_FORMAT_NV12_ER : VPI_IMAGE_FORMAT_Y8_ER;
    input_data.buffer.pitch.numPlanes = is_nv12_semiplanar ? 2 : 1;
    input_data.buffer.pitch.planes[0].data = (void *)eglFrame.frame.pPitch[0];
    input_data.buffer.pitch.planes[0].width = eglFrame.width;
    input_data.buffer.pitch.planes[0].height = eglFrame.height;
    input_data.buffer.pitch.planes[0].pitchBytes = eglFrame.pitch;
    if (is_nv12_semiplanar)
    {
        input_data.buffer.pitch.planes[1].data = (void *)eglFrame.frame.pPitch[1];
        input_data.buffer.pitch.planes[1].width = eglFrame.width / 2;
        input_data.buffer.pitch.planes[1].height = eglFrame.height / 2;
        input_data.buffer.pitch.planes[1].pitchBytes = eglFrame.pitch;
    }

    unsigned char *scratch_dev = NULL;
    unsigned char *scratch_uv_dev = NULL;
    size_t scratch_pitch = 0;
    cudaError_t cuda_status = cudaMallocPitch((void **)&scratch_dev, &scratch_pitch, eglFrame.width, eglFrame.height);
    if (cuda_status != cudaSuccess)
    {
        cerr << "cudaMallocPitch scratch failed: " << cudaGetErrorString(cuda_status) << endl;
        cuGraphicsUnregisterResource(resource);
        return -1;
    }
    size_t scratch_uv_pitch = 0;
    if (is_nv12_semiplanar)
    {
        cuda_status = cudaMallocPitch((void **)&scratch_uv_dev, &scratch_uv_pitch, eglFrame.width, eglFrame.height / 2);
        if (cuda_status != cudaSuccess)
        {
            cerr << "cudaMallocPitch scratch UV failed: " << cudaGetErrorString(cuda_status) << endl;
            cudaFree(scratch_dev);
            cuGraphicsUnregisterResource(resource);
            return -1;
        }
    }

    VPIImage input = NULL;
    VPIImage output = NULL;
    VPIStream stream = NULL;
    VPIImageData output_data = input_data;
    output_data.buffer.pitch.planes[0].data = scratch_dev;
    output_data.buffer.pitch.planes[0].pitchBytes = scratch_pitch;
    if (is_nv12_semiplanar)
    {
        output_data.buffer.pitch.planes[1].data = scratch_uv_dev;
        output_data.buffer.pitch.planes[1].pitchBytes = scratch_uv_pitch;
    }
    VPIStatus status = VPI_SUCCESS;
    static int frame_count = 0;
    int current_frame = frame_count + 1;
    load_vpi_matrices_once();
    VPIPerspectiveTransform xform = {1.0f, 0.002f, 1.0f, -0.002f, 1.0f, -1.0f, 0.0f, 0.0f, 1.0f};
    if (!g_vpi_matrices.empty())
    {
        size_t matrix_index = static_cast<size_t>(current_frame - 1);
        if (matrix_index < g_vpi_matrices.size())
        {
            memcpy(xform, g_vpi_matrices[matrix_index].m, sizeof(xform));
        }
        else
        {
            xform[0][0] = 1.0f;
            xform[0][1] = 0.0f;
            xform[0][2] = 0.0f;
            xform[1][0] = 0.0f;
            xform[1][1] = 1.0f;
            xform[1][2] = 0.0f;
            xform[2][0] = 0.0f;
            xform[2][1] = 0.0f;
            xform[2][2] = 1.0f;
            if (current_frame <= 5 || current_frame % 100 == 0)
            {
                cerr << "VPI_MATRIX_FALLBACK_IDENTITY frame=" << current_frame << endl;
            }
        }
    }

    status = vpiStreamCreate(VPI_BACKEND_CUDA, &stream);
    if (status != VPI_SUCCESS) goto vpi_fail;
    status = vpiImageCreateWrapper(&input_data, NULL, VPI_BACKEND_CUDA, &input);
    if (status != VPI_SUCCESS) goto vpi_fail;
    status = vpiImageCreateWrapper(&output_data, NULL, VPI_BACKEND_CUDA, &output);
    if (status != VPI_SUCCESS) goto vpi_fail;

    {
        auto t0 = std::chrono::high_resolution_clock::now();
        status = vpiSubmitPerspectiveWarp(stream, VPI_BACKEND_CUDA, input, xform, output, NULL,
                                          VPI_INTERP_LINEAR, VPI_BORDER_ZERO, 0);
        if (status != VPI_SUCCESS) goto vpi_fail;
        status = vpiStreamSync(stream);
        if (status != VPI_SUCCESS) goto vpi_fail;
        cuda_status = cudaMemcpy2D((void *)eglFrame.frame.pPitch[0], eglFrame.pitch,
                                   scratch_dev, scratch_pitch,
                                   eglFrame.width, eglFrame.height,
                                   cudaMemcpyDeviceToDevice);
        if (cuda_status != cudaSuccess)
        {
            cerr << "cudaMemcpy2D scratch back failed: " << cudaGetErrorString(cuda_status) << endl;
            goto vpi_fail;
        }
        if (is_nv12_semiplanar)
        {
            cuda_status = cudaMemcpy2D((void *)eglFrame.frame.pPitch[1], eglFrame.pitch,
                                       scratch_uv_dev, scratch_uv_pitch,
                                       eglFrame.width, eglFrame.height / 2,
                                       cudaMemcpyDeviceToDevice);
            if (cuda_status != cudaSuccess)
            {
                cerr << "cudaMemcpy2D scratch UV back failed: " << cudaGetErrorString(cuda_status) << endl;
                goto vpi_fail;
            }
        }
        auto t1 = std::chrono::high_resolution_clock::now();
        static double total_ms = 0.0;
        double elapsed_ms = std::chrono::duration<double, std::milli>(t1 - t0).count();
        frame_count++;
        total_ms += elapsed_ms;
        if (frame_count <= 5 || frame_count % 100 == 0)
        {
            cerr << "VPI_ENC_WARP frame=" << frame_count << " elapsed_ms=" << elapsed_ms
                 << " avg_ms=" << (total_ms / frame_count) << endl;
        }
    }

    vpiImageDestroy(output);
    vpiImageDestroy(input);
    vpiStreamDestroy(stream);
    if (scratch_uv_dev) cudaFree(scratch_uv_dev);
    cudaFree(scratch_dev);
    cuGraphicsUnregisterResource(resource);
    return 0;

vpi_fail:
    char msg[VPI_MAX_STATUS_MESSAGE_LENGTH];
    vpiGetLastStatusMessage(msg, sizeof(msg));
    cerr << "VPI encode warp failed status=" << status << " msg=" << msg << endl;
    if (output) vpiImageDestroy(output);
    if (input) vpiImageDestroy(input);
    if (stream) vpiStreamDestroy(stream);
    if (scratch_uv_dev) cudaFree(scratch_uv_dev);
    if (scratch_dev) cudaFree(scratch_dev);
    cuGraphicsUnregisterResource(resource);
    return -1;
}
'''


def patch_main(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "VPI_ENC_WARP" in text:
        return
    text = text.replace(
        '#include "video_cuda_enc.h"\n',
        '#include "video_cuda_enc.h"\n'
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
    marker = "static int\nrender_rect(context_t *ctx, NvBuffer *buffer)\n{"
    if marker not in text:
        raise RuntimeError(f"render_rect marker not found in {path}")
    text = text.replace(marker, VPI_INSERT + "\n" + marker, 1)
    old = (
        "    /* Map EGLImage to CUDA buffer, and call CUDA kernel to\n"
        "       draw a 32x32 pixels black box on left-top of each frame */\n"
        "    HandleEGLImage(&ctx->eglimg);"
    )
    new = (
        "    /* Map EGLImage to a VPI CUDA wrapper and run a minimal perspective warp. */\n"
        "    ret = vpi_warp_egl_image(ctx->eglimg);\n"
        "    if (ret < 0)\n"
        "    {\n"
        '        cerr << "Error while VPI warp on encoder input buffer" << endl;\n'
        "        return -1;\n"
        "    }"
    )
    if old not in text:
        raise RuntimeError("HandleEGLImage call block not found")
    text = text.replace(old, new, 1)
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
    parser = argparse.ArgumentParser(description="Patch copied MMAPI 03_video_cuda_enc sample to run VPI CUDA warp on encoder input buffer.")
    parser.add_argument("--sample-dir", type=Path, required=True)
    args = parser.parse_args()
    patch_main(args.sample_dir / "video_cuda_enc_main.cpp")
    patch_makefile(args.sample_dir / "Makefile")
    print(f"patched: {args.sample_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
