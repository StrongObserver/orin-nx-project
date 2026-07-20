from __future__ import annotations

import argparse
from pathlib import Path


HELPERS = r'''
static int g_format_probe_input_scratch_fd[MAX_BUFFERS];
static int g_format_probe_output_scratch_fd[MAX_BUFFERS];
static bool g_format_probe_scratch_fd_ready = false;

static void
init_format_probe_scratch_fd_array()
{
    if (!g_format_probe_scratch_fd_ready)
    {
        for (int i = 0; i < MAX_BUFFERS; ++i)
        {
            g_format_probe_input_scratch_fd[i] = -1;
            g_format_probe_output_scratch_fd[i] = -1;
        }
        g_format_probe_scratch_fd_ready = true;
    }
}

static void
print_surface_info(const char *label, int fd, NvBufSurface *surf)
{
    if (surf == NULL)
    {
        cerr << "SURFACE_INFO label=" << label << " fd=" << fd << " null=1" << endl;
        return;
    }
    NvBufSurfaceParams &p = surf->surfaceList[0];
    cerr << "SURFACE_INFO label=" << label
         << " fd=" << fd
         << " memType=" << surf->memType
         << " batchSize=" << surf->batchSize
         << " width=" << p.width
         << " height=" << p.height
         << " pitch=" << p.pitch
         << " colorFormat=" << p.colorFormat
         << " layout=" << p.layout
         << " plane0_width=" << p.planeParams.width[0]
         << " plane0_height=" << p.planeParams.height[0]
         << " plane0_pitch=" << p.planeParams.pitch[0]
         << " plane0_offset=" << p.planeParams.offset[0]
         << " plane1_width=" << p.planeParams.width[1]
         << " plane1_height=" << p.planeParams.height[1]
         << " plane1_pitch=" << p.planeParams.pitch[1]
         << " plane1_offset=" << p.planeParams.offset[1]
         << endl;
}
'''


def patch_main(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "SURFACE_INFO label=" in text:
        print(f"already surface-format patched: {path}")
        return

    marker = "static void\nabort(context_t *ctx)\n{"
    if marker not in text:
        raise RuntimeError(f"abort marker not found in {path}")
    text = text.replace(marker, HELPERS + "\n" + marker, 1)

    query_marker = "    NvBufSurf::NvCommonAllocateParams cParams = {0};\n"
    if "init_format_probe_scratch_fd_array();" not in text:
        text = text.replace(query_marker, query_marker + "\n    init_format_probe_scratch_fd_array();\n", 1)

    alloc_marker = """            ret = NvBufSurf::NvAllocate(&cParams, 1, &ctx->dmabuff_fd[index]);
            TEST_ERROR(ret < 0, "Failed to create buffers", error);
"""
    alloc_insert = alloc_marker + """            NvBufSurf::NvCommonAllocateParams scratchParams = cParams;
            scratchParams.layout = NVBUF_LAYOUT_PITCH;
            scratchParams.colorFormat = NVBUF_COLOR_FORMAT_NV12_ER;
            if (g_format_probe_input_scratch_fd[index] != -1)
            {
                NvBufSurf::NvDestroy(g_format_probe_input_scratch_fd[index]);
                g_format_probe_input_scratch_fd[index] = -1;
            }
            if (g_format_probe_output_scratch_fd[index] != -1)
            {
                NvBufSurf::NvDestroy(g_format_probe_output_scratch_fd[index]);
                g_format_probe_output_scratch_fd[index] = -1;
            }
            ret = NvBufSurf::NvAllocate(&scratchParams, 1, &g_format_probe_input_scratch_fd[index]);
            TEST_ERROR(ret < 0, "Failed to create format probe input scratch buffers", error);
            ret = NvBufSurf::NvAllocate(&scratchParams, 1, &g_format_probe_output_scratch_fd[index]);
            TEST_ERROR(ret < 0, "Failed to create format probe output scratch buffers", error);
"""
    if "g_format_probe_input_scratch_fd[index]" not in text:
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

            if (v4l2_buf.index == 0)
            {
                print_surface_info("main_dmabuf", ctx->dmabuff_fd[v4l2_buf.index], nvbuf_surf);
                NvBufSurface *input_scratch_surf = 0;
                ret = NvBufSurfaceFromFd(g_format_probe_input_scratch_fd[v4l2_buf.index], (void**)(&input_scratch_surf));
                if (ret == 0)
                {
                    print_surface_info("input_scratch", g_format_probe_input_scratch_fd[v4l2_buf.index], input_scratch_surf);
                }
                else
                {
                    cerr << "SURFACE_INFO label=input_scratch fd=" << g_format_probe_input_scratch_fd[v4l2_buf.index] << " fromfd_error=" << ret << endl;
                }
                NvBufSurface *output_scratch_surf = 0;
                ret = NvBufSurfaceFromFd(g_format_probe_output_scratch_fd[v4l2_buf.index], (void**)(&output_scratch_surf));
                if (ret == 0)
                {
                    print_surface_info("output_scratch", g_format_probe_output_scratch_fd[v4l2_buf.index], output_scratch_surf);
                }
                else
                {
                    cerr << "SURFACE_INFO label=output_scratch fd=" << g_format_probe_output_scratch_fd[v4l2_buf.index] << " fromfd_error=" << ret << endl;
                }
            }

            if (ctx->enc_output_memory_type == V4L2_MEMORY_DMABUF)
"""
    if "print_surface_info(\"main_dmabuf\"" not in text:
        if insert_marker not in text:
            raise RuntimeError("NvBufSurfaceFromFd insertion block not found")
        text = text.replace(insert_marker, insert_replacement, 1)

    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Patch MMAPI transcode sample to print main/scratch NvBufSurface format and layout.")
    parser.add_argument("--sample-dir", type=Path, required=True)
    args = parser.parse_args()
    patch_main(args.sample_dir / "multivideo_transcode_main.cpp")
    print(f"patched surface format probe: {args.sample_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
