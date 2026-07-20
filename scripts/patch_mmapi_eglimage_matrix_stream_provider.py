from __future__ import annotations

import argparse
from pathlib import Path


STREAM_HELPERS = r'''
static bool g_vpi_matrix_stream_opened = false;
static std::ifstream g_vpi_matrix_stream;
static bool g_vpi_matrix_stream_header_skipped = false;

static bool
read_matrix_from_stream(VpiMatrix3x3 &mat, long &matrix_index)
{
    const char *path = getenv("VPI_MATRIX_FIFO");
    if (path == NULL || path[0] == '\0')
    {
        return false;
    }
    if (!g_vpi_matrix_stream_opened)
    {
        g_vpi_matrix_stream.open(path);
        g_vpi_matrix_stream_opened = true;
        if (!g_vpi_matrix_stream.is_open())
        {
            cerr << "VPI matrix stream could not be opened: " << path << endl;
            return false;
        }
        cerr << "VPI_MATRIX_STREAM_OPENED path=" << path << endl;
    }
    if (!g_vpi_matrix_stream_header_skipped)
    {
        std::string header;
        if (!std::getline(g_vpi_matrix_stream, header))
        {
            return false;
        }
        g_vpi_matrix_stream_header_skipped = true;
    }
    std::string line;
    if (!std::getline(g_vpi_matrix_stream, line))
    {
        return false;
    }
    std::stringstream ss(line);
    std::string cell;
    std::vector<std::string> cells;
    while (std::getline(ss, cell, ','))
    {
        cells.push_back(cell);
    }
    if (cells.size() < 10)
    {
        return false;
    }
    matrix_index = std::stol(cells[0]);
    mat.m[0][0] = std::stof(cells[1]);
    mat.m[0][1] = std::stof(cells[2]);
    mat.m[0][2] = std::stof(cells[3]);
    mat.m[1][0] = std::stof(cells[4]);
    mat.m[1][1] = std::stof(cells[5]);
    mat.m[1][2] = std::stof(cells[6]);
    mat.m[2][0] = std::stof(cells[7]);
    mat.m[2][1] = std::stof(cells[8]);
    mat.m[2][2] = std::stof(cells[9]);
    return true;
}
'''


def patch_main(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "VPI_MATRIX_STREAM_OPENED" in text:
        print(f"already stream-patched: {path}")
        return

    marker = "static int\nvpi_warp_egl_images(EGLImageKHR input_egl, EGLImageKHR output_egl)\n{"
    if marker not in text:
        raise RuntimeError("vpi_warp_egl_images marker not found")
    text = text.replace(marker, STREAM_HELPERS + "\n" + marker, 1)

    old = """    load_vpi_matrices_once();
    VPIPerspectiveTransform xform = {1.0f, 0.002f, 1.0f, -0.002f, 1.0f, -1.0f, 0.0f, 0.0f, 1.0f};
    bool matrix_fallback = false;
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
        }
    }
"""
    new = """    bool use_matrix_stream = false;
    const char *stream_path = getenv("VPI_MATRIX_FIFO");
    if (stream_path != NULL && stream_path[0] != '\\0')
    {
        use_matrix_stream = true;
    }
    if (!use_matrix_stream)
    {
        load_vpi_matrices_once();
    }
    VPIPerspectiveTransform xform = {1.0f, 0.002f, 1.0f, -0.002f, 1.0f, -1.0f, 0.0f, 0.0f, 1.0f};
    bool matrix_fallback = false;
    long matrix_index_log = -1;
    auto matrix_t0 = std::chrono::high_resolution_clock::now();
    if (use_matrix_stream)
    {
        VpiMatrix3x3 stream_mat = {};
        if (read_matrix_from_stream(stream_mat, matrix_index_log))
        {
            memcpy(xform, stream_mat.m, sizeof(xform));
        }
        else
        {
            matrix_fallback = true;
        }
    }
    else if (!g_vpi_matrices.empty())
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
        }
    }
"""
    if old not in text:
        raise RuntimeError("matrix handoff block not found")
    text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")
    print(f"patched EGLImage matrix stream provider: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Patch accepted EGLImage MMAPI sample to read per-frame matrices from VPI_MATRIX_FIFO.")
    parser.add_argument("--sample-dir", type=Path, required=True)
    args = parser.parse_args()
    patch_main(args.sample_dir / "multivideo_transcode_main.cpp")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
