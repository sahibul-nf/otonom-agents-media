import unittest
from unittest.mock import patch

from media_engine.genres import (
    UNIVERSAL_CATALOG,
    genre_catalog,
    genre_options,
    genre_prompt_phrase,
    normalize_genres,
    resolve_genre_pack,
    uses_devotional_tone,
    workspace_curation_context,
)
from media_engine.youtube_pipeline import TranscriptEntry, llm_rank_suggestions


class GenrePackTests(unittest.TestCase):
    def test_pack_follows_workspace_not_product(self):
        self.assertEqual(resolve_genre_pack("nourbit"), "devotional")
        self.assertEqual(resolve_genre_pack("workspace"), "general")
        self.assertEqual(resolve_genre_pack("acme", "SaaS tips for builders"), "tech_finance")
        self.assertEqual(resolve_genre_pack("masjid", "Islamic lecture clips"), "devotional")

    def test_catalog_is_universal_angles(self):
        nourbit = [item["id"] for item in genre_options(profile_id="nourbit")]
        workspace = [item["id"] for item in genre_options(profile_id="workspace")]
        techtalk = genre_catalog(profile_id="techtalk", niche="TechTalk Intel finance")
        self.assertEqual(tuple(nourbit), UNIVERSAL_CATALOG)
        self.assertEqual(nourbit, workspace)
        self.assertNotIn("kajian", [item["id"] for item in techtalk["options"]])
        self.assertNotIn("markets", [item["id"] for item in techtalk["options"]])
        self.assertEqual(techtalk["defaults"], ["advice", "opinion", "explainer"])
        self.assertIn("story", nourbit)

    def test_empty_genres_use_angle_defaults_not_niche_chips(self):
        self.assertEqual(
            normalize_genres(None, profile_id="workspace"),
            ["story", "advice", "social_commentary"],
        )
        self.assertEqual(
            normalize_genres("", profile_id="nourbit"),
            ["story", "advice", "social_commentary"],
        )
        self.assertEqual(
            normalize_genres([], profile_id="studio", niche="tech finance"),
            ["advice", "opinion", "explainer"],
        )

    def test_unknown_ids_do_not_fall_back_to_kajian(self):
        self.assertEqual(normalize_genres(["story", "unknown", "story"], profile_id="workspace"), ["story"])
        self.assertEqual(
            normalize_genres(["not-a-genre"], profile_id="workspace"),
            ["story", "advice", "social_commentary"],
        )

    def test_legacy_ids_still_parse(self):
        self.assertEqual(normalize_genres(["markets", "advice"]), ["markets", "advice"])

    def test_prompt_phrase_and_devotional_tone_from_niche(self):
        self.assertEqual(genre_prompt_phrase(["advice", "opinion"]), "Advice, Opinion")
        self.assertFalse(uses_devotional_tone(["advice"], profile_id="workspace"))
        self.assertTrue(uses_devotional_tone(["advice"], profile_id="nourbit"))
        self.assertTrue(uses_devotional_tone(["kajian"]))

    def test_workspace_context_for_curation(self):
        text = workspace_curation_context("TechTalk Intel", "tech & finance edutainment")
        self.assertIn("TechTalk Intel", text)
        self.assertIn("tech & finance", text)

    def test_llm_prompt_uses_workspace_niche_not_custom_chips(self):
        captured: dict[str, str] = {}

        def fake_llm(_provider: str, system: str, user: str):
            captured["system"] = system
            captured["user"] = user
            return {"clips": []}

        entries = [TranscriptEntry(index * 1000, (index + 1) * 1000, "pasar AI bisnis") for index in range(20)]
        with patch("media_engine.youtube_pipeline.call_llm_json", side_effect=fake_llm):
            llm_rank_suggestions(
                entries,
                2,
                "deepseek",
                genres=["advice", "opinion"],
                profile_id="workspace",
                niche="tech & finance for builders",
                workspace_name="TechTalk Intel",
            )

        self.assertNotIn("Nourbit", captured["system"])
        self.assertIn("TechTalk Intel", captured["user"])
        self.assertIn("tech & finance for builders", captured["user"])
        self.assertNotIn("spiritual", captured["user"].lower())
        self.assertIn("Opinion", captured["user"])


if __name__ == "__main__":
    unittest.main()
