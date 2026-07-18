from __future__ import annotations

import argparse
from pathlib import Path

from patch_mmapi_vpi_encode_warp import VPI_INSERT


def patch_main(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "VPI_ENC_WARP" in text:
        text = text.replace("VPI_ENC_WARP", "VPI_DEC_WARP")
    else:
        text = text.replace(
            '#include "videodec.h"\n',
            '#include "videodec.h"\n'
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
        insert = VPI_INSERT.replace("VPI_ENC_WARP", "VPI_DEC_WARP")
        text = text.replace(marker, insert + "\n" + marker, 1)

    old = (
        "            /* Map EGLImage to CUDA buffer, and call CUDA kernel to\n"
        "               draw a 32x32 pixels black box on left-top of each frame */\n"
        "            HandleEGLImage(&ctx->egl_image);"
    )
    new = (
        "            /* Map EGLImage to a VPI CUDA wrapper and run a minimal perspective warp. */\n"
        "            ret = vpi_warp_egl_image(ctx->egl_image);\n"
        "            if (ret < 0)\n"
        "            {\n"
        '                cerr << "Error while VPI warp on decoder output buffer" << endl;\n'
        "                break;\n"
        "            }"
    )
    if old not in text:
        raise RuntimeError("HandleEGLImage decode block not found")
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
    parser = argparse.ArgumentParser(description="Patch copied MMAPI 02_video_dec_cuda sample to run VPI CUDA warp on decoder output buffer.")
    parser.add_argument("--sample-dir", type=Path, required=True)
    args = parser.parse_args()
    patch_main(args.sample_dir / "videodec_main.cpp")
    patch_makefile(args.sample_dir / "Makefile")
    print(f"patched: {args.sample_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
