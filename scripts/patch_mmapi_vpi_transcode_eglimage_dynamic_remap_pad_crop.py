from __future__ import annotations

import argparse
from pathlib import Path

from patch_mmapi_vpi_transcode_eglimage_remap_pad_crop_probe import patch_main as patch_remap_pad_crop_main
from patch_mmapi_vpi_transcode_eglimage_remap_pad_crop_probe import patch_makefile


def patch_dynamic_remap(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "VPI_EGLIMAGE_DYNAMIC_REMAP_PAD_CROP" in text:
        print(f"already dynamic Remap pad/crop patched: {path}")
        return

    old_once = """    if (g_remap_pad_ready)
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

    old_payload_name = "g_remap_pad_payload"
    # Keep the global symbol declared by the baseline patch, but stop relying on
    # it for reuse. Replacing every use would be invasive; instead destroy and
    # recreate it per frame inside the same global handle.
    marker = """    status = vpiCreateRemap(VPI_BACKEND_CUDA, &g_remap_pad_map, &g_remap_pad_payload);
    if (status != VPI_SUCCESS)
    {
        goto fail;
    }

    cerr << "VPI_REMAP_PAD_CROP_PAYLOAD_READY mode=" << g_remap_pad_mode
"""
    replacement = """    {
        float phase = frame_hint * 0.12f;
        float drift = sinf(frame_hint * 0.05f) * std::max(1.0f, width * 0.003f);
        float dyn_amp = std::max(2.0f, width * 0.010f);
        for (int y = 0; y < g_remap_pad_map.numVertPoints; ++y)
        {
            VPIKeypointF32 *row = (VPIKeypointF32 *)((uint8_t *)g_remap_pad_map.keypoints + y * g_remap_pad_map.pitchBytes);
            for (int x = 0; x < g_remap_pad_map.numHorizPoints; ++x)
            {
                row[x].x += drift + dyn_amp * sinf(row[x].y * 2.0f * 3.14159265f / std::max(1U, height) + phase);
            }
        }
    }

    {
        auto payload_t0 = std::chrono::high_resolution_clock::now();
        status = vpiCreateRemap(VPI_BACKEND_CUDA, &g_remap_pad_map, &g_remap_pad_payload);
        auto payload_t1 = std::chrono::high_resolution_clock::now();
        g_dynamic_remap_payload_create_ms = std::chrono::duration<double, std::milli>(payload_t1 - payload_t0).count();
    }
    if (status != VPI_SUCCESS)
    {
        goto fail;
    }

    if (frame_hint <= 5 || frame_hint % 100 == 0)
    {
        cerr << "VPI_DYNAMIC_REMAP_PAYLOAD_READY frame=" << frame_hint
             << " mode=" << g_remap_pad_mode
             << " payload_create_ms=" << g_dynamic_remap_payload_create_ms
             << " width=" << width
"""
    if marker not in text:
        raise RuntimeError("payload creation marker not found")
    text = text.replace(marker, replacement, 1)

    old_log_tail = """         << " width=" << width
         << " height=" << height
         << " grid_width=" << g_remap_pad_map.grid.regionWidth[0]
         << " grid_height=" << g_remap_pad_map.grid.regionHeight[0]
         << " points=" << g_remap_pad_map.numHorizPoints << "x" << g_remap_pad_map.numVertPoints << endl;
    g_remap_pad_ready = true;
    return 0;
"""
    new_log_tail = """             << " height=" << height
             << " grid_width=" << g_remap_pad_map.grid.regionWidth[0]
             << " grid_height=" << g_remap_pad_map.grid.regionHeight[0]
             << " points=" << g_remap_pad_map.numHorizPoints << "x" << g_remap_pad_map.numVertPoints << endl;
    }
    g_remap_pad_ready = true;
    return 0;
"""
    if old_log_tail not in text:
        raise RuntimeError("payload log tail not found")
    text = text.replace(old_log_tail, new_log_tail, 1)

    old_signature = "init_remap_pad_payload_once(uint32_t width, uint32_t height)"
    new_signature = "init_remap_pad_payload_once(uint32_t width, uint32_t height, int frame_hint)"
    text = text.replace(old_signature, new_signature, 1)

    old_call = """    if (init_remap_pad_payload_once(width, height) != 0)
    {
        return -1;
    }
"""
    new_call = """    int current_frame = frame_count + 1;
    if (init_remap_pad_payload_once(width, height, current_frame) != 0)
    {
        return -1;
    }
"""
    if old_call not in text:
        raise RuntimeError("payload init call not found")
    text = text.replace(old_call, new_call, 1)

    if "static double g_dynamic_remap_payload_create_ms" not in text:
        text = text.replace(
            "static uint32_t g_remap_pad_scratch_height = 0;\n",
            "static uint32_t g_remap_pad_scratch_height = 0;\nstatic double g_dynamic_remap_payload_create_ms = 0.0;\n",
            1,
        )

    old_after_submit = """    vpiImageDestroy(output);
    vpiImageDestroy(input);
    vpiStreamDestroy(stream);
    return 0;
"""
    new_after_submit = """    vpiImageDestroy(output);
    vpiImageDestroy(input);
    vpiStreamDestroy(stream);
    vpiPayloadDestroy(g_remap_pad_payload);
    g_remap_pad_payload = NULL;
    vpiWarpMapFreeData(&g_remap_pad_map);
    g_remap_pad_ready = false;
    return 0;
"""
    if old_after_submit not in text:
        raise RuntimeError("success cleanup block not found")
    text = text.replace(old_after_submit, new_after_submit, 1)

    old_fail_cleanup = """    if (output) vpiImageDestroy(output);
    if (input) vpiImageDestroy(input);
    if (stream) vpiStreamDestroy(stream);
    return -1;
}
"""
    new_fail_cleanup = """    if (output) vpiImageDestroy(output);
    if (input) vpiImageDestroy(input);
    if (stream) vpiStreamDestroy(stream);
    if (g_remap_pad_payload)
    {
        vpiPayloadDestroy(g_remap_pad_payload);
        g_remap_pad_payload = NULL;
    }
    vpiWarpMapFreeData(&g_remap_pad_map);
    g_remap_pad_ready = false;
    return -1;
}
"""
    if old_fail_cleanup not in text:
        raise RuntimeError("failure cleanup block not found")
    text = text.replace(old_fail_cleanup, new_fail_cleanup, 1)

    text = text.replace("VPI_EGLIMAGE_REMAP_PAD_CROP frame=", "VPI_EGLIMAGE_DYNAMIC_REMAP_PAD_CROP frame=", 1)
    text = text.replace(
        '" wrapper_call_ms=" << wrapper_call_ms',
        '" payload_create_ms=" << g_dynamic_remap_payload_create_ms\n'
        '                     << " wrapper_call_ms=" << wrapper_call_ms',
        1,
    )
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Patch Remap pad/crop MMAPI sample to recreate VPI Remap payload dynamically per frame.")
    parser.add_argument("--sample-dir", type=Path, required=True)
    args = parser.parse_args()
    cpp = args.sample_dir / "multivideo_transcode_main.cpp"
    patch_remap_pad_crop_main(cpp)
    patch_dynamic_remap(cpp)
    patch_makefile(args.sample_dir / "Makefile")
    print(f"patched dynamic Remap pad/crop transcode: {args.sample_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
