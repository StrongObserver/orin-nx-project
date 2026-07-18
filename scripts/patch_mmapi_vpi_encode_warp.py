from __future__ import annotations

import argparse
from pathlib import Path


VPI_INSERT = r'''
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

    VPIImageData input_data;
    memset(&input_data, 0, sizeof(input_data));
    input_data.bufferType = VPI_IMAGE_BUFFER_CUDA_PITCH_LINEAR;
    input_data.buffer.pitch.format = VPI_IMAGE_FORMAT_Y8_ER;
    input_data.buffer.pitch.numPlanes = 1;
    input_data.buffer.pitch.planes[0].data = (void *)eglFrame.frame.pPitch[0];
    input_data.buffer.pitch.planes[0].width = eglFrame.width;
    input_data.buffer.pitch.planes[0].height = eglFrame.height;
    input_data.buffer.pitch.planes[0].pitchBytes = eglFrame.pitch;

    VPIImage input = NULL;
    VPIImage output = NULL;
    VPIStream stream = NULL;
    VPIImageData output_data = input_data;
    VPIStatus status = VPI_SUCCESS;
    VPIPerspectiveTransform xform = {1.0f, 0.002f, 1.0f, -0.002f, 1.0f, -1.0f, 0.0f, 0.0f, 1.0f};

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
        static int frame_count = 0;
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
    cuGraphicsUnregisterResource(resource);
    return 0;

vpi_fail:
    char msg[VPI_MAX_STATUS_MESSAGE_LENGTH];
    vpiGetLastStatusMessage(msg, sizeof(msg));
    cerr << "VPI encode warp failed status=" << status << " msg=" << msg << endl;
    if (output) vpiImageDestroy(output);
    if (input) vpiImageDestroy(input);
    if (stream) vpiStreamDestroy(stream);
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
        "#include <cuda.h>\n"
        "#include <cuda_runtime.h>\n"
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
