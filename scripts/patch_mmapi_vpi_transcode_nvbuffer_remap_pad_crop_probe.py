from __future__ import annotations

import argparse
from pathlib import Path


HELPERS = r'''
static VPIWarpMap g_nvbuf_remap_map = {};
static VPIPayload g_nvbuf_remap_payload = NULL;
static bool g_nvbuf_remap_ready = false;
static std::string g_nvbuf_remap_mode = "identity";
static uint32_t g_nvbuf_remap_scratch_width = 0;
static uint32_t g_nvbuf_remap_scratch_height = 0;
static int g_nvbuf_remap_input_scratch_fd[MAX_BUFFERS];
static int g_nvbuf_remap_output_scratch_fd[MAX_BUFFERS];
static bool g_nvbuf_remap_scratch_fd_ready = false;

static void
init_nvbuf_remap_scratch_fd_array()
{
    if (!g_nvbuf_remap_scratch_fd_ready)
    {
        for (int i = 0; i < MAX_BUFFERS; ++i)
        {
            g_nvbuf_remap_input_scratch_fd[i] = -1;
            g_nvbuf_remap_output_scratch_fd[i] = -1;
        }
        g_nvbuf_remap_scratch_fd_ready = true;
    }
}

static int
align_up_int(int value, int align)
{
    return ((value + align - 1) / align) * align;
}

static int
nvbuf_remap_transform_fd_roi(int src_fd, int dst_fd, uint32_t roi_width, uint32_t roi_height)
{
    NvBufSurf::NvCommonTransformParams transform_params;
    memset(&transform_params, 0, sizeof(transform_params));
    transform_params.src_top = 0;
    transform_params.src_left = 0;
    transform_params.src_width = roi_width;
    transform_params.src_height = roi_height;
    transform_params.dst_top = 0;
    transform_params.dst_left = 0;
    transform_params.dst_width = roi_width;
    transform_params.dst_height = roi_height;
    transform_params.flag = NVBUFSURF_TRANSFORM_FILTER;
    transform_params.flip = NvBufSurfTransform_None;
    transform_params.filter = NvBufSurfTransformInter_Nearest;
    return NvBufSurf::NvTransform(&transform_params, src_fd, dst_fd);
}

static int
init_nvbuf_remap_payload_once(uint32_t width, uint32_t height)
{
    if (g_nvbuf_remap_ready)
    {
        return 0;
    }

    const char *mode_env = getenv("VPI_REMAP_MODE");
    if (mode_env != NULL && mode_env[0] != '\0')
    {
        g_nvbuf_remap_mode = mode_env;
    }

    memset(&g_nvbuf_remap_map, 0, sizeof(g_nvbuf_remap_map));
    g_nvbuf_remap_map.grid.numHorizRegions = 1;
    g_nvbuf_remap_map.grid.numVertRegions = 1;
    g_nvbuf_remap_map.grid.regionWidth[0] = align_up_int(width, 64);
    g_nvbuf_remap_map.grid.regionHeight[0] = align_up_int(height, 16);
    g_nvbuf_remap_map.grid.horizInterval[0] = 16;
    g_nvbuf_remap_map.grid.vertInterval[0] = 16;

    VPIStatus status = vpiWarpMapAllocData(&g_nvbuf_remap_map);
    if (status != VPI_SUCCESS)
    {
        goto fail;
    }
    status = vpiWarpMapGenerateIdentity(&g_nvbuf_remap_map);
    if (status != VPI_SUCCESS)
    {
        goto fail;
    }

    {
        float amp = std::max(3.0f, width * 0.015f);
        float shift_x = std::max(4.0f, width * 0.02f);
        float safe_margin = amp + 2.0f;
        float safe_scale_x = std::max(0.80f, ((float)width - 2.0f * safe_margin) / std::max(1.0f, (float)width));
        float safe_scale_y = std::max(0.80f, ((float)height - 8.0f) / std::max(1.0f, (float)height));
        float cx = ((float)width - 1.0f) * 0.5f;
        float cy = ((float)height - 1.0f) * 0.5f;
        for (int y = 0; y < g_nvbuf_remap_map.numVertPoints; ++y)
        {
            VPIKeypointF32 *row = (VPIKeypointF32 *)((uint8_t *)g_nvbuf_remap_map.keypoints + y * g_nvbuf_remap_map.pitchBytes);
            for (int x = 0; x < g_nvbuf_remap_map.numHorizPoints; ++x)
            {
                float px = row[x].x;
                float py = row[x].y;
                if (g_nvbuf_remap_mode == "wave_safe")
                {
                    px = cx + (px - cx) * safe_scale_x;
                    py = cy + (py - cy) * safe_scale_y;
                }
                if (g_nvbuf_remap_mode == "shift")
                {
                    px += shift_x;
                }
                else if (g_nvbuf_remap_mode == "wave" || g_nvbuf_remap_mode == "wave_safe")
                {
                    px += amp * sinf(py * 2.0f * 3.14159265f / std::max(1U, height));
                }
                else if (g_nvbuf_remap_mode != "identity")
                {
                    cerr << "Unsupported VPI_REMAP_MODE=" << g_nvbuf_remap_mode << endl;
                    return -1;
                }
                row[x].x = px;
                row[x].y = py;
            }
        }
    }

    status = vpiCreateRemap(VPI_BACKEND_CUDA, &g_nvbuf_remap_map, &g_nvbuf_remap_payload);
    if (status != VPI_SUCCESS)
    {
        goto fail;
    }

    cerr << "VPI_NVBUFFER_REMAP_PAD_CROP_PAYLOAD_READY mode=" << g_nvbuf_remap_mode
         << " width=" << width
         << " height=" << height
         << " grid_width=" << g_nvbuf_remap_map.grid.regionWidth[0]
         << " grid_height=" << g_nvbuf_remap_map.grid.regionHeight[0]
         << " points=" << g_nvbuf_remap_map.numHorizPoints << "x" << g_nvbuf_remap_map.numVertPoints << endl;
    g_nvbuf_remap_ready = true;
    return 0;

fail:
    char msg[VPI_MAX_STATUS_MESSAGE_LENGTH];
    vpiGetLastStatusMessage(msg, sizeof(msg));
    cerr << "VPI NvBuffer Remap pad/crop payload init failed status=" << status << " msg=" << msg << endl;
    if (g_nvbuf_remap_payload)
    {
        vpiPayloadDestroy(g_nvbuf_remap_payload);
        g_nvbuf_remap_payload = NULL;
    }
    vpiWarpMapFreeData(&g_nvbuf_remap_map);
    return -1;
}

static int
vpi_remap_nvbuffer_pair(int input_fd, int output_fd, uint32_t width, uint32_t height)
{
    VPIImage input = NULL;
    VPIImage output = NULL;
    VPIStream stream = NULL;
    VPIStatus status = VPI_SUCCESS;
    static int frame_count = 0;

    if (init_nvbuf_remap_payload_once(width, height) != 0)
    {
        return -1;
    }

    VPIImageData input_data;
    memset(&input_data, 0, sizeof(input_data));
    input_data.bufferType = VPI_IMAGE_BUFFER_NVBUFFER;
    input_data.buffer.fd = input_fd;

    VPIImageData output_data;
    memset(&output_data, 0, sizeof(output_data));
    output_data.bufferType = VPI_IMAGE_BUFFER_NVBUFFER;
    output_data.buffer.fd = output_fd;

    status = vpiStreamCreate(VPI_BACKEND_CUDA, &stream);
    if (status != VPI_SUCCESS) goto vpi_fail;
    status = vpiImageCreateWrapper(&input_data, NULL, VPI_BACKEND_CUDA, &input);
    if (status != VPI_SUCCESS) goto vpi_fail;
    status = vpiImageCreateWrapper(&output_data, NULL, VPI_BACKEND_CUDA, &output);
    if (status != VPI_SUCCESS) goto vpi_fail;

    {
        auto t0 = std::chrono::high_resolution_clock::now();
        status = vpiSubmitRemap(stream, VPI_BACKEND_CUDA, g_nvbuf_remap_payload, input, output,
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
            cerr << "VPI_NVBUFFER_REMAP_PAD_CROP frame=" << frame_count
                 << " mode=" << g_nvbuf_remap_mode
                 << " scratch_width=" << width
                 << " scratch_height=" << height
                 << " elapsed_ms=" << elapsed_ms
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
    cerr << "VPI NvBuffer Remap pad/crop failed status=" << status << " msg=" << msg << endl;
    if (output) vpiImageDestroy(output);
    if (input) vpiImageDestroy(input);
    if (stream) vpiStreamDestroy(stream);
    return -1;
}
'''


def patch_main(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "VPI_NVBUFFER_REMAP_PAD_CROP" in text:
        print(f"already NvBuffer Remap pad/crop patched: {path}")
        return

    text = text.replace(
        '#include "NvUtils.h"\n#include "multivideo_transcode.h"\n',
        '#include "NvUtils.h"\n#include "multivideo_transcode.h"\n'
        "#include <algorithm>\n"
        "#include <chrono>\n"
        "#include <cmath>\n"
        "#include <cstdlib>\n"
        "#include <string>\n"
        "#include <vpi/Image.h>\n"
        "#include <vpi/Status.h>\n"
        "#include <vpi/Stream.h>\n"
        "#include <vpi/WarpMap.h>\n"
        "#include <vpi/algo/Remap.h>\n",
        1,
    )
    marker = "static void\nabort(context_t *ctx)\n{"
    if marker not in text:
        raise RuntimeError(f"abort marker not found in {path}")
    text = text.replace(marker, HELPERS + "\n" + marker, 1)

    query_marker = "    NvBufSurf::NvCommonAllocateParams cParams = {0};\n"
    if "init_nvbuf_remap_scratch_fd_array();" not in text:
        text = text.replace(query_marker, query_marker + "\n    init_nvbuf_remap_scratch_fd_array();\n", 1)

    alloc_marker = """            ret = NvBufSurf::NvAllocate(&cParams, 1, &ctx->dmabuff_fd[index]);
            TEST_ERROR(ret < 0, "Failed to create buffers", error);
"""
    alloc_insert = alloc_marker + """            NvBufSurf::NvCommonAllocateParams scratchParams = cParams;
            scratchParams.layout = NVBUF_LAYOUT_PITCH;
            scratchParams.colorFormat = NVBUF_COLOR_FORMAT_NV12_ER;
            scratchParams.width = align_up_int((int)cParams.width, 64);
            scratchParams.height = align_up_int((int)cParams.height, 16);
            g_nvbuf_remap_scratch_width = scratchParams.width;
            g_nvbuf_remap_scratch_height = scratchParams.height;
            if (g_nvbuf_remap_input_scratch_fd[index] != -1)
            {
                NvBufSurf::NvDestroy(g_nvbuf_remap_input_scratch_fd[index]);
                g_nvbuf_remap_input_scratch_fd[index] = -1;
            }
            if (g_nvbuf_remap_output_scratch_fd[index] != -1)
            {
                NvBufSurf::NvDestroy(g_nvbuf_remap_output_scratch_fd[index]);
                g_nvbuf_remap_output_scratch_fd[index] = -1;
            }
            ret = NvBufSurf::NvAllocate(&scratchParams, 1, &g_nvbuf_remap_input_scratch_fd[index]);
            TEST_ERROR(ret < 0, "Failed to create VPI NvBuffer Remap input scratch buffers", error);
            ret = NvBufSurf::NvAllocate(&scratchParams, 1, &g_nvbuf_remap_output_scratch_fd[index]);
            TEST_ERROR(ret < 0, "Failed to create VPI NvBuffer Remap output scratch buffers", error);
            if (index == 0)
            {
                cerr << "NVBUFFER_REMAP_PAD_CROP_SCRATCH_ALLOC main_width=" << cParams.width
                     << " main_height=" << cParams.height
                     << " scratch_width=" << scratchParams.width
                     << " scratch_height=" << scratchParams.height << endl;
            }
"""
    if "g_nvbuf_remap_input_scratch_fd[index]" not in text:
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

            if (g_nvbuf_remap_input_scratch_fd[v4l2_buf.index] < 0 || g_nvbuf_remap_output_scratch_fd[v4l2_buf.index] < 0)
            {
                abort(ctx);
                cerr << "VPI NvBuffer Remap scratch buffers are not allocated" << endl;
                break;
            }
            auto nvbuf_remap_stage_t0 = std::chrono::high_resolution_clock::now();
            ret = nvbuf_remap_transform_fd_roi(ctx->dmabuff_fd[v4l2_buf.index],
                                               g_nvbuf_remap_input_scratch_fd[v4l2_buf.index],
                                               ctx->width, ctx->height);
            auto nvbuf_remap_stage_t1 = std::chrono::high_resolution_clock::now();
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while transforming native main DMABUF to VPI NvBuffer Remap input scratch" << endl;
                break;
            }
            ret = vpi_remap_nvbuffer_pair(g_nvbuf_remap_input_scratch_fd[v4l2_buf.index],
                                          g_nvbuf_remap_output_scratch_fd[v4l2_buf.index],
                                          g_nvbuf_remap_scratch_width, g_nvbuf_remap_scratch_height);
            auto nvbuf_remap_stage_t2 = std::chrono::high_resolution_clock::now();
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while VPI Remap on NvBuffer scratch pair" << endl;
                break;
            }
            ret = nvbuf_remap_transform_fd_roi(g_nvbuf_remap_output_scratch_fd[v4l2_buf.index],
                                               ctx->dmabuff_fd[v4l2_buf.index],
                                               ctx->width, ctx->height);
            auto nvbuf_remap_stage_t3 = std::chrono::high_resolution_clock::now();
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while transforming VPI NvBuffer Remap output scratch back to native main DMABUF" << endl;
                break;
            }
            static int nvbuf_remap_stage_frame = 0;
            static double nvbuf_remap_stage_total_ms = 0.0;
            nvbuf_remap_stage_frame++;
            double input_transform_ms = std::chrono::duration<double, std::milli>(nvbuf_remap_stage_t1 - nvbuf_remap_stage_t0).count();
            double wrapper_call_ms = std::chrono::duration<double, std::milli>(nvbuf_remap_stage_t2 - nvbuf_remap_stage_t1).count();
            double output_transform_ms = std::chrono::duration<double, std::milli>(nvbuf_remap_stage_t3 - nvbuf_remap_stage_t2).count();
            double total_stage_ms = std::chrono::duration<double, std::milli>(nvbuf_remap_stage_t3 - nvbuf_remap_stage_t0).count();
            nvbuf_remap_stage_total_ms += total_stage_ms;
            if (nvbuf_remap_stage_frame <= 5 || nvbuf_remap_stage_frame % 100 == 0)
            {
                cerr << "NVBUFFER_REMAP_PAD_CROP_STAGE_TIMING frame=" << nvbuf_remap_stage_frame
                     << " main_width=" << ctx->width
                     << " main_height=" << ctx->height
                     << " scratch_width=" << g_nvbuf_remap_scratch_width
                     << " scratch_height=" << g_nvbuf_remap_scratch_height
                     << " input_transform_ms=" << input_transform_ms
                     << " wrapper_call_ms=" << wrapper_call_ms
                     << " output_transform_ms=" << output_transform_ms
                     << " total_stage_ms=" << total_stage_ms
                     << " avg_total_stage_ms=" << (nvbuf_remap_stage_total_ms / nvbuf_remap_stage_frame)
                     << endl;
            }

            if (ctx->enc_output_memory_type == V4L2_MEMORY_DMABUF)
"""
    if "VPI NvBuffer Remap scratch buffers are not allocated" not in text:
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
            1,
        )
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Patch MMAPI sample to test VPI Remap pad/crop with VPI_IMAGE_BUFFER_NVBUFFER wrappers.")
    parser.add_argument("--sample-dir", type=Path, required=True)
    args = parser.parse_args()
    patch_main(args.sample_dir / "multivideo_transcode_main.cpp")
    patch_makefile(args.sample_dir / "Makefile")
    print(f"patched NvBuffer Remap pad/crop transcode: {args.sample_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
