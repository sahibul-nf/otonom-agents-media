import unittest

from media_engine.speech_language import (
    asr_cache_language_tag,
    build_transcript_language_list,
    is_auto_language,
    niche_transcript_fallbacks,
    normalize_speech_language,
    whisper_language_arg,
)


class SpeechLanguageTests(unittest.TestCase):
    def test_normalize_defaults_to_auto(self):
        self.assertEqual(normalize_speech_language(None), "auto")
        self.assertEqual(normalize_speech_language(""), "auto")
        self.assertEqual(normalize_speech_language("bad"), "auto")

    def test_whisper_language_arg_auto_is_none(self):
        self.assertIsNone(whisper_language_arg("auto"))
        self.assertEqual(whisper_language_arg("id"), "id")

    def test_asr_cache_tag_distinguishes_auto_from_pinned(self):
        self.assertEqual(asr_cache_language_tag("auto"), "auto")
        self.assertEqual(asr_cache_language_tag("id"), "id")

    def test_is_auto_language(self):
        self.assertTrue(is_auto_language("auto"))
        self.assertFalse(is_auto_language("id"))

    def test_niche_transcript_fallbacks_follow_pack(self):
        self.assertEqual(niche_transcript_fallbacks(niche="kajian"), ("id", "ms", "ar", "en"))
        self.assertEqual(niche_transcript_fallbacks(niche="markets"), ("id", "en"))
        self.assertEqual(niche_transcript_fallbacks(profile_id="nourbit"), ("id", "ms", "ar", "en"))

    def test_build_transcript_language_list_auto_uses_detected_then_niche(self):
        langs = build_transcript_language_list("en", niche="markets", explicit="auto")
        self.assertEqual(langs[:2], ["en", "id"])

    def test_build_transcript_language_list_respects_explicit_pin(self):
        langs = build_transcript_language_list("en", niche="kajian", explicit="ar,id")
        self.assertEqual(langs, ["ar", "id"])

    def test_build_transcript_language_list_auto_without_detected_uses_niche(self):
        langs = build_transcript_language_list(None, niche="kajian", explicit="auto")
        self.assertEqual(langs[:3], ["id", "ms", "ar"])


if __name__ == "__main__":
    unittest.main()
