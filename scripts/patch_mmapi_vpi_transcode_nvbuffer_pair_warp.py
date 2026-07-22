from __future__ import annotations

import argparse
from pathlib import Path


HELPERS = r'''
struct VpiMatrix3x3
{
    float m[3][3];
};

static bool g_nvbuf_pair_matrices_loaded = false;
static std::vector<VpiMatrix3x3> g_nvbuf_pair_matrices;
static int g_nvbuf_pair_input_scratch_fd[MAX_BUFFERS];
static int g_nvbuf_pair_output_scratch_fd[MAX_BUFFERS];
static bool g_nvbuf_pair_scratch_fd_ready = false;

static void
init_nvbuf_pair_scratch_fd_array()
{
    if (!g_nvbuf_pair_scratch_fd_ready)
    {
        for (int i = 0; i < MAX_BUFFERS; ++i)
        {
            g_nvbuf_pair_input_scratch_fd[i] = -1;
            g_nvbuf_pair_output_scratch_fd[i] = -1;
        }
        g_nvbuf_pair_scratch_fd_ready = true;
    }
}

static void
load_nvbuf_pair_matrices_once()
{
    if (g_nvbuf_pair_matrices_loaded)
    {
        return;
    }
    g_nvbuf_pair_matrices_loaded = true;
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
    std::getline(file, line);
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
        g_nvbuf_pair_matrices.push_back(mat);
    }
    cerr << "VPI_MATRIX_LOADED path=" << path << " count=" << g_nvbuf_pair_matrices.size() << endl;
}

static int
nvbuf_pair_transform_fd(int src_fd, int dst_fd, uint32_t width, uint32_t height)
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
vpi_warp_nvbuffer_pair(int input_fd, int output_fd)
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
    output_data.bufferType = VPI_IMAGE_BUFFER_NVBUFFER;
    output_data.buffer.fd = output_fd;

    load_nvbuf_pair_matrices_once();
    VPIPerspectiveTransform xform = {1.0f, 0.002f, 1.0f, -0.002f, 1.0f, -1.0f, 0.0f, 0.0f, 1.0f};
    bool matrix_fallback = false;
    long matrix_index_log = -1;
    auto matrix_t0 = std::chrono::high_resolution_clock::now();
    if (!g_nvbuf_pair_matrices.empty())
    {
        size_t matrix_index = static_cast<size_t>(current_frame - 1);
        matrix_index_log = static_cast<long>(matrix_index);
        if (matrix_index < g_nvbuf_pair_matrices.size())
        {
            memcpy(xform, g_nvbuf_pair_matrices[matrix_index].m, sizeof(xform));
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
    if (current_frame <= 5 || current_frame % 100 == 0 || matrix_fallback)
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
            cerr << "VPI_NVBUFFER_PAIR_WARP frame=" << frame_count << " elapsed_ms=" << elapsed_ms
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
    cerr << "VPI NvBuffer pair warp failed status=" << status << " msg=" << msg << endl;
    if (output) vpiImageDestroy(output);
    if (input) vpiImageDestroy(input);
    if (stream) vpiStreamDestroy(stream);
    return -1;
}
'''


def patch_main(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "VPI_NVBUFFER_PAIR_WARP" in text:
        print(f"already patched: {path}")
        return

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
    text = text.replace(marker, HELPERS + "\n" + marker, 1)

    query_marker = "    NvBufSurf::NvCommonAllocateParams cParams = {0};\n"
    if "init_nvbuf_pair_scratch_fd_array();" not in text:
        text = text.replace(query_marker, query_marker + "\n    init_nvbuf_pair_scratch_fd_array();\n", 1)

    alloc_marker = """            ret = NvBufSurf::NvAllocate(&cParams, 1, &ctx->dmabuff_fd[index]);
            TEST_ERROR(ret < 0, "Failed to create buffers", error);
"""
    alloc_insert = alloc_marker + """            NvBufSurf::NvCommonAllocateParams scratchParams = cParams;
            scratchParams.layout = NVBUF_LAYOUT_PITCH;
            scratchParams.colorFormat = NVBUF_COLOR_FORMAT_NV12_ER;
            if (g_nvbuf_pair_input_scratch_fd[index] != -1)
            {
                NvBufSurf::NvDestroy(g_nvbuf_pair_input_scratch_fd[index]);
                g_nvbuf_pair_input_scratch_fd[index] = -1;
            }
            if (g_nvbuf_pair_output_scratch_fd[index] != -1)
            {
                NvBufSurf::NvDestroy(g_nvbuf_pair_output_scratch_fd[index]);
                g_nvbuf_pair_output_scratch_fd[index] = -1;
            }
            ret = NvBufSurf::NvAllocate(&scratchParams, 1, &g_nvbuf_pair_input_scratch_fd[index]);
            TEST_ERROR(ret < 0, "Failed to create VPI NvBuffer pair input scratch buffers", error);
            ret = NvBufSurf::NvAllocate(&scratchParams, 1, &g_nvbuf_pair_output_scratch_fd[index]);
            TEST_ERROR(ret < 0, "Failed to create VPI NvBuffer pair output scratch buffers", error);
"""
    if "g_nvbuf_pair_input_scratch_fd[index]" not in text:
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

            if (g_nvbuf_pair_input_scratch_fd[v4l2_buf.index] < 0 || g_nvbuf_pair_output_scratch_fd[v4l2_buf.index] < 0)
            {
                abort(ctx);
                cerr << "VPI NvBuffer pair scratch buffers are not allocated" << endl;
                break;
            }
            auto nvbuf_pair_stage_t0 = std::chrono::high_resolution_clock::now();
            ret = nvbuf_pair_transform_fd(ctx->dmabuff_fd[v4l2_buf.index], g_nvbuf_pair_input_scratch_fd[v4l2_buf.index], ctx->width, ctx->height);
            auto nvbuf_pair_stage_t1 = std::chrono::high_resolution_clock::now();
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while transforming main DMABUF to VPI NvBuffer input scratch" << endl;
                break;
            }
            ret = vpi_warp_nvbuffer_pair(g_nvbuf_pair_input_scratch_fd[v4l2_buf.index],
                                         g_nvbuf_pair_output_scratch_fd[v4l2_buf.index]);
            auto nvbuf_pair_stage_t2 = std::chrono::high_resolution_clock::now();
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while VPI warp on format-matched NvBuffer pair" << endl;
                break;
            }
            ret = nvbuf_pair_transform_fd(g_nvbuf_pair_output_scratch_fd[v4l2_buf.index], ctx->dmabuff_fd[v4l2_buf.index], ctx->width, ctx->height);
            auto nvbuf_pair_stage_t3 = std::chrono::high_resolution_clock::now();
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while transforming VPI NvBuffer output scratch to main DMABUF" << endl;
                break;
            }
            static int nvbuf_pair_stage_frame = 0;
            static double nvbuf_pair_stage_total_ms = 0.0;
            nvbuf_pair_stage_frame++;
            double input_transform_ms = std::chrono::duration<double, std::milli>(nvbuf_pair_stage_t1 - nvbuf_pair_stage_t0).count();
            double wrapper_call_ms = std::chrono::duration<double, std::milli>(nvbuf_pair_stage_t2 - nvbuf_pair_stage_t1).count();
            double output_transform_ms = std::chrono::duration<double, std::milli>(nvbuf_pair_stage_t3 - nvbuf_pair_stage_t2).count();
            double total_stage_ms = std::chrono::duration<double, std::milli>(nvbuf_pair_stage_t3 - nvbuf_pair_stage_t0).count();
            nvbuf_pair_stage_total_ms += total_stage_ms;
            if (nvbuf_pair_stage_frame <= 5 || nvbuf_pair_stage_frame % 100 == 0)
            {
                cerr << "NVBUFFER_PAIR_STAGE_TIMING frame=" << nvbuf_pair_stage_frame
                     << " input_transform_ms=" << input_transform_ms
                     << " wrapper_call_ms=" << wrapper_call_ms
                     << " output_transform_ms=" << output_transform_ms
                     << " total_stage_ms=" << total_stage_ms
                     << " avg_total_stage_ms=" << (nvbuf_pair_stage_total_ms / nvbuf_pair_stage_frame)
                     << endl;
            }

            if (ctx->enc_output_memory_type == V4L2_MEMORY_DMABUF)
"""
    if "VPI NvBuffer pair scratch buffers are not allocated" not in text:
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
    parser = argparse.ArgumentParser(description="Patch MMAPI transcode sample to test format-matched VPI_IMAGE_BUFFER_NVBUFFER scratch pair.")
    parser.add_argument("--sample-dir", type=Path, required=True)
    args = parser.parse_args()
    patch_main(args.sample_dir / "multivideo_transcode_main.cpp")
    patch_makefile(args.sample_dir / "Makefile")
    print(f"patched NvBuffer pair transcode: {args.sample_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
