from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.patch_video_cuda_enc_yuv420_verifier import patch_sample


MAKEFILE = """include ../Rules.mk
OBJS += \\
\t$(ALGO_CUDA_DIR)/NvAnalysis.o \\
\t$(ALGO_CUDA_DIR)/NvCudaProc.o

%.o: %.cpp
\t@echo "Compiling: $<"
\t$(CPP) $(CPPFLAGS) -c $<
"""

MAIN = """int render_rect(context_t *ctx) {
    HandleEGLImage(&ctx->eglimg);
    return 0;
}
"""


class Yuv420PatcherTests(unittest.TestCase):
    def test_patch_is_idempotent_and_local(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "Makefile").write_text(MAKEFILE, encoding="utf-8")
            (root / "video_cuda_enc_main.cpp").write_text(MAIN, encoding="utf-8")
            patch_sample(root)
            first = {path.name: path.read_bytes() for path in root.iterdir()}
            patch_sample(root)
            second = {path.name: path.read_bytes() for path in root.iterdir()}
            self.assertEqual(first, second)
            makefile = (root / "Makefile").read_text(encoding="utf-8")
            main = (root / "video_cuda_enc_main.cpp").read_text(encoding="utf-8")
            cuda = (root / "NvAnalysis.cu").read_text(encoding="utf-8")
            self.assertIn("NvAnalysis.o: NvAnalysis.cu", makefile)
            self.assertNotIn("$(ALGO_CUDA_DIR)/NvAnalysis.o", makefile)
            self.assertIn("CUDA_YUV420_HANDLE_FAILURE", main)
            self.assertIn("frame->planeCount != 2 && frame->planeCount != 3", cuda)
            self.assertIn("frame->frame.pPitch[plane]", cuda)
            self.assertIn("planeParams.pitch[1]", main)
            self.assertIn("visible_height", cuda)
            self.assertIn('strcmp(mode, "noop")', cuda)


if __name__ == "__main__":
    unittest.main()
