from __future__ import annotations

import argparse
from pathlib import Path


def patch_main(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "MATRIX_HANDOFF frame=" in text:
        print(f"already patched: {path}")
        return

    old = """    if (!g_vpi_matrices.empty())
    {
        size_t matrix_index = static_cast<size_t>(current_frame - 1);
        if (matrix_index < g_vpi_matrices.size())
        {
            memcpy(xform, g_vpi_matrices[matrix_index].m, sizeof(xform));
        }
        else
        {
            xform[0][0] = 1.0f;
            xform[0][1] = 0.0f;
            xform[0][2] = 0.0f;
            xform[1][0] = 0.0f;
            xform[1][1] = 1.0f;
            xform[1][2] = 0.0f;
            xform[2][0] = 0.0f;
            xform[2][1] = 0.0f;
            xform[2][2] = 1.0f;
            if (current_frame <= 5 || current_frame % 100 == 0)
            {
                cerr << "VPI_MATRIX_FALLBACK_IDENTITY frame=" << current_frame << endl;
            }
        }
    }
"""
    new = """    bool matrix_fallback = false;
    long matrix_index_log = -1;
    auto matrix_t0 = std::chrono::high_resolution_clock::now();
    if (!g_vpi_matrices.empty())
    {
        size_t matrix_index = static_cast<size_t>(current_frame - 1);
        matrix_index_log = static_cast<long>(matrix_index);
        if (matrix_index < g_vpi_matrices.size())
        {
            memcpy(xform, g_vpi_matrices[matrix_index].m, sizeof(xform));
        }
        else
        {
            matrix_fallback = true;
            xform[0][0] = 1.0f;
            xform[0][1] = 0.0f;
            xform[0][2] = 0.0f;
            xform[1][0] = 0.0f;
            xform[1][1] = 1.0f;
            xform[1][2] = 0.0f;
            xform[2][0] = 0.0f;
            xform[2][1] = 0.0f;
            xform[2][2] = 1.0f;
            if (current_frame <= 5 || current_frame % 100 == 0)
            {
                cerr << "VPI_MATRIX_FALLBACK_IDENTITY frame=" << current_frame << endl;
            }
        }
    }
    auto matrix_t1 = std::chrono::high_resolution_clock::now();
    double matrix_elapsed_us = std::chrono::duration<double, std::micro>(matrix_t1 - matrix_t0).count();
    if (current_frame <= 5 || current_frame % 30 == 0 || matrix_fallback)
    {
        cerr << "MATRIX_HANDOFF frame=" << current_frame
             << " matrix_index=" << matrix_index_log
             << " fallback=" << (matrix_fallback ? 1 : 0)
             << " elapsed_us=" << matrix_elapsed_us << endl;
    }
"""
    if old not in text:
        raise RuntimeError("matrix selection block not found")
    text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")
    print(f"patched matrix handoff logging: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Patch copied MMAPI VPI matrix sample to log mock online matrix handoff timing.")
    parser.add_argument("--sample-dir", type=Path, required=True)
    args = parser.parse_args()
    patch_main(args.sample_dir / "multivideo_transcode_main.cpp")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
