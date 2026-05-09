import unittest

from media_engine.rendering import (
    PREMIUM_PRESET,
    build_caption_segments,
    build_premium_render_contract,
    validate_premium_duration,
)


class PremiumRenderingTests(unittest.TestCase):
    def test_premium_contract_contains_review_safe_fields(self):
        candidate = {
            "id": "clip_test",
            "start_ms": 335000,
            "end_ms": 455000,
            "title_hook": "Kenapa Hati Masih Kesepian?",
            "viral_reason": "Momen reflektif yang kuat.",
            "transcript_span": "Allah selalu bersama kita maka hati tidak perlu merasa kesepian.",
        }
        profile = {
            "id": "nourbit",
            "watermark_text": "Nourbit Clips",
            "cta_text": "Follow Nourbit untuk nasihat singkat lainnya",
        }

        contract = build_premium_render_contract(
            candidate,
            profile,
            "runtime/render_test/source.mp4",
            "https://www.youtube.com/live/WSg7MGv4_Fs",
            "Source: Ribath Nouraniyyah Hasyimiyyah",
        )

        self.assertEqual(contract["composition"], "NourbitPremiumShort")
        self.assertEqual(contract["stylePreset"], PREMIUM_PRESET)
        self.assertEqual(contract["width"], 1080)
        self.assertEqual(contract["height"], 1920)
        self.assertTrue(contract["publishSafety"]["reviewRequired"])
        self.assertFalse(contract["publishSafety"]["autoPublishAllowed"])
        self.assertGreater(len(contract["captions"]), 0)

    def test_premium_duration_bounds(self):
        validate_premium_duration(90_000)
        validate_premium_duration(150_000)
        with self.assertRaises(ValueError):
            validate_premium_duration(89_999)
        with self.assertRaises(ValueError):
            validate_premium_duration(150_001)

    def test_caption_segments_fit_duration(self):
        captions = build_caption_segments("satu dua tiga empat lima enam tujuh delapan sembilan", 10_000)
        self.assertEqual(captions[0]["startMs"], 0)
        self.assertLessEqual(captions[-1]["endMs"], 10_000)


if __name__ == "__main__":
    unittest.main()
