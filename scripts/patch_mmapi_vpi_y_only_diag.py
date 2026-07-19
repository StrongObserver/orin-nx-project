from __future__ import annotations

import argparse
from pathlib import Path


def patch_main(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "VPI_Y_ONLY_DIAG enabled" in text:
        print(f"already patched: {path}")
        return

    old = """    input_data.buffer.pitch.format = is_nv12_semiplanar ? VPI_IMAGE_FORMAT_NV12_ER : VPI_IMAGE_FORMAT_Y8_ER;
    input_data.buffer.pitch.numPlanes = is_nv12_semiplanar ? 2 : 1;
    input_data.buffer.pitch.planes[0].data = (void *)eglFrame.frame.pPitch[0];
"""
    new = """    bool y_only_diag = false;
    const char *y_only_env = getenv("VPI_Y_ONLY_DIAG");
    if (is_nv12_semiplanar && y_only_env != NULL && y_only_env[0] != '\\0' && y_only_env[0] != '0')
    {
        y_only_diag = true;
        static bool printed_y_only_diag = false;
        if (!printed_y_only_diag)
        {
            cerr << "VPI_Y_ONLY_DIAG enabled: warp Y plane only and keep original UV plane" << endl;
            printed_y_only_diag = true;
        }
    }
    input_data.buffer.pitch.format = y_only_diag ? VPI_IMAGE_FORMAT_Y8_ER : (is_nv12_semiplanar ? VPI_IMAGE_FORMAT_NV12_ER : VPI_IMAGE_FORMAT_Y8_ER);
    input_data.buffer.pitch.numPlanes = y_only_diag ? 1 : (is_nv12_semiplanar ? 2 : 1);
    input_data.buffer.pitch.planes[0].data = (void *)eglFrame.frame.pPitch[0];
"""
    if old not in text:
        raise RuntimeError("input_data format block not found")
    text = text.replace(old, new, 1)

    text = text.replace(
        "    if (is_nv12_semiplanar)\n    {\n        input_data.buffer.pitch.planes[1].data = (void *)eglFrame.frame.pPitch[1];",
        "    if (is_nv12_semiplanar && !y_only_diag)\n    {\n        input_data.buffer.pitch.planes[1].data = (void *)eglFrame.frame.pPitch[1];",
        1,
    )
    text = text.replace(
        "    if (is_nv12_semiplanar)\n    {\n        cuda_status = cudaMallocPitch((void **)&scratch_uv_dev, &scratch_uv_pitch, eglFrame.width, eglFrame.height / 2);",
        "    if (is_nv12_semiplanar && !y_only_diag)\n    {\n        cuda_status = cudaMallocPitch((void **)&scratch_uv_dev, &scratch_uv_pitch, eglFrame.width, eglFrame.height / 2);",
        1,
    )
    text = text.replace(
        "    if (is_nv12_semiplanar)\n    {\n        output_data.buffer.pitch.planes[1].data = scratch_uv_dev;",
        "    if (is_nv12_semiplanar && !y_only_diag)\n    {\n        output_data.buffer.pitch.planes[1].data = scratch_uv_dev;",
        1,
    )
    text = text.replace(
        "        if (is_nv12_semiplanar)\n        {\n            cuda_status = cudaMemcpy2D((void *)eglFrame.frame.pPitch[1], eglFrame.pitch,",
        "        if (is_nv12_semiplanar && !y_only_diag)\n        {\n            cuda_status = cudaMemcpy2D((void *)eglFrame.frame.pPitch[1], eglFrame.pitch,",
        1,
    )

    old_sync = """        auto t1 = std::chrono::high_resolution_clock::now();
        static double total_ms = 0.0;
"""
    new_sync = """        cuda_status = cudaDeviceSynchronize();
        if (cuda_status != cudaSuccess)
        {
            cerr << "cudaDeviceSynchronize after VPI warp failed: " << cudaGetErrorString(cuda_status) << endl;
            goto vpi_fail;
        }
        auto t1 = std::chrono::high_resolution_clock::now();
        static double total_ms = 0.0;
"""
    if old_sync not in text:
        raise RuntimeError("post-copy timing block not found")
    text = text.replace(old_sync, new_sync, 1)

    path.write_text(text, encoding="utf-8")
    print(f"patched y-only diagnostic: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Patch MMAPI VPI matrix sample with VPI_Y_ONLY_DIAG mode.")
    parser.add_argument("--sample-dir", type=Path, required=True)
    args = parser.parse_args()
    patch_main(args.sample_dir / "multivideo_transcode_main.cpp")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
