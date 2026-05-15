import unittest

from media_engine.caption_edits import merge_caption_corrections, normalize_edited_captions


class CaptionEditTests(unittest.TestCase):
    def test_normalizes_manual_caption_text_and_preserves_timing(self):
        captions = normalize_edited_captions(
            [
                {"text": "  Allah   tidak pernah   jauh ", "startMs": 0, "endMs": 1200, "words": [{"text": "wrong"}]},
                {"text": "Qalbu perlu dzikir", "startMs": 1200, "endMs": 2400},
            ]
        )

        self.assertEqual(captions[0]["text"], "Allah tidak pernah jauh")
        self.assertEqual(captions[0]["startMs"], 0)
        self.assertEqual(captions[0]["endMs"], 1200)
        self.assertNotIn("words", captions[0])
        self.assertEqual(captions[1]["timestampMs"], 1200)

    def test_rejects_empty_caption_edits(self):
        with self.assertRaises(ValueError):
            normalize_edited_captions([{"text": "", "startMs": 0, "endMs": 1000}])

    def test_merge_preserves_automatic_correction_metadata(self):
        merged = merge_caption_corrections(
            {"correction_count": 3},
            [{"text": "Rasulullah", "startMs": 100, "endMs": 900}],
        )

        self.assertTrue(merged["manual_edit"])
        self.assertEqual(merged["correction_count"], 3)
        self.assertEqual(merged["edited_caption_count"], 1)
        self.assertEqual(merged["edited_captions"][0]["text"], "Rasulullah")


if __name__ == "__main__":
    unittest.main()
