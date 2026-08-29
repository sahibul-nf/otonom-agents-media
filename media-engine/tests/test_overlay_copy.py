import unittest

from media_engine.hyperframes_recipes import LayoutContext, get_recipe
from media_engine.overlay_copy import (
    FORBIDDEN_OVERLAY_COPY,
    heuristic_overlay_slots,
    merge_overlay_slots,
    overlay_slots_for_candidate,
)
from media_engine.rendering import build_premium_render_contract
from media_engine.youtube_pipeline import TranscriptEntry, build_candidate


def _layout() -> LayoutContext:
    return LayoutContext(
        width=1080,
        height=1920,
        is_landscape=False,
        caption_font_size=54,
        text_color="#ffffff",
        highlight_color="#d8b45f",
        accent="#d8b45f",
        secondary_accent="#f8fafc",
    )


def _candidate(**overrides):
    payload = {
        "id": "clip_overlay",
        "start_ms": 0,
        "end_ms": 60_000,
        "title_hook": "Fed pivot changes the tape",
        "hook_subtitle": "Rates still lead risk",
        "viral_reason": "Reason",
        "transcript_span": "Fed pivot changes the tape",
        "timed_captions": [
            {
                "text": "Fed pivot",
                "startMs": 0,
                "endMs": 60_000,
                "words": [
                    {"text": "Fed", "startMs": 0, "endMs": 30_000},
                    {"text": "pivot", "startMs": 30_000, "endMs": 60_000},
                ],
            }
        ],
    }
    payload.update(overrides)
    return payload


class OverlayCopyTests(unittest.TestCase):
    def test_heuristic_slots_from_title_and_subtitle(self):
        slots = heuristic_overlay_slots("Fed pivot changes the tape", "Rates still lead risk")
        self.assertEqual(slots["headline"], "Fed pivot changes the tape")
        self.assertEqual(slots["subhead"], "Rates still lead risk")
        self.assertEqual(slots["kicker"], "Fed")
        self.assertNotIn(slots["headline"].lower(), FORBIDDEN_OVERLAY_COPY)

    def test_forbidden_llm_overlay_is_ignored(self):
        merged = merge_overlay_slots(
            heuristic_overlay_slots("Fed pivot changes the tape", "Rates still lead risk"),
            {"headline": "More clarity", "stamp": "MUSTARD MODE"},
        )
        self.assertEqual(merged["headline"], "Fed pivot changes the tape")
        self.assertNotEqual(merged.get("stamp", "").lower(), "mustard mode")

    def test_quintessence_uses_title_not_dummy(self):
        html = get_recipe("quintessence_serif").render_overlay(
            {"titleHook": "Fed pivot changes the tape", "hookSubtitle": "Rates still lead risk"},
            {"id": "quintessence_serif"},
            _layout(),
        )
        self.assertIn("Fed", html)
        self.assertNotIn("More clarity", html)

    def test_velocity_uses_title_not_dummy(self):
        html = get_recipe("velocity_business_promo").render_overlay(
            {"titleHook": "Fed pivot changes the tape", "hookSubtitle": "Rates still lead risk"},
            {"id": "velocity_business_promo"},
            _layout(),
        )
        self.assertIn("Fed pivot changes the tape", html)
        self.assertNotIn("BOOST YOUR BUSINESS", html)

    def test_techtalk_keeps_title_and_brand(self):
        html = get_recipe("techtalk_intel_brief").render_overlay(
            {
                "titleHook": "Bitcoin is scarce",
                "hookSubtitle": "21 juta unit",
                "watermarkText": "TechTalk",
            },
            {"id": "techtalk_intel_brief"},
            _layout(),
        )
        self.assertIn("Bitcoin is scarce", html)
        self.assertIn("TechTalk", html)

    def test_render_contract_includes_overlay_slots(self):
        contract = build_premium_render_contract(
            _candidate(),
            {"id": "workspace", "watermark_text": "", "cta_text": ""},
            "source.mp4",
            "https://youtu.be/test",
            "Source",
        )
        self.assertEqual(contract["overlay"]["headline"], "Fed pivot changes the tape")
        self.assertNotIn("more clarity", " ".join(contract["overlay"].values()).lower())

    def test_build_candidate_stores_overlay_slots(self):
        entries = [
            TranscriptEntry(index * 1000, (index + 1) * 1000, "fed pivot changes the tape for markets")
            for index in range(70)
        ]
        candidate = build_candidate(
            "workspace",
            "source",
            entries,
            0,
            60_000,
            1,
            {"caption": {"max_words_per_caption": 3}, "ai": {"remove_filler_words": False}},
            llm_provider="none",
        )
        self.assertTrue(candidate["overlay_slots"]["headline"])
        self.assertEqual(candidate["curation_metadata"]["overlay_slots"], candidate["overlay_slots"])

    def test_stale_persisted_overlay_is_ignored_when_title_changes(self):
        slots = overlay_slots_for_candidate(
            {
                "title_hook": "Zuhud itu Kaya atau Miskin?",
                "hook_subtitle": "Nasihat singkat soal zuhud.",
                "curation_metadata": {
                    "overlay_slots": {"headline": "Secara Fitrah, Kita Tidak Bisa Berarti Kaya Saja?"},
                },
            },
        )
        self.assertEqual(slots["headline"], "Zuhud itu Kaya atau Miskin?")

    def test_persisted_metadata_overlay_kept_when_it_matches_title(self):
        slots = overlay_slots_for_candidate(
            {
                "title_hook": "Fed pivot changes the tape",
                "hook_subtitle": "Rates still lead risk",
                "curation_metadata": {"overlay_slots": {"headline": "Fed pivot changes the tape"}},
            },
            {"overlay": {"headline": "More clarity"}},
        )
        self.assertEqual(slots["headline"], "Fed pivot changes the tape")


if __name__ == "__main__":
    unittest.main()
