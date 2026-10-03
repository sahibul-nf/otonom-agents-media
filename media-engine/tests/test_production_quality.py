import unittest

from media_engine.asr import words_from_faster_whisper_segments
from media_engine.caption_composer import compose_caption_groups
from media_engine.transcript_quality import resolve_glossary
from media_engine.costs import estimate_clip_cost
from media_engine.render_quality import build_render_quality_report


class MockWord:
    def __init__(self, word, start, end, probability=0.9):
        self.word = word
        self.start = start
        self.end = end
        self.probability = probability


class MockSegment:
    def __init__(self, words):
        self.words = words


class ProductionQualityTests(unittest.TestCase):
    def test_asr_adapter_maps_words_to_ms(self):
        words = words_from_faster_whisper_segments(
            [MockSegment([MockWord(" Allah", 0.1, 0.5), MockWord(" dekat", 0.5, 0.9)])]
        )

        self.assertEqual(words[0]["text"], "Allah")
        self.assertEqual(words[0]["startMs"], 100)
        self.assertEqual(words[1]["endMs"], 900)

    def test_caption_composer_creates_non_overlapping_groups(self):
        captions, metadata = compose_caption_groups(
            [
                {"text": "Alloh", "startMs": 0, "endMs": 300, "confidence": 0.8},
                {"text": "dekat", "startMs": 300, "endMs": 700, "confidence": 0.9},
                {"text": "qolbu", "startMs": 1600, "endMs": 1900, "confidence": 0.7},
            ],
            max_words_per_caption=2,
            glossary=resolve_glossary("nourbit"),
        )

        self.assertEqual(captions[0]["text"], "Allah dekat")
        self.assertEqual(captions[1]["text"], "qalbu")
        self.assertLessEqual(captions[0]["endMs"], captions[1]["startMs"])
        self.assertEqual(metadata["caption_count"], 2)

    def test_render_quality_penalizes_overlap(self):
        report = build_render_quality_report(
            {
                "durationMs": 2000,
                "captionEvents": [
                    {"startMs": 0, "endMs": 1000},
                    {"startMs": 900, "endMs": 1600},
                ],
            },
            "/tmp/out.mp4",
        )

        self.assertEqual(report["caption_overlap_count"], 1)
        self.assertLess(report["quality_score"], 100)

    def test_cost_estimator_is_deterministic(self):
        cost = estimate_clip_cost(60_000, llm_provider="deepseek", caption_source="whisper", renderer="remotion")

        self.assertEqual(cost["currency"], "USD")
        self.assertGreater(cost["estimated_total"], 0)
        self.assertEqual(cost["cloud_asr_cost"], 0.0)


if __name__ == "__main__":
    unittest.main()
