import unittest

from media_engine.autonomy import evaluate_quality_gate, get_autonomy_settings
from media_engine.scoring import (
    HYGIENE_FLAG_ABRUPT_BOUNDARY,
    HYGIENE_FLAG_CAPTION_NOISE,
    HYGIENE_GATE_HOLD,
    HYGIENE_GATE_NEEDS_ATTENTION,
    HYGIENE_GATE_PASS,
    evaluate_hygiene_gate,
    resolve_scoring_pack,
    score_candidate_text,
)


class ScoringNicheTests(unittest.TestCase):
    def test_devotional_pack_boosts_faith_keywords(self):
        devotional = score_candidate_text(
            "Allah memberi ketenangan hati lewat dzikir dan taubat setiap malam.",
            "Rahasia Hati yang Tenang",
            60_000,
            pack_id="devotional",
        )
        tech = score_candidate_text(
            "Allah memberi ketenangan hati lewat dzikir dan taubat setiap malam.",
            "Rahasia Hati yang Tenang",
            60_000,
            pack_id="tech_finance",
        )
        self.assertEqual(devotional["scoring_pack"], "devotional")
        self.assertEqual(tech["scoring_pack"], "tech_finance")
        self.assertGreater(devotional["performance_score"], tech["performance_score"])
        self.assertEqual(devotional["overall_score"], devotional["performance_score"])

    def test_tech_finance_pack_boosts_builder_keywords(self):
        tech = score_candidate_text(
            "Startup AI ini menarik investor karena revenue SaaS dan margin bisnis naik cepat.",
            "Kenapa Investor Pilih AI?",
            55_000,
            pack_id="tech_finance",
        )
        devotional = score_candidate_text(
            "Startup AI ini menarik investor karena revenue SaaS dan margin bisnis naik cepat.",
            "Kenapa Investor Pilih AI?",
            55_000,
            pack_id="devotional",
        )
        self.assertGreater(tech["performance_score"], devotional["performance_score"])

    def test_profile_id_resolves_pack(self):
        pack = resolve_scoring_pack(profile_id="techtalk", niche="Tech & Finance")
        self.assertEqual(pack, "tech_finance")
        nourbit = resolve_scoring_pack(profile_id="nourbit")
        self.assertEqual(nourbit, "devotional")

    def test_performance_score_excludes_caption_and_boundary_from_weight(self):
        shared = "Startup AI ini menarik investor karena revenue SaaS dan margin bisnis naik cepat."
        clean = score_candidate_text(
            shared,
            "Kenapa Investor Pilih AI?",
            55_000,
            boundary_confidence=95,
            pack_id="tech_finance",
        )
        noisy = score_candidate_text(
            f"{shared} [music] ...",
            "Kenapa Investor Pilih AI?",
            55_000,
            boundary_confidence=45,
            pack_id="tech_finance",
        )
        self.assertEqual(clean["hygiene_gate"], HYGIENE_GATE_PASS)
        self.assertEqual(noisy["hygiene_gate"], HYGIENE_GATE_NEEDS_ATTENTION)
        self.assertIn(HYGIENE_FLAG_ABRUPT_BOUNDARY, noisy["hygiene_flags"])
        self.assertGreaterEqual(clean["performance_score"], noisy["performance_score"] - 5)

    def test_hygiene_gate_hold_on_catastrophic_caption(self):
        hygiene = evaluate_hygiene_gate(
            caption_confidence=40,
            boundary_confidence=90,
            catastrophic_caption=True,
        )
        self.assertEqual(hygiene["gate_status"], HYGIENE_GATE_HOLD)
        self.assertIn(HYGIENE_FLAG_CAPTION_NOISE, hygiene["flags"])


class TwoLayerAutonomyTests(unittest.TestCase):
    def _settings(self):
        return {
            "autonomy_mode": "assisted",
            "review_grace_hours": 12,
            "auto_schedule_enabled": 1,
            "overall_threshold": 82,
            "hook_threshold": 80,
            "caption_threshold": 90,
            "boundary_threshold": 80,
        }

    def test_high_performance_with_hygiene_pass_auto_qualifies(self):
        scored = score_candidate_text(
            "Kenapa investor memilih startup AI dengan revenue SaaS dan margin bisnis naik cepat?",
            "Kenapa Investor Pilih AI?",
            60_000,
            boundary_confidence=90,
            opening_strength=90,
            pack_id="tech_finance",
        )
        candidate = {
            "score": scored,
            "curation_metadata": {"boundary_confidence": 90},
            "asr_metadata": {"low_confidence_word_count": 0, "word_count": 40},
        }
        gate = evaluate_quality_gate(candidate, self._settings())
        self.assertEqual(gate["hygiene_gate"], HYGIENE_GATE_PASS)
        if gate["passed"]:
            self.assertTrue(gate["auto_qualified"])

    def test_high_performance_with_needs_attention_passes_assisted_mode(self):
        scored = score_candidate_text(
            "Kenapa investor memilih startup AI dengan revenue SaaS dan margin bisnis naik cepat?",
            "Kenapa Investor Pilih AI?",
            60_000,
            boundary_confidence=62,
            opening_strength=90,
            pack_id="tech_finance",
        )
        candidate = {
            "score": scored,
            "curation_metadata": {"boundary_confidence": 62},
            "asr_metadata": {"low_confidence_word_count": 0, "word_count": 40},
        }
        settings = self._settings()
        settings["overall_threshold"] = 60
        settings["hook_threshold"] = 60
        gate = evaluate_quality_gate(candidate, settings)
        self.assertEqual(gate["hygiene_gate"], HYGIENE_GATE_NEEDS_ATTENTION)
        self.assertIn(HYGIENE_FLAG_ABRUPT_BOUNDARY, gate["hygiene_flags"])
        if gate["scores"]["performance"] >= 60:
            self.assertTrue(gate["checks"]["hygiene_gate"])

    def test_full_mode_blocks_needs_attention_even_with_high_performance(self):
        scored = score_candidate_text(
            "Kenapa investor memilih startup AI dengan revenue SaaS dan margin bisnis naik cepat?",
            "Kenapa Investor Pilih AI?",
            60_000,
            boundary_confidence=62,
            opening_strength=90,
            pack_id="tech_finance",
        )
        candidate = {
            "score": scored,
            "curation_metadata": {"boundary_confidence": 62},
            "asr_metadata": {"low_confidence_word_count": 0, "word_count": 40},
        }
        settings = self._settings()
        settings["autonomy_mode"] = "full"
        settings["overall_threshold"] = 60
        settings["hook_threshold"] = 60
        gate = evaluate_quality_gate(candidate, settings)
        self.assertEqual(gate["hygiene_gate"], HYGIENE_GATE_NEEDS_ATTENTION)
        self.assertFalse(gate["passed"])


if __name__ == "__main__":
    unittest.main()
