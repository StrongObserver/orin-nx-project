from __future__ import annotations

import unittest

from scripts.live_matrix_producer import scheduled_prefix_len


class PrefixScheduleTests(unittest.TestCase):
    def test_stride_one_matches_each_prefix(self) -> None:
        self.assertEqual(
            [scheduled_prefix_len(frame, 179, 90, 1) for frame in range(1, 6)],
            [91, 92, 93, 94, 95],
        )

    def test_stride_five_reuses_prefixes(self) -> None:
        self.assertEqual(
            [scheduled_prefix_len(frame, 179, 90, 5) for frame in range(1, 12)],
            [91, 91, 91, 91, 91, 96, 96, 96, 96, 96, 101],
        )

    def test_tail_clamps_to_full_motion_count(self) -> None:
        self.assertEqual(scheduled_prefix_len(88, 179, 90, 5), 176)
        self.assertEqual(scheduled_prefix_len(89, 179, 90, 5), 179)
        self.assertEqual(scheduled_prefix_len(179, 179, 90, 5), 179)

    def test_invalid_arguments_fail(self) -> None:
        with self.assertRaises(ValueError):
            scheduled_prefix_len(0, 179, 90, 5)
        with self.assertRaises(ValueError):
            scheduled_prefix_len(1, 0, 90, 5)


if __name__ == "__main__":
    unittest.main()
