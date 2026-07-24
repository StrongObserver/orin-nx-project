from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.patch_mmapi_cuda_encoder_dmabuf_bridge import patch_sample


MAKEFILE = """include ../Rules.mk
SRCS := multivideo_transcode_main.cpp
OBJS := $(SRCS:.cpp=.o)

%.o: %.cpp
\t@echo "Compiling: $<"
\t$(CPP) $(CPPFLAGS) -c $<
"""

MAIN = """#include "multivideo_transcode.h"
static void *
dec_capture_loop_fcn(void *arg)
{
            if (ctx->enc->output_plane.qBuffer(v4l2_buf, NULL) < 0)
            {
                return NULL;
            }
}
"""


class EncoderDmabufBridgePatcherTests(unittest.TestCase):
    def test_patch_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "Makefile").write_text(MAKEFILE, encoding="utf-8")
            (root / "multivideo_transcode_main.cpp").write_text(MAIN, encoding="utf-8")
            patch_sample(root)
            first = {path.name: path.read_bytes() for path in root.iterdir()}
            patch_sample(root)
            second = {path.name: path.read_bytes() for path in root.iterdir()}
            self.assertEqual(first, second)
            main = (root / "multivideo_transcode_main.cpp").read_text(encoding="utf-8")
            makefile = (root / "Makefile").read_text(encoding="utf-8")
            self.assertIn("CUDA_ENCODER_DMABUF_BRIDGE", main)
            self.assertIn("NvBufSurfaceMapEglImage", main)
            self.assertIn("#include <EGL/egl.h>", main)
            self.assertIn("#include <EGL/eglext.h>", main)
            self.assertIn("NvAnalysis.o NvCudaProc.o", makefile)


if __name__ == "__main__":
    unittest.main()
