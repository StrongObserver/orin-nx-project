from __future__ import annotations

import unittest

import numpy as np

from scripts.make_yuv420_reference import chroma_matrix


class ChromaMatrixTests(unittest.TestCase):
    def test_identity_remains_identity(self) -> None:
        matrix = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float32)
        np.testing.assert_allclose(chroma_matrix(matrix), matrix)

    def test_even_translation_scales_by_half(self) -> None:
        matrix = np.array([[1.0, 0.0, -8.0], [0.0, 1.0, -4.0]], dtype=np.float32)
        expected = np.array([[1.0, 0.0, -4.0], [0.0, 1.0, -2.0]], dtype=np.float32)
        np.testing.assert_allclose(chroma_matrix(matrix), expected)

    def test_pixel_center_offset_is_preserved_for_affine(self) -> None:
        matrix = np.array([[0.99, 0.02, -3.0], [-0.02, 0.99, 4.0]], dtype=np.float32)
        result = chroma_matrix(matrix)
        self.assertAlmostEqual(float(result[0, 2]), -1.4975, places=6)
        self.assertAlmostEqual(float(result[1, 2]), 1.9925, places=6)


if __name__ == "__main__":
    unittest.main()
