from __future__ import annotations

import argparse
from pathlib import Path

from patch_mmapi_vpi_encode_warp import VPI_INSERT


def patch_main(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "VPI_TRANSCODE_WARP" not in text:
        text = text.replace(
            '#include "NvUtils.h"\n#include "multivideo_transcode.h"\n',
            '#include "NvUtils.h"\n#include "multivideo_transcode.h"\n'
            "#include <chrono>\n"
            "#include <cuda.h>\n"
            "#include <cuda_runtime.h>\n"
            '#include "cudaEGL.h"\n'
            "#include <vpi/Image.h>\n"
            "#include <vpi/Status.h>\n"
            "#include <vpi/Stream.h>\n"
            "#include <vpi/algo/PerspectiveWarp.h>\n",
        )
        marker = "static void *\ndec_capture_loop_fcn(void *arg)\n{"
        if marker not in text:
            raise RuntimeError(f"decode capture marker not found in {path}")
        insert = VPI_INSERT.replace("VPI_ENC_WARP", "VPI_TRANSCODE_WARP")
        text = text.replace(marker, insert + "\n" + marker, 1)

    old = """            ret = NvBufSurfaceFromFd(ctx->dmabuff_fd[v4l2_buf.index], (void**)(&nvbuf_surf));
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while calling NvBufSurfaceFromFd" << endl;
                break;
            }

            if (ctx->enc_output_memory_type == V4L2_MEMORY_DMABUF)
"""
    new = """            ret = NvBufSurfaceFromFd(ctx->dmabuff_fd[v4l2_buf.index], (void**)(&nvbuf_surf));
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while calling NvBufSurfaceFromFd" << endl;
                break;
            }

            if (nvbuf_surf->surfaceList[0].mappedAddr.eglImage == NULL)
            {
                if (NvBufSurfaceMapEglImage(nvbuf_surf, 0) != 0)
                {
                    abort(ctx);
                    cerr << "Unable to map transcode dmabuf fd to EGLImage" << endl;
                    break;
                }
            }
            static bool printed_surface_info = false;
            if (!printed_surface_info)
            {
                cerr << "VPI_SURFACE_INFO width=" << nvbuf_surf->surfaceList[0].width
                     << " height=" << nvbuf_surf->surfaceList[0].height
                     << " pitch=" << nvbuf_surf->surfaceList[0].pitch
                     << " layout=" << nvbuf_surf->surfaceList[0].layout
                     << " colorFormat=" << nvbuf_surf->surfaceList[0].colorFormat
                     << " num_planes=" << nvbuf_surf->surfaceList[0].planeParams.num_planes
                     << " p0_pitch=" << nvbuf_surf->surfaceList[0].planeParams.pitch[0]
                     << " p0_offset=" << nvbuf_surf->surfaceList[0].planeParams.offset[0]
                     << " p0_width=" << nvbuf_surf->surfaceList[0].planeParams.width[0]
                     << " p0_height=" << nvbuf_surf->surfaceList[0].planeParams.height[0]
                     << " p1_pitch=" << nvbuf_surf->surfaceList[0].planeParams.pitch[1]
                     << " p1_offset=" << nvbuf_surf->surfaceList[0].planeParams.offset[1]
                     << " p1_width=" << nvbuf_surf->surfaceList[0].planeParams.width[1]
                     << " p1_height=" << nvbuf_surf->surfaceList[0].planeParams.height[1]
                     << endl;
                printed_surface_info = true;
            }
            ret = vpi_warp_egl_image(nvbuf_surf->surfaceList[0].mappedAddr.eglImage);
            if (ret < 0)
            {
                abort(ctx);
                cerr << "Error while VPI warp on transcode DMABUF" << endl;
                break;
            }
            if (NvBufSurfaceUnMapEglImage(nvbuf_surf, 0) != 0)
            {
                abort(ctx);
                cerr << "Unable to unmap transcode EGLImage" << endl;
                break;
            }

            if (ctx->enc_output_memory_type == V4L2_MEMORY_DMABUF)
"""
    if old not in text:
        raise RuntimeError("NvBufSurfaceFromFd insertion block not found")
    text = text.replace(old, new, 1)
    text = text.replace(
        "            cParams.layout = NVBUF_LAYOUT_BLOCK_LINEAR;",
        "            cParams.layout = NVBUF_LAYOUT_PITCH;",
        1,
    )
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
    parser = argparse.ArgumentParser(description="Patch copied MMAPI 16_multivideo_transcode sample to run VPI CUDA warp before encoder qBuffer.")
    parser.add_argument("--sample-dir", type=Path, required=True)
    args = parser.parse_args()
    patch_main(args.sample_dir / "multivideo_transcode_main.cpp")
    patch_makefile(args.sample_dir / "Makefile")
    print(f"patched: {args.sample_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
