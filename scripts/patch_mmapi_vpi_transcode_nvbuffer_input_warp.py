from __future__ import annotations

import argparse
from pathlib import Path

from patch_mmapi_vpi_transcode_eglimage_warp import HELPERS


def patch_main(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "VPI_NVBUFFER_INPUT_WARP" in text:
        print(f"already patched: {path}")
        return

    helper = HELPERS.replace("VPI_EGLIMAGE_WARP", "VPI_NVBUFFER_INPUT_WARP")
    text = text.replace(
        '#include "NvUtils.h"\n#include "multivideo_transcode.h"\n',
        '#include "NvUtils.h"\n#include "multivideo_transcode.h"\n'
        "#include <chrono>\n"
        "#include <cstdlib>\n"
        "#include <fstream>\n"
        "#include <sstream>\n"
        "#include <string>\n"
        "#include <vector>\n"
        "#include <vpi/Image.h>\n"
        "#include <vpi/Status.h>\n"
        "#include <vpi/Stream.h>\n"
        "#include <vpi/algo/PerspectiveWarp.h>\n",
    )
    marker = "static void\nabort(context_t *ctx)\n{"
    if marker not in text:
        raise RuntimeError(f"abort marker not found in {path}")
    text = text.replace(marker, helper + "\n" + marker, 1)

    query_marker = "    NvBufSurf::NvCommonAllocateParams cParams = {0};\n"
    if "init_vpi_scratch_fd_array();" not in text:
        text = text.replace(query_marker, query_marker + "\n    init_vpi_scratch_fd_array();\n", 1)

    alloc_marker = """            ret = NvBufSurf::NvAllocate(&cParams, 1, &ctx->dmabuff_fd[index]);
            TEST_ERROR(ret < 0, "Failed to create buffers", error);
"""
    alloc_insert = alloc_marker + """            NvBufSurf::NvCommonAllocateParams scratchParams = cParams;
            scratchParams.layout = NVBUF_LAYOUT_PITCH;
            scratchParams.colorFormat = NVBUF_COLOR_FORMAT_NV12_ER;
            if (g_vpi_output_scratch_fd[index] != -1)
            {
                NvBufSurf::NvDestroy(g_vpi_output_scratch_fd[index]);
                g_vpi_output_scratch_fd[index] = -1;
            }
            ret = NvBufSurf::NvAllocate(&scratchParams, 1, &g_vpi_output_scratch_fd[index]);
            TEST_ERROR(ret < 0, "Failed to create VPI output scratch buffers", error);
"""
    if "g_vpi_output_scratch_fd[index]" not in text:
        if alloc_marker not in text:
            raise RuntimeError("dmabuf allocation marker not found")
        text = text.replace(alloc_marker, alloc_insert, 1)

    # Add a direct-NvBuffer wrapper helper after the EGLImage helper. It wraps
    # the decoder/encoder DMABUF fd as VPI_IMAGE_BUFFER_NVBUFFER and writes to an
    # EGLImage output scratch. This intentionally tests only input-transform
    # removal first.
    direct_helper = r'''
static int
vpi_warp_nvbuffer_to_eglimage(int input_fd, EGLImageKHR output_egl)
{
    VPIImage input = NULL;
    VPIImage output = NULL;
    VPIStream stream = NULL;
    VPIStatus status = VPI_SUCCESS;
    static int frame_count = 0;
    int current_frame = frame_count + 1;

    VPIImageData input_data;
    memset(&input_data, 0, sizeof(input_data));
    input_data.bufferType = VPI_IMAGE_BUFFER_NVBUFFER;
    input_data.buffer.fd = input_fd;

    VPIImageData output_data;
    memset(&output_data, 0, sizeof(output_data));
    output_data.bufferType = VPI_IMAGE_BUFFER_EGLIMAGE;
    output_data.buffer.egl = output_egl;

    load_vpi_matrices_once();
    VPIPerspectiveTransform xform = {1.0f, 0.002f, 1.0f, -0.002f, 1.0f, -1.0f, 0.0f, 0.0f, 1.0f};
    bool matrix_fallback = false;
    long matrix_index_log = -1;
    auto matrix_t0 = std::chrono::high_resolution_clock::now();
    if (!g_vpi_matrices.empty())
    {
        size_t matrix_index = static_cast<size_t>(current_frame - 1);
        matrix_index_log = static_cast<long>(matrix_index);
        if (matrix_index < g_vpi_matrices.size())
        {
            memcpy(xform, g_vpi_matrices[matrix_index].m, sizeof(xform));
        }
        else
        {
            matrix_fallback = true;
        }
    }
    if (matrix_fallback)
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
    }
    auto matrix_t1 = std::chrono::high_resolution_clock::now();
    double matrix_elapsed_us = std::chrono::duration<double, std::micro>(matrix_t1 - matrix_t0).count();
    if (current_frame <= 5 || current_frame % 30 == 0 || matrix_fallback)
    {
        cerr << "MATRIX_HANDOFF frame=" << current_frame
             << " matrix_index=" << matrix_index_log
             << " fallback=" << (matrix_fallback ? 1 : 0)
             << " elapsed_us=" << matrix_elapsed_us << endl;
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
        auto t1 = std::chrono::high_resolution_clock::now();
        static double total_ms = 0.0;
        double elapsed_ms = std::chrono::duration<double, std::milli>(t1 - t0).count();
        frame_count++;
        total_ms += elapsed_ms;
        if (frame_count <= 5 || frame_count % 100 == 0)
        {
            cerr << "VPI_NVBUFFER_INPUT_WARP frame=" << frame_count << " elapsed_ms=" << elapsed_ms
                 << " avg_ms=" << (total_ms / frame_count) << endl;
        }
    }

    vpiImageDestroy(output);
    vpiImageDestroy(input);
    vpiStreamDestroy(stream);
    return 0;

vpi_fail:
    char msg[VPI_MAX_STATUS_MESSAGE_LENGTH];
    vpiGetLastStatusMessage(msg, sizeof(msg));
    cerr << "VPI NvBuffer input warp failed status=" << status << " msg=" << msg << endl;
    if (output) vpiImageDestroy(output);
    if (input) vpiImageDestroy(input);
    if (stream) vpiStreamDestroy(stream);
    return -1;
}
'''
    if "vpi_warp_nvbuffer_to_eglimage" not in text:
        text = text.replace(marker, direct_helper + "\n" + marker, 1)

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

            if (g_vpi_output_scratch_fd[v4l2_buf.index] < 0)
            {
                abort(ctx);
                cerr << "VPI NvBuffer-input output scratch buffer is not allocated" << endl;
                break;
            }
            NvBufSurface *output_scratch_surf = 0;
            ret = NvBufSurfaceFromFd(g_vpi_output_scratch_fd[v4l2_buf.index], (void**)(&output_scratch_surf));
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while calling NvBufSurfaceFromFd for VPI output scratch" << endl;
                break;
            }
            auto nvbuf_stage_t0 = std::chrono::high_resolution_clock::now();
            if (output_scratch_surf->surfaceList[0].mappedAddr.eglImage == NULL)
            {
                if (NvBufSurfaceMapEglImage(output_scratch_surf, 0) != 0)
                {
                    abort(ctx);
                    cerr << "Unable to map VPI output scratch fd to EGLImage" << endl;
                    break;
                }
            }
            auto nvbuf_stage_t1 = std::chrono::high_resolution_clock::now();
            ret = vpi_warp_nvbuffer_to_eglimage(ctx->dmabuff_fd[v4l2_buf.index],
                                                output_scratch_surf->surfaceList[0].mappedAddr.eglImage);
            auto nvbuf_stage_t2 = std::chrono::high_resolution_clock::now();
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while VPI warp from NvBuffer to EGLImage output scratch" << endl;
                break;
            }
            if (NvBufSurfaceUnMapEglImage(output_scratch_surf, 0) != 0)
            {
                abort(ctx);
                cerr << "Unable to unmap VPI output scratch EGLImage" << endl;
                break;
            }
            auto nvbuf_stage_t3 = std::chrono::high_resolution_clock::now();
            ret = vpi_transform_fd(g_vpi_output_scratch_fd[v4l2_buf.index], ctx->dmabuff_fd[v4l2_buf.index], ctx->width, ctx->height);
            auto nvbuf_stage_t4 = std::chrono::high_resolution_clock::now();
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while transforming VPI output scratch back to transcode DMABUF" << endl;
                break;
            }
            static int nvbuf_stage_frame = 0;
            static double nvbuf_stage_total_ms = 0.0;
            nvbuf_stage_frame++;
            double map_ms = std::chrono::duration<double, std::milli>(nvbuf_stage_t1 - nvbuf_stage_t0).count();
            double wrapper_call_ms = std::chrono::duration<double, std::milli>(nvbuf_stage_t2 - nvbuf_stage_t1).count();
            double output_transform_ms = std::chrono::duration<double, std::milli>(nvbuf_stage_t4 - nvbuf_stage_t3).count();
            double total_stage_ms = std::chrono::duration<double, std::milli>(nvbuf_stage_t4 - nvbuf_stage_t0).count();
            nvbuf_stage_total_ms += total_stage_ms;
            if (nvbuf_stage_frame <= 5 || nvbuf_stage_frame % 100 == 0)
            {
                cerr << "NVBUFFER_INPUT_STAGE_TIMING frame=" << nvbuf_stage_frame
                     << " map_ms=" << map_ms
                     << " wrapper_call_ms=" << wrapper_call_ms
                     << " output_transform_ms=" << output_transform_ms
                     << " total_stage_ms=" << total_stage_ms
                     << " avg_total_stage_ms=" << (nvbuf_stage_total_ms / nvbuf_stage_frame)
                     << endl;
            }

            if (ctx->enc_output_memory_type == V4L2_MEMORY_DMABUF)
"""
    if "VPI NvBuffer-input output scratch buffer is not allocated" not in text:
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
    parser = argparse.ArgumentParser(description="Patch MMAPI transcode sample to test VPI_IMAGE_BUFFER_NVBUFFER input wrapping.")
    parser.add_argument("--sample-dir", type=Path, required=True)
    args = parser.parse_args()
    patch_main(args.sample_dir / "multivideo_transcode_main.cpp")
    patch_makefile(args.sample_dir / "Makefile")
    print(f"patched NvBuffer-input transcode: {args.sample_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
