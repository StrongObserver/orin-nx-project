from __future__ import annotations

import argparse
from pathlib import Path

from patch_mmapi_vpi_transcode_nvbuffer_remap_pad_crop_probe import patch_main as patch_nvbuffer_remap_main
from patch_mmapi_vpi_transcode_nvbuffer_remap_pad_crop_probe import patch_makefile


def patch_dynamic(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "VPI_NVBUFFER_DYNAMIC_REMAP_PAD_CROP" in text:
        print(f"already NvBuffer dynamic Remap patched: {path}")
        return

    old_once = """    if (g_nvbuf_remap_ready)
    {
        return 0;
    }

    const char *mode_env = getenv("VPI_REMAP_MODE");
"""
    new_once = """    const char *mode_env = getenv("VPI_REMAP_MODE");
"""
    if old_once not in text:
        raise RuntimeError("payload-ready early-return block not found")
    text = text.replace(old_once, new_once, 1)

    if "static double g_dynamic_nvbuf_remap_payload_create_ms" not in text:
        text = text.replace(
            "static bool g_nvbuf_remap_scratch_fd_ready = false;\n",
            "static bool g_nvbuf_remap_scratch_fd_ready = false;\nstatic double g_dynamic_nvbuf_remap_payload_create_ms = 0.0;\n",
            1,
        )

    old_signature = "init_nvbuf_remap_payload_once(uint32_t width, uint32_t height)"
    new_signature = "init_nvbuf_remap_payload_once(uint32_t width, uint32_t height, int frame_hint)"
    text = text.replace(old_signature, new_signature, 1)

    marker = """    status = vpiCreateRemap(VPI_BACKEND_CUDA, &g_nvbuf_remap_map, &g_nvbuf_remap_payload);
    if (status != VPI_SUCCESS)
    {
        goto fail;
    }

    cerr << "VPI_NVBUFFER_REMAP_PAD_CROP_PAYLOAD_READY mode=" << g_nvbuf_remap_mode
"""
    replacement = """    {
        float phase = frame_hint * 0.12f;
        float drift = sinf(frame_hint * 0.05f) * std::max(1.0f, width * 0.003f);
        float dyn_amp = std::max(2.0f, width * 0.010f);
        for (int y = 0; y < g_nvbuf_remap_map.numVertPoints; ++y)
        {
            VPIKeypointF32 *row = (VPIKeypointF32 *)((uint8_t *)g_nvbuf_remap_map.keypoints + y * g_nvbuf_remap_map.pitchBytes);
            for (int x = 0; x < g_nvbuf_remap_map.numHorizPoints; ++x)
            {
                row[x].x += drift + dyn_amp * sinf(row[x].y * 2.0f * 3.14159265f / std::max(1U, height) + phase);
            }
        }
    }

    {
        auto payload_t0 = std::chrono::high_resolution_clock::now();
        status = vpiCreateRemap(VPI_BACKEND_CUDA, &g_nvbuf_remap_map, &g_nvbuf_remap_payload);
        auto payload_t1 = std::chrono::high_resolution_clock::now();
        g_dynamic_nvbuf_remap_payload_create_ms = std::chrono::duration<double, std::milli>(payload_t1 - payload_t0).count();
    }
    if (status != VPI_SUCCESS)
    {
        goto fail;
    }

    if (frame_hint <= 5 || frame_hint % 100 == 0)
    {
        cerr << "VPI_NVBUFFER_DYNAMIC_REMAP_PAYLOAD_READY frame=" << frame_hint
             << " mode=" << g_nvbuf_remap_mode
             << " payload_create_ms=" << g_dynamic_nvbuf_remap_payload_create_ms
             << " width=" << width
"""
    if marker not in text:
        raise RuntimeError("payload creation marker not found")
    text = text.replace(marker, replacement, 1)

    old_tail = """         << " width=" << width
         << " height=" << height
         << " grid_width=" << g_nvbuf_remap_map.grid.regionWidth[0]
         << " grid_height=" << g_nvbuf_remap_map.grid.regionHeight[0]
         << " points=" << g_nvbuf_remap_map.numHorizPoints << "x" << g_nvbuf_remap_map.numVertPoints << endl;
    g_nvbuf_remap_ready = true;
    return 0;
"""
    new_tail = """             << " height=" << height
             << " grid_width=" << g_nvbuf_remap_map.grid.regionWidth[0]
             << " grid_height=" << g_nvbuf_remap_map.grid.regionHeight[0]
             << " points=" << g_nvbuf_remap_map.numHorizPoints << "x" << g_nvbuf_remap_map.numVertPoints << endl;
    }
    g_nvbuf_remap_ready = true;
    return 0;
"""
    if old_tail not in text:
        raise RuntimeError("payload log tail not found")
    text = text.replace(old_tail, new_tail, 1)

    old_call = """    if (init_nvbuf_remap_payload_once(width, height) != 0)
    {
        return -1;
    }
"""
    new_call = """    int current_frame = frame_count + 1;
    if (init_nvbuf_remap_payload_once(width, height, current_frame) != 0)
    {
        return -1;
    }
"""
    if old_call not in text:
        raise RuntimeError("payload init call not found")
    text = text.replace(old_call, new_call, 1)

    old_success = """    vpiImageDestroy(output);
    vpiImageDestroy(input);
    vpiStreamDestroy(stream);
    return 0;
"""
    new_success = """    vpiImageDestroy(output);
    vpiImageDestroy(input);
    vpiStreamDestroy(stream);
    vpiPayloadDestroy(g_nvbuf_remap_payload);
    g_nvbuf_remap_payload = NULL;
    vpiWarpMapFreeData(&g_nvbuf_remap_map);
    g_nvbuf_remap_ready = false;
    return 0;
"""
    if old_success not in text:
        raise RuntimeError("success cleanup block not found")
    text = text.replace(old_success, new_success, 1)

    old_fail = """    if (output) vpiImageDestroy(output);
    if (input) vpiImageDestroy(input);
    if (stream) vpiStreamDestroy(stream);
    return -1;
}
"""
    new_fail = """    if (output) vpiImageDestroy(output);
    if (input) vpiImageDestroy(input);
    if (stream) vpiStreamDestroy(stream);
    if (g_nvbuf_remap_payload)
    {
        vpiPayloadDestroy(g_nvbuf_remap_payload);
        g_nvbuf_remap_payload = NULL;
    }
    vpiWarpMapFreeData(&g_nvbuf_remap_map);
    g_nvbuf_remap_ready = false;
    return -1;
}
"""
    if old_fail not in text:
        raise RuntimeError("failure cleanup block not found")
    text = text.replace(old_fail, new_fail, 1)

    text = text.replace("VPI_NVBUFFER_REMAP_PAD_CROP frame=", "VPI_NVBUFFER_DYNAMIC_REMAP_PAD_CROP frame=", 1)
    text = text.replace(
        '" wrapper_call_ms=" << wrapper_call_ms',
        '" payload_create_ms=" << g_dynamic_nvbuf_remap_payload_create_ms\n'
        '                     << " wrapper_call_ms=" << wrapper_call_ms',
        1,
    )
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Patch NvBuffer Remap pad/crop MMAPI sample to recreate Remap payload dynamically per frame.")
    parser.add_argument("--sample-dir", type=Path, required=True)
    args = parser.parse_args()
    cpp = args.sample_dir / "multivideo_transcode_main.cpp"
    patch_nvbuffer_remap_main(cpp)
    patch_dynamic(cpp)
    patch_makefile(args.sample_dir / "Makefile")
    print(f"patched NvBuffer dynamic Remap pad/crop transcode: {args.sample_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
