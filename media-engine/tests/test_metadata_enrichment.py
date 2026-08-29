import unittest
from unittest.mock import patch

from media_engine.metadata_refresh import (
    enrich_candidate_metadata,
    metadata_editor_system_prompt,
    needs_metadata_enrichment,
)
from media_engine.youtube_pipeline import hook_subtitle_for_span, title_for_span


class MetadataEnrichmentTests(unittest.TestCase):
    def test_fragment_span_title_uses_clause_boundary(self):
        span = (
            "itu adalah apa maksudnya mujahadah sebelum kita disiksa oleh keadaan "
            "maka siksa diri sebelum disiksa oleh hawa nafsu"
        )
        title = title_for_span(span)
        subtitle = hook_subtitle_for_span(span, title)

        self.assertGreaterEqual(len(title.split()), 4)
        self.assertNotIn("ringkasan isi clip:", subtitle.lower())

    def test_needs_enrichment_for_heuristic_sources(self):
        self.assertTrue(
            needs_metadata_enrichment(
                {"curation_metadata": {"title_source": "heuristic_span", "subtitle_source": "heuristic_span"}}
            )
        )
        self.assertFalse(
            needs_metadata_enrichment(
                {"curation_metadata": {"title_source": "llm_deepseek", "subtitle_source": "llm_deepseek"}}
            )
        )

    def test_enrich_candidate_metadata_uses_llm_when_available(self):
        candidate = {
            "profile_id": "techtalk",
            "transcript_span": "Kenapa inflasi AS masih bandel meski suku bunga sudah naik?",
            "title_hook": "Kenapa Inflasi AS Masih",
            "hook_subtitle": "Ringkasan isi clip: inflasi naik.",
            "curation_metadata": {"title_source": "heuristic_span", "subtitle_source": "heuristic_span"},
            "start_ms": 0,
            "end_ms": 60_000,
        }
        with patch("media_engine.metadata_refresh.available_metadata_provider", return_value="deepseek"), patch(
            "media_engine.metadata_refresh.call_llm_json",
            return_value={
                "title_hook": "Kenapa Inflasi AS Masih Bandel?",
                "hook_subtitle": "Suku bunga naik, tapi harga belum turun.",
                "viral_reason": "Pertanyaan langsung soal inflasi dan kebijakan moneter.",
            },
        ):
            enrich_candidate_metadata(
                candidate,
                llm_provider="deepseek",
                profile_id="techtalk",
                niche="tech_finance",
                workspace_name="TechTalk Intel",
            )

        self.assertEqual(candidate["title_hook"], "Kenapa Inflasi AS Masih Bandel?")
        self.assertEqual(candidate["curation_metadata"]["title_source"], "llm_deepseek")

    def test_metadata_editor_prompt_is_niche_aware(self):
        devotional = metadata_editor_system_prompt(profile_id="nourbit", niche="islamic")
        tech = metadata_editor_system_prompt(profile_id="techtalk", niche="tech_finance")

        self.assertIn("Islamic", devotional)
        self.assertIn("tech and finance", tech)


if __name__ == "__main__":
    unittest.main()
