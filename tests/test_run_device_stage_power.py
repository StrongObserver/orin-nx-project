from __future__ import annotations

import unittest

from scripts.run_device_stage_power import parse_handoff, percentile


class DeviceStagePowerTests(unittest.TestCase):
    def test_handoff_parse(self) -> None:
        fallback, mismatch = parse_handoff(
            "\n".join(
                [
                    "MATRIX_HANDOFF frame=1 matrix_index=0 fallback=0 elapsed_us=2",
                    "MATRIX_HANDOFF frame=30 matrix_index=28 fallback=0 elapsed_us=2",
                    "MATRIX_HANDOFF frame=60 matrix_index=-1 fallback=1 elapsed_us=2",
                ]
            )
        )
        self.assertEqual(fallback, 1)
        self.assertEqual(mismatch, 1)

    def test_percentile_uses_upper_observation(self) -> None:
        self.assertEqual(percentile([1.0, 2.0, 3.0, 4.0], 95), 4.0)


if __name__ == "__main__":
    unittest.main()
