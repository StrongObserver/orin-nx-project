from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.run_device_stage_endurance import classify_failure, parse_handoff, probe_frame_count


class EnduranceParsingTests(unittest.TestCase):
    def test_parse_handoff_healthy_samples(self) -> None:
        parsed = parse_handoff(
            "\n".join(
                [
                    "MATRIX_HANDOFF frame=1 matrix_index=0 fallback=0 elapsed_us=0.32",
                    "MATRIX_HANDOFF frame=30 matrix_index=29 fallback=0 elapsed_us=1.02",
                    "MATRIX_HANDOFF frame=180 matrix_index=179 fallback=0 elapsed_us=1.06",
                ]
            )
        )
        self.assertEqual(parsed["handoff_samples"], 3)
        self.assertEqual(parsed["fallback_count"], 0)
        self.assertEqual(parsed["frame_index_mismatch_count"], 0)
        self.assertEqual(parsed["max_handoff_frame"], 180)

    def test_parse_handoff_detects_fallback_and_mismatch(self) -> None:
        parsed = parse_handoff(
            "\n".join(
                [
                    "MATRIX_HANDOFF frame=1 matrix_index=-1 fallback=1 elapsed_us=3.2",
                    "MATRIX_HANDOFF frame=30 matrix_index=28 fallback=0 elapsed_us=1.0",
                ]
            )
        )
        self.assertEqual(parsed["fallback_count"], 1)
        self.assertEqual(parsed["frame_index_mismatch_count"], 1)

    def test_classify_failure_healthy(self) -> None:
        reason = classify_failure(
            0,
            True,
            {
                "handoff_samples": 8,
                "fallback_count": 0,
                "frame_index_mismatch_count": 0,
                "max_handoff_frame": 180,
            },
            handoff_required=True,
            readable=1,
            frame_count=180,
            expected_frames=180,
            timing_required=True,
            timing_present=True,
        )
        self.assertEqual(reason, "")

    def test_classify_failure_reports_all_relevant_causes(self) -> None:
        reason = classify_failure(
            7,
            False,
            {
                "handoff_samples": 2,
                "fallback_count": 1,
                "frame_index_mismatch_count": 1,
                "max_handoff_frame": 30,
            },
            handoff_required=True,
            readable=1,
            frame_count=179,
            expected_frames=180,
            timing_required=True,
            timing_present=False,
        )
        self.assertEqual(
            reason,
            "rc=7;success_marker_missing;fallback=1;mismatch=1;frames=179;stage_timing_missing",
        )

    def test_classify_failure_reports_unreadable_without_frame_duplication(self) -> None:
        reason = classify_failure(
            0,
            True,
            {
                "handoff_samples": 0,
                "fallback_count": 0,
                "frame_index_mismatch_count": 0,
                "max_handoff_frame": 0,
            },
            handoff_required=False,
            readable=0,
            frame_count=0,
            expected_frames=180,
            timing_required=False,
            timing_present=False,
        )
        self.assertEqual(reason, "output_unreadable")

    def test_classify_failure_reports_missing_handoff_instrumentation(self) -> None:
        reason = classify_failure(
            0,
            True,
            {
                "handoff_samples": 0,
                "fallback_count": 0,
                "frame_index_mismatch_count": 0,
                "max_handoff_frame": 0,
            },
            handoff_required=True,
            readable=1,
            frame_count=180,
            expected_frames=180,
            timing_required=False,
            timing_present=False,
        )
        self.assertEqual(reason, "handoff_instrumentation_missing")

    def test_probe_frame_count_handles_missing_ffprobe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.h264"
            path.write_bytes(b"not-empty")
            with mock.patch("scripts.run_device_stage_endurance.shutil.which", return_value=None):
                self.assertEqual(probe_frame_count(path), (0, 0))


if __name__ == "__main__":
    unittest.main()
