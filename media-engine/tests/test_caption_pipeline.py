import unittest
from unittest.mock import patch

from media_engine.caption_pipeline import (
    apply_youtube_text,
    asr_initial_prompt,
    build_polish_system_prompt,
    polish_uncertain_words,
)
from media_engine.youtube_pipeline import TranscriptEntry


class CaptionPipelineTests(unittest.TestCase):
    def test_asr_prompt_uses_source_title_not_hardcoded_religion_only(self):
        prompt = asr_initial_prompt(
            {"title_hook": "Uang Itu Kotor?", "transcript_span": "uang bukan hal kotor"},
            source_title="5 Kebohongan Tentang Hidup",
            source_channel="Timothy Ronald",
            niche="tech finance",
        )

        self.assertIn("Timothy Ronald", prompt)
        self.assertIn("Uang Itu Kotor?", prompt)
        self.assertNotEqual(prompt, "Allah, Rasulullah, dzikir, zikir, qalbu, sholawat, istighfar, ma'rifat, taubat, syukur")

    def test_youtube_text_replaces_uncertain_whisper_token_and_keeps_timing(self):
        whisper = [{"text": "wang", "startMs": 0, "endMs": 400, "confidence": 0.4}]
        entries = [TranscriptEntry(1000, 2000, "uang itu")]

        words, meta = apply_youtube_text(whisper, entries, clip_start_ms=1000)

        self.assertEqual(words[0]["text"], "uang")
        self.assertEqual(words[0]["startMs"], 0)
        self.assertEqual(words[0]["endMs"], 400)
        self.assertGreaterEqual(words[0]["confidence"], 0.92)
        self.assertEqual(meta["youtube_replaced"], 1)

    def test_youtube_skips_misaligned_high_confidence_token(self):
        whisper = [
            {"text": "Bitcoin", "startMs": 0, "endMs": 400, "confidence": 0.95},
            {"text": "naik", "startMs": 400, "endMs": 800, "confidence": 0.9},
        ]
        entries = [TranscriptEntry(0, 2000, "the market is rising")]

        words, meta = apply_youtube_text(whisper, entries, clip_start_ms=0)

        self.assertEqual(words[0]["text"], "Bitcoin")
        self.assertGreater(meta.get("youtube_skipped", 0), 0)
        self.assertEqual(meta["youtube_replaced"], 0)

    def test_youtube_absent_leaves_whisper_words(self):
        whisper = [{"text": "wang", "startMs": 0, "endMs": 400, "confidence": 0.4}]

        words, meta = apply_youtube_text(whisper, [], clip_start_ms=0)

        self.assertEqual(words[0]["text"], "wang")
        self.assertEqual(meta["youtube_replaced"], 0)

    def test_llm_polish_replaces_uncertain_token_without_moving_times(self):
        words = [
            {"text": "pilih", "startMs": 0, "endMs": 200, "confidence": 0.9},
            {"text": "bitkon", "startMs": 200, "endMs": 500, "confidence": 0.4},
        ]

        with patch(
            "media_engine.caption_pipeline.call_llm_json",
            return_value={"replacements": [{"index": 1, "text": "Bitcoin"}]},
        ):
            next_words, meta = polish_uncertain_words(words, "deepseek", context="crypto clip")

        self.assertEqual(next_words[1]["text"], "Bitcoin")
        self.assertEqual(next_words[1]["startMs"], 200)
        self.assertEqual(next_words[1]["endMs"], 500)
        self.assertEqual(meta["llm_replacements"], 1)

    def test_llm_polish_skipped_when_provider_none(self):
        words = [{"text": "bitkon", "startMs": 0, "endMs": 200, "confidence": 0.4}]

        next_words, meta = polish_uncertain_words(words, "none")

        self.assertEqual(next_words[0]["text"], "bitkon")
        self.assertTrue(meta["llm_skipped"])

    def test_polish_prompt_uses_tech_domain_for_finance_niche(self):
        prompt = build_polish_system_prompt(detected_language="en", niche="markets", profile_id="workspace")

        self.assertIn("tech, finance", prompt.lower())
        self.assertNotIn("indonesian/arabic asr captions", prompt.lower())

    def test_polish_prompt_uses_devotional_domain_for_nourbit(self):
        prompt = build_polish_system_prompt(detected_language="id", profile_id="nourbit")

        self.assertIn("devotional", prompt.lower())


if __name__ == "__main__":
    unittest.main()
