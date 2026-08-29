import unittest

from media_engine.captions import (
    align_caption_timeline_start,
    captions_out_of_sync,
    captions_timeline_uses_source_offset,
    normalize_caption_timeline_for_render,
    rebase_captions_to_clip_zero,
)


class CaptionAlignTests(unittest.TestCase):
    def test_align_shifts_late_first_caption_near_zero(self):
        captions = [
            {
                "text": "assalamualaikum",
                "startMs": 2800,
                "endMs": 3600,
                "words": [
                    {"text": "assalamualaikum", "startMs": 2800, "endMs": 3600},
                ],
            }
        ]
        aligned = align_caption_timeline_start(captions)
        self.assertEqual(aligned[0]["startMs"], 120)
        self.assertEqual(aligned[0]["words"][0]["startMs"], 120)

    def test_align_keeps_captions_when_first_word_is_already_early(self):
        captions = [
            {
                "text": "halo",
                "startMs": 80,
                "endMs": 500,
                "words": [{"text": "halo", "startMs": 80, "endMs": 500}],
            }
        ]
        aligned = align_caption_timeline_start(captions)
        self.assertEqual(aligned[0]["startMs"], 80)

    def test_detects_absolute_source_timeline(self):
        captions = [
            {
                "text": "kajian",
                "startMs": 125_400,
                "endMs": 126_000,
                "words": [{"text": "kajian", "startMs": 125_400, "endMs": 126_000}],
            }
        ]
        self.assertTrue(captions_timeline_uses_source_offset(captions, 125_000))

    def test_rebase_absolute_timeline_to_clip_zero(self):
        captions = [
            {
                "text": "awal",
                "startMs": 125_000,
                "endMs": 125_500,
                "words": [{"text": "awal", "startMs": 125_000, "endMs": 125_500}],
            },
            {
                "text": "tengah",
                "startMs": 130_000,
                "endMs": 130_800,
                "words": [{"text": "tengah", "startMs": 130_000, "endMs": 130_800}],
            },
        ]
        rebased = rebase_captions_to_clip_zero(captions, 125_000)
        self.assertEqual(rebased[1]["startMs"], 5_000)
        self.assertEqual(rebased[1]["words"][0]["startMs"], 5_000)

    def test_normalize_rebases_then_aligns_leading_dead_air(self):
        captions = [
            {
                "text": "kajian",
                "startMs": 125_800,
                "endMs": 126_400,
                "words": [{"text": "kajian", "startMs": 125_800, "endMs": 126_400}],
            }
        ]
        normalized = normalize_caption_timeline_for_render(captions, clip_start_ms=125_000)
        self.assertEqual(normalized[0]["startMs"], 120)
        self.assertEqual(normalized[0]["words"][0]["startMs"], 120)

    def test_out_of_sync_when_caption_span_exceeds_media(self):
        captions = [
            {
                "text": "late",
                "startMs": 40_000,
                "endMs": 95_000,
                "words": [{"text": "late", "startMs": 40_000, "endMs": 95_000}],
            }
        ]
        self.assertTrue(captions_out_of_sync(captions, video_ms=60_000))

    def test_out_of_sync_when_many_captions_end_far_before_media(self):
        captions = [
            {"text": f"line {index}", "startMs": index * 2000, "endMs": index * 2000 + 800}
            for index in range(8)
        ]
        self.assertTrue(captions_out_of_sync(captions, video_ms=60_000))


if __name__ == "__main__":
    unittest.main()
