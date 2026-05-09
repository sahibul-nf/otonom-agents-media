import unittest

from media_engine.curation import SAMPLE_NOURBIT_TRANSCRIPT, curate_dry_run, parse_timecode, parse_transcript


class CurationTests(unittest.TestCase):
    def test_parse_timecode_to_ms(self):
        self.assertEqual(parse_timecode("00:01:05"), 65000)

    def test_parse_transcript(self):
        lines = parse_transcript(SAMPLE_NOURBIT_TRANSCRIPT)
        self.assertGreaterEqual(len(lines), 3)
        self.assertEqual(lines[0].start_ms, 0)

    def test_curate_dry_run_candidate_shape(self):
        candidate = curate_dry_run("nourbit", "source", SAMPLE_NOURBIT_TRANSCRIPT)
        self.assertEqual(candidate["profile_id"], "nourbit")
        self.assertGreater(candidate["end_ms"], candidate["start_ms"])
        self.assertLessEqual(candidate["end_ms"] - candidate["start_ms"], 90000)
        self.assertEqual(candidate["status"], "draft")


if __name__ == "__main__":
    unittest.main()
