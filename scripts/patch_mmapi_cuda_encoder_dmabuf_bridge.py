from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.patch_video_cuda_enc_yuv420_verifier import (
    LOCAL_NVANALYSIS_CU,
    LOCAL_NVANALYSIS_H,
    LOCAL_NVCUDAPROC_CPP,
    LOCAL_NVCUDAPROC_H,
)


BRIDGE_HELPER = r'''
static int
cuda_process_encoder_dmabuf(NvBufSurface *surface, uint32_t width, uint32_t height)
{
    if (surface == NULL)
    {
        return -1;
    }
    if (surface->surfaceList[0].mappedAddr.eglImage == NULL)
    {
        if (NvBufSurfaceMapEglImage(surface, 0) != 0)
        {
            cerr << "CUDA_ENCODER_DMABUF_ERROR map_egl" << endl;
            return -1;
        }
    }
    EGLImageKHR image = surface->surfaceList[0].mappedAddr.eglImage;
    int ret = HandleEGLImage(
        &image, width, height,
        surface->surfaceList[0].planeParams.pitch[0],
        surface->surfaceList[0].planeParams.pitch[1],
        surface->surfaceList[0].planeParams.pitch[2]);
    if (NvBufSurfaceUnMapEglImage(surface, 0) != 0)
    {
        cerr << "CUDA_ENCODER_DMABUF_ERROR unmap_egl" << endl;
        return -1;
    }
    return ret;
}
'''


def patch_makefile(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "NvAnalysis.o" not in text:
        marker = "OBJS := $(SRCS:.cpp=.o)\n"
        if marker not in text:
            raise RuntimeError("OBJS marker not found")
        text = text.replace(
            marker,
            marker + "\nOBJS += NvAnalysis.o NvCudaProc.o\n",
            1,
        )
    if "NvAnalysis.o: NvAnalysis.cu" not in text:
        marker = "%.o: %.cpp\n\t@echo \"Compiling: $<\"\n\t$(CPP) $(CPPFLAGS) -c $<\n"
        if marker not in text:
            raise RuntimeError("local C++ compile rule not found")
        text = text.replace(
            marker,
            marker
            + "\nNvAnalysis.o: NvAnalysis.cu\n"
            + "\t@echo \"Compiling: $<\"\n"
            + "\t$(NVCC) -I$(ALGO_CUDA_DIR) -Xcompiler -fPIC "
            + "-gencode arch=compute_87,code=sm_87 -o $@ -c $<\n",
            1,
        )
    path.write_text(text, encoding="utf-8")


def patch_main(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "CUDA_ENCODER_DMABUF_BRIDGE" in text:
        return
    include_marker = '#include "multivideo_transcode.h"\n'
    if include_marker not in text:
        raise RuntimeError("transcode include marker not found")
    text = text.replace(
        include_marker,
        include_marker
        + "#include <EGL/egl.h>\n"
        + "#include <EGL/eglext.h>\n"
        + '#include "NvCudaProc.h"\n',
        1,
    )
    function_marker = "static void *\ndec_capture_loop_fcn(void *arg)\n{"
    if function_marker not in text:
        raise RuntimeError("decoder capture loop marker not found")
    text = text.replace(
        function_marker,
        BRIDGE_HELPER + "\n" + function_marker,
        1,
    )
    queue_marker = """            if (ctx->enc->output_plane.qBuffer(v4l2_buf, NULL) < 0)
            {
"""
    bridge = """            const char *cuda_bridge_mode = getenv("CUDA_YUV_MODE");
            if (cuda_bridge_mode != NULL && cuda_bridge_mode[0] != '\\0')
            {
                if (cuda_process_encoder_dmabuf(nvbuf_surf, ctx->width, ctx->height) != 0)
                {
                    abort(ctx);
                    cerr << "CUDA_ENCODER_DMABUF_BRIDGE failed mode="
                         << cuda_bridge_mode << endl;
                    break;
                }
            }

"""
    if queue_marker not in text:
        raise RuntimeError("encoder output qBuffer marker not found")
    queue_position = text.rfind(queue_marker)
    text = text[:queue_position] + bridge + text[queue_position:]
    path.write_text(text, encoding="utf-8")


def patch_sample(sample_dir: Path) -> None:
    required = [sample_dir / "Makefile", sample_dir / "multivideo_transcode_main.cpp"]
    if not all(path.exists() for path in required):
        raise FileNotFoundError("sample_dir must be a copied 16_multivideo_transcode sample")
    patch_makefile(sample_dir / "Makefile")
    patch_main(sample_dir / "multivideo_transcode_main.cpp")
    (sample_dir / "NvAnalysis.h").write_text(LOCAL_NVANALYSIS_H, encoding="utf-8")
    (sample_dir / "NvAnalysis.cu").write_text(LOCAL_NVANALYSIS_CU, encoding="utf-8")
    (sample_dir / "NvCudaProc.h").write_text(LOCAL_NVCUDAPROC_H, encoding="utf-8")
    (sample_dir / "NvCudaProc.cpp").write_text(LOCAL_NVCUDAPROC_CPP, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Patch copied 16_multivideo_transcode at the encoder-compatible DMABUF boundary."
    )
    parser.add_argument("sample_dir", type=Path)
    args = parser.parse_args()
    patch_sample(args.sample_dir)
    print(f"patched CUDA encoder-DMABUF bridge: {args.sample_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
