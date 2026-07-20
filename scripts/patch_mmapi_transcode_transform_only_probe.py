from __future__ import annotations

import argparse
from pathlib import Path


HELPERS = r'''
static int g_transform_input_scratch_fd[MAX_BUFFERS];
static int g_transform_output_scratch_fd[MAX_BUFFERS];
static bool g_transform_scratch_fd_ready = false;

static void
init_transform_scratch_fd_array()
{
    if (!g_transform_scratch_fd_ready)
    {
        for (int i = 0; i < MAX_BUFFERS; ++i)
        {
            g_transform_input_scratch_fd[i] = -1;
            g_transform_output_scratch_fd[i] = -1;
        }
        g_transform_scratch_fd_ready = true;
    }
}

static int
transform_probe_fd(int src_fd, int dst_fd, uint32_t width, uint32_t height)
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
'''


def patch_main(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "TRANSFORM_ONLY_STAGE" in text:
        print(f"already transform-only patched: {path}")
        return

    text = text.replace(
        '#include "NvUtils.h"\n#include "multivideo_transcode.h"\n',
        '#include "NvUtils.h"\n#include "multivideo_transcode.h"\n'
        "#include <chrono>\n",
    )
    marker = "static void\nabort(context_t *ctx)\n{"
    if marker not in text:
        raise RuntimeError(f"abort marker not found in {path}")
    text = text.replace(marker, HELPERS + "\n" + marker, 1)

    query_marker = "    NvBufSurf::NvCommonAllocateParams cParams = {0};\n"
    if "init_transform_scratch_fd_array();" not in text:
        text = text.replace(query_marker, query_marker + "\n    init_transform_scratch_fd_array();\n", 1)

    alloc_marker = """            ret = NvBufSurf::NvAllocate(&cParams, 1, &ctx->dmabuff_fd[index]);
            TEST_ERROR(ret < 0, "Failed to create buffers", error);
"""
    alloc_insert = alloc_marker + """            NvBufSurf::NvCommonAllocateParams scratchParams = cParams;
            scratchParams.layout = NVBUF_LAYOUT_PITCH;
            scratchParams.colorFormat = NVBUF_COLOR_FORMAT_NV12_ER;
            if (g_transform_input_scratch_fd[index] != -1)
            {
                NvBufSurf::NvDestroy(g_transform_input_scratch_fd[index]);
                g_transform_input_scratch_fd[index] = -1;
            }
            if (g_transform_output_scratch_fd[index] != -1)
            {
                NvBufSurf::NvDestroy(g_transform_output_scratch_fd[index]);
                g_transform_output_scratch_fd[index] = -1;
            }
            ret = NvBufSurf::NvAllocate(&scratchParams, 1, &g_transform_input_scratch_fd[index]);
            TEST_ERROR(ret < 0, "Failed to create transform input scratch buffers", error);
            ret = NvBufSurf::NvAllocate(&scratchParams, 1, &g_transform_output_scratch_fd[index]);
            TEST_ERROR(ret < 0, "Failed to create transform output scratch buffers", error);
"""
    if "g_transform_input_scratch_fd[index]" not in text:
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

            if (g_transform_input_scratch_fd[v4l2_buf.index] < 0 || g_transform_output_scratch_fd[v4l2_buf.index] < 0)
            {
                abort(ctx);
                cerr << "Transform probe scratch buffers are not allocated" << endl;
                break;
            }
            auto transform_t0 = std::chrono::high_resolution_clock::now();
            ret = transform_probe_fd(ctx->dmabuff_fd[v4l2_buf.index], g_transform_input_scratch_fd[v4l2_buf.index], ctx->width, ctx->height);
            auto transform_t1 = std::chrono::high_resolution_clock::now();
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while transform-probing input scratch" << endl;
                break;
            }
            ret = transform_probe_fd(g_transform_input_scratch_fd[v4l2_buf.index], g_transform_output_scratch_fd[v4l2_buf.index], ctx->width, ctx->height);
            auto transform_t2 = std::chrono::high_resolution_clock::now();
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while transform-probing scratch copy" << endl;
                break;
            }
            ret = transform_probe_fd(g_transform_output_scratch_fd[v4l2_buf.index], ctx->dmabuff_fd[v4l2_buf.index], ctx->width, ctx->height);
            auto transform_t3 = std::chrono::high_resolution_clock::now();
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while transform-probing output back to DMABUF" << endl;
                break;
            }
            static int transform_probe_frame = 0;
            static double transform_probe_total_ms = 0.0;
            transform_probe_frame++;
            double input_ms = std::chrono::duration<double, std::milli>(transform_t1 - transform_t0).count();
            double scratch_copy_ms = std::chrono::duration<double, std::milli>(transform_t2 - transform_t1).count();
            double output_ms = std::chrono::duration<double, std::milli>(transform_t3 - transform_t2).count();
            double total_ms = std::chrono::duration<double, std::milli>(transform_t3 - transform_t0).count();
            transform_probe_total_ms += total_ms;
            if (transform_probe_frame <= 5 || transform_probe_frame % 100 == 0)
            {
                cerr << "TRANSFORM_ONLY_STAGE frame=" << transform_probe_frame
                     << " input_ms=" << input_ms
                     << " scratch_copy_ms=" << scratch_copy_ms
                     << " output_ms=" << output_ms
                     << " total_ms=" << total_ms
                     << " avg_total_ms=" << (transform_probe_total_ms / transform_probe_frame)
                     << endl;
            }

            if (ctx->enc_output_memory_type == V4L2_MEMORY_DMABUF)
"""
    if "TRANSFORM_ONLY_STAGE frame=" not in text:
        if insert_marker not in text:
            raise RuntimeError("NvBufSurfaceFromFd insertion block not found")
        text = text.replace(insert_marker, insert_replacement, 1)

    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Patch MMAPI transcode sample to measure transform-only dataflow cost.")
    parser.add_argument("--sample-dir", type=Path, required=True)
    args = parser.parse_args()
    patch_main(args.sample_dir / "multivideo_transcode_main.cpp")
    print(f"patched transform-only probe: {args.sample_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
