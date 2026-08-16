import unittest

from media_engine.transcript_quality import (
    DEVOTIONAL_GLOSSARY,
    TECH_FINANCE_GLOSSARY,
    correct_asr_words,
    correct_text_with_glossary,
    resolve_glossary,
)


class TranscriptQualityTests(unittest.TestCase):
    def test_resolve_glossary_uses_devotional_pack_for_nourbit(self):
        glossary = resolve_glossary(profile_id="nourbit")

        self.assertIn("alloh", glossary)
        self.assertEqual(glossary["alloh"], DEVOTIONAL_GLOSSARY["alloh"])

    def test_resolve_glossary_uses_tech_pack_for_markets_niche(self):
        glossary = resolve_glossary(profile_id="workspace", niche="markets and AI")

        self.assertIn("bitkon", glossary)
        self.assertNotIn("alloh", glossary)

    def test_resolve_glossary_merges_custom_profile_overrides(self):
        glossary = resolve_glossary(
            profile_id="workspace",
            niche="markets",
            profile={"caption_glossary": {"solana": "Solana"}},
        )

        self.assertEqual(glossary["solana"], "Solana")
        self.assertIn("bitkon", glossary)

    def test_devotional_glossary_fixes_arabic_indonesian_typos(self):
        text = correct_text_with_glossary(
            "Alloh mengingatkan qolbu untuk jikir dan istigfar kepada rosulullah.",
            DEVOTIONAL_GLOSSARY,
        )

        self.assertIn("Allah", text)
        self.assertIn("qalbu", text)
        self.assertIn("dzikir", text)
        self.assertIn("istighfar", text)
        self.assertIn("Rasulullah", text)

    def test_tech_glossary_fixes_crypto_terms(self):
        words, metadata = correct_asr_words(
            [{"text": "bitkon", "confidence": 0.4}],
            glossary=TECH_FINANCE_GLOSSARY,
        )

        self.assertEqual(words[0]["text"], "Bitcoin")
        self.assertEqual(metadata["correction_count"], 1)

    def test_tech_pack_does_not_force_devotional_terms(self):
        words, metadata = correct_asr_words(
            [{"text": "alloh", "confidence": 0.4}],
            glossary=resolve_glossary(profile_id="workspace", niche="tech finance"),
        )

        self.assertEqual(words[0]["text"], "alloh")
        self.assertEqual(metadata["correction_count"], 0)


if __name__ == "__main__":
    unittest.main()
