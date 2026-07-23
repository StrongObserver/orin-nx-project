from __future__ import annotations

import argparse
from pathlib import Path


HELPERS = r'''
struct VpiMatrix3x3
{
    float m[3][3];
};

static VPIWarpMap g_remap_map = {};
static VPIPayload g_remap_payload = NULL;
static bool g_remap_ready = false;
static std::string g_remap_mode = "identity";
static int g_remap_width = 0;
static int g_remap_height = 0;
static int g_vpi_input_scratch_fd[MAX_BUFFERS];
static int g_vpi_output_scratch_fd[MAX_BUFFERS];
static bool g_vpi_scratch_fd_ready = false;

static void
init_vpi_scratch_fd_array()
{
    if (!g_vpi_scratch_fd_ready)
    {
        for (int i = 0; i < MAX_BUFFERS; ++i)
        {
            g_vpi_input_scratch_fd[i] = -1;
            g_vpi_output_scratch_fd[i] = -1;
        }
        g_vpi_scratch_fd_ready = true;
    }
}

static int
align_up_int(int value, int align)
{
    return ((value + align - 1) / align) * align;
}

static int
vpi_transform_fd(int src_fd, int dst_fd, uint32_t width, uint32_t height)
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
init_remap_payload_once(uint32_t width, uint32_t height)
{
    if (g_remap_ready)
    {
        return 0;
    }

    const char *mode_env = getenv("VPI_REMAP_MODE");
    if (mode_env != NULL && mode_env[0] != '\0')
    {
        g_remap_mode = mode_env;
    }

    g_remap_width = width;
    g_remap_height = height;
    memset(&g_remap_map, 0, sizeof(g_remap_map));
    g_remap_map.grid.numHorizRegions = 1;
    g_remap_map.grid.numVertRegions = 1;
    g_remap_map.grid.regionWidth[0] = align_up_int(width, 64);
    g_remap_map.grid.regionHeight[0] = align_up_int(height, 16);
    g_remap_map.grid.horizInterval[0] = 16;
    g_remap_map.grid.vertInterval[0] = 16;

    VPIStatus status = vpiWarpMapAllocData(&g_remap_map);
    if (status != VPI_SUCCESS)
    {
        goto fail;
    }
    status = vpiWarpMapGenerateIdentity(&g_remap_map);
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
        for (int y = 0; y < g_remap_map.numVertPoints; ++y)
        {
            VPIKeypointF32 *row = (VPIKeypointF32 *)((uint8_t *)g_remap_map.keypoints + y * g_remap_map.pitchBytes);
            for (int x = 0; x < g_remap_map.numHorizPoints; ++x)
            {
                float px = row[x].x;
                float py = row[x].y;
                if (g_remap_mode == "wave_safe")
                {
                    px = cx + (px - cx) * safe_scale_x;
                    py = cy + (py - cy) * safe_scale_y;
                }
                if (g_remap_mode == "shift")
                {
                    px += shift_x;
                }
                else if (g_remap_mode == "wave" || g_remap_mode == "wave_safe")
                {
                    px += amp * sinf(py * 2.0f * 3.14159265f / std::max(1U, height));
                }
                else if (g_remap_mode != "identity")
                {
                    cerr << "Unsupported VPI_REMAP_MODE=" << g_remap_mode << endl;
                    return -1;
                }
                row[x].x = px;
                row[x].y = py;
            }
        }
    }

    status = vpiCreateRemap(VPI_BACKEND_CUDA, &g_remap_map, &g_remap_payload);
    if (status != VPI_SUCCESS)
    {
        goto fail;
    }

    cerr << "VPI_REMAP_PAYLOAD_READY mode=" << g_remap_mode
         << " width=" << width
         << " height=" << height
         << " grid_width=" << g_remap_map.grid.regionWidth[0]
         << " grid_height=" << g_remap_map.grid.regionHeight[0]
         << " points=" << g_remap_map.numHorizPoints << "x" << g_remap_map.numVertPoints << endl;
    g_remap_ready = true;
    return 0;

fail:
    char msg[VPI_MAX_STATUS_MESSAGE_LENGTH];
    vpiGetLastStatusMessage(msg, sizeof(msg));
    cerr << "VPI Remap payload init failed status=" << status << " msg=" << msg << endl;
    if (g_remap_payload)
    {
        vpiPayloadDestroy(g_remap_payload);
        g_remap_payload = NULL;
    }
    vpiWarpMapFreeData(&g_remap_map);
    return -1;
}

static int
vpi_remap_egl_images(EGLImageKHR input_egl, EGLImageKHR output_egl, uint32_t width, uint32_t height)
{
    VPIImage input = NULL;
    VPIImage output = NULL;
    VPIStream stream = NULL;
    VPIStatus status = VPI_SUCCESS;
    static int frame_count = 0;

    if (init_remap_payload_once(width, height) != 0)
    {
        return -1;
    }

    VPIImageData input_data;
    memset(&input_data, 0, sizeof(input_data));
    input_data.bufferType = VPI_IMAGE_BUFFER_EGLIMAGE;
    input_data.buffer.egl = input_egl;

    VPIImageData output_data;
    memset(&output_data, 0, sizeof(output_data));
    output_data.bufferType = VPI_IMAGE_BUFFER_EGLIMAGE;
    output_data.buffer.egl = output_egl;

    status = vpiStreamCreate(VPI_BACKEND_CUDA, &stream);
    if (status != VPI_SUCCESS) goto vpi_fail;
    status = vpiImageCreateWrapper(&input_data, NULL, VPI_BACKEND_CUDA, &input);
    if (status != VPI_SUCCESS) goto vpi_fail;
    status = vpiImageCreateWrapper(&output_data, NULL, VPI_BACKEND_CUDA, &output);
    if (status != VPI_SUCCESS) goto vpi_fail;

    {
        auto t0 = std::chrono::high_resolution_clock::now();
        status = vpiSubmitRemap(stream, VPI_BACKEND_CUDA, g_remap_payload, input, output,
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
            cerr << "VPI_EGLIMAGE_REMAP frame=" << frame_count << " mode=" << g_remap_mode
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
    cerr << "VPI EGLImage remap failed status=" << status << " msg=" << msg << endl;
    if (output) vpiImageDestroy(output);
    if (input) vpiImageDestroy(input);
    if (stream) vpiStreamDestroy(stream);
    return -1;
}
'''


def patch_main(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "VPI_EGLIMAGE_REMAP" not in text:
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
        )
        marker = "static void\nabort(context_t *ctx)\n{"
        if marker not in text:
            raise RuntimeError(f"abort marker not found in {path}")
        text = text.replace(marker, HELPERS + "\n" + marker, 1)

    query_marker = "    NvBufSurf::NvCommonAllocateParams cParams = {0};\n"
    if "init_vpi_scratch_fd_array();" not in text:
        text = text.replace(query_marker, query_marker + "\n    init_vpi_scratch_fd_array();\n", 1)

    alloc_marker = """            ret = NvBufSurf::NvAllocate(&cParams, 1, &ctx->dmabuff_fd[index]);
            TEST_ERROR(ret < 0, "Failed to create buffers", error);
"""
    alloc_insert = alloc_marker + """            NvBufSurf::NvCommonAllocateParams scratchParams = cParams;
            scratchParams.layout = NVBUF_LAYOUT_PITCH;
            scratchParams.colorFormat = NVBUF_COLOR_FORMAT_NV12_ER;
            if (g_vpi_input_scratch_fd[index] != -1)
            {
                NvBufSurf::NvDestroy(g_vpi_input_scratch_fd[index]);
                g_vpi_input_scratch_fd[index] = -1;
            }
            if (g_vpi_output_scratch_fd[index] != -1)
            {
                NvBufSurf::NvDestroy(g_vpi_output_scratch_fd[index]);
                g_vpi_output_scratch_fd[index] = -1;
            }
            ret = NvBufSurf::NvAllocate(&scratchParams, 1, &g_vpi_input_scratch_fd[index]);
            TEST_ERROR(ret < 0, "Failed to create VPI input scratch buffers", error);
            ret = NvBufSurf::NvAllocate(&scratchParams, 1, &g_vpi_output_scratch_fd[index]);
            TEST_ERROR(ret < 0, "Failed to create VPI output scratch buffers", error);
"""
    if "g_vpi_input_scratch_fd[index]" not in text:
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

            if (g_vpi_input_scratch_fd[v4l2_buf.index] < 0 || g_vpi_output_scratch_fd[v4l2_buf.index] < 0)
            {
                abort(ctx);
                cerr << "VPI Remap scratch buffers are not allocated" << endl;
                break;
            }
            auto remap_stage_t0 = std::chrono::high_resolution_clock::now();
            ret = vpi_transform_fd(ctx->dmabuff_fd[v4l2_buf.index], g_vpi_input_scratch_fd[v4l2_buf.index], ctx->width, ctx->height);
            auto remap_stage_t1 = std::chrono::high_resolution_clock::now();
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while transforming transcode DMABUF to VPI Remap input scratch" << endl;
                break;
            }
            NvBufSurface *input_scratch_surf = 0;
            ret = NvBufSurfaceFromFd(g_vpi_input_scratch_fd[v4l2_buf.index], (void**)(&input_scratch_surf));
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while calling NvBufSurfaceFromFd for VPI Remap input scratch" << endl;
                break;
            }
            NvBufSurface *output_scratch_surf = 0;
            ret = NvBufSurfaceFromFd(g_vpi_output_scratch_fd[v4l2_buf.index], (void**)(&output_scratch_surf));
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while calling NvBufSurfaceFromFd for VPI Remap output scratch" << endl;
                break;
            }
            if (input_scratch_surf->surfaceList[0].mappedAddr.eglImage == NULL)
            {
                if (NvBufSurfaceMapEglImage(input_scratch_surf, 0) != 0)
                {
                    abort(ctx);
                    cerr << "Unable to map VPI Remap input scratch fd to EGLImage" << endl;
                    break;
                }
            }
            if (output_scratch_surf->surfaceList[0].mappedAddr.eglImage == NULL)
            {
                if (NvBufSurfaceMapEglImage(output_scratch_surf, 0) != 0)
                {
                    abort(ctx);
                    cerr << "Unable to map VPI Remap output scratch fd to EGLImage" << endl;
                    break;
                }
            }
            auto remap_stage_t2 = std::chrono::high_resolution_clock::now();
            ret = vpi_remap_egl_images(input_scratch_surf->surfaceList[0].mappedAddr.eglImage,
                                       output_scratch_surf->surfaceList[0].mappedAddr.eglImage,
                                       ctx->width, ctx->height);
            auto remap_stage_t3 = std::chrono::high_resolution_clock::now();
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while VPI Remap on EGLImage scratch buffers" << endl;
                break;
            }
            if (NvBufSurfaceUnMapEglImage(input_scratch_surf, 0) != 0)
            {
                abort(ctx);
                cerr << "Unable to unmap VPI Remap input scratch EGLImage" << endl;
                break;
            }
            if (NvBufSurfaceUnMapEglImage(output_scratch_surf, 0) != 0)
            {
                abort(ctx);
                cerr << "Unable to unmap VPI Remap output scratch EGLImage" << endl;
                break;
            }
            auto remap_stage_t4 = std::chrono::high_resolution_clock::now();
            ret = vpi_transform_fd(g_vpi_output_scratch_fd[v4l2_buf.index], ctx->dmabuff_fd[v4l2_buf.index], ctx->width, ctx->height);
            auto remap_stage_t5 = std::chrono::high_resolution_clock::now();
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while transforming VPI Remap output scratch back to transcode DMABUF" << endl;
                break;
            }
            static int remap_stage_frame = 0;
            static double remap_stage_total_ms = 0.0;
            remap_stage_frame++;
            double input_transform_ms = std::chrono::duration<double, std::milli>(remap_stage_t1 - remap_stage_t0).count();
            double wrapper_call_ms = std::chrono::duration<double, std::milli>(remap_stage_t3 - remap_stage_t2).count();
            double output_transform_ms = std::chrono::duration<double, std::milli>(remap_stage_t5 - remap_stage_t4).count();
            double total_stage_ms = std::chrono::duration<double, std::milli>(remap_stage_t5 - remap_stage_t0).count();
            remap_stage_total_ms += total_stage_ms;
            if (remap_stage_frame <= 5 || remap_stage_frame % 100 == 0)
            {
                cerr << "REMAP_STAGE_TIMING frame=" << remap_stage_frame
                     << " input_transform_ms=" << input_transform_ms
                     << " wrapper_call_ms=" << wrapper_call_ms
                     << " output_transform_ms=" << output_transform_ms
                     << " total_stage_ms=" << total_stage_ms
                     << " avg_total_stage_ms=" << (remap_stage_total_ms / remap_stage_frame)
                     << endl;
            }

            if (ctx->enc_output_memory_type == V4L2_MEMORY_DMABUF)
"""
    if "VPI Remap scratch buffers are not allocated" not in text:
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
    parser = argparse.ArgumentParser(description="Patch accepted EGLImage MMAPI sample to run VPI Remap on pitch-linear scratch buffers.")
    parser.add_argument("--sample-dir", type=Path, required=True)
    args = parser.parse_args()
    patch_main(args.sample_dir / "multivideo_transcode_main.cpp")
    patch_makefile(args.sample_dir / "Makefile")
    print(f"patched EGLImage Remap transcode: {args.sample_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
