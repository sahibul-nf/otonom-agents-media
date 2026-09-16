import unittest
from unittest.mock import patch

from media_engine.llm import LLMError
from media_engine.post_copy import (
    build_post_caption,
    caption_char_limit,
    enrich_post_copy_for_candidate,
    generate_post_caption,
    resolve_post_copy_context,
)


class PostCopyTests(unittest.TestCase):
    def test_platform_limits_use_tiktok_and_telegram_caps(self):
        self.assertEqual(caption_char_limit("tiktok"), 2200)
        self.assertEqual(caption_char_limit("telegram_channel"), 1024)
        self.assertEqual(caption_char_limit(""), 400)

    def test_build_post_caption_respects_platform_limit(self):
        long_body = "A" * 500
        candidate = {
            "profile_id": "workspace",
            "title_hook": long_body,
            "hook_subtitle": "Subtitle",
            "curation_metadata": {"post_caption_override": f"{long_body}\n\n#One #Two #Three #Four #Five"},
        }
        caption = build_post_caption(candidate, platform="tiktok")
        self.assertLessEqual(len(caption), 2200)

    def test_workspace_context_uses_profile_cta_and_name(self):
        ctx = resolve_post_copy_context(profile_id="nourbit")
        self.assertIn("Nourbit", ctx.workspace_name)
        self.assertIn("Follow Nourbit", ctx.cta_text)

    def test_generate_post_caption_is_workspace_aware(self):
        candidate = {
            "profile_id": "nourbit",
            "title_hook": "Syukur Hakiki Itu Apa?",
            "hook_subtitle": "Pengingat tentang rasa syukur yang tulus.",
            "viral_reason": "Reason",
            "transcript_span": "Syukur hakiki adalah ketika hati merasa cukup dengan anugerah Allah.",
        }
        with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-key"}, clear=True), patch(
            "media_engine.post_copy.call_llm_json",
        ) as call:
            call.return_value = {
                "post_caption": "Syukur hakiki dimulai dari hati yang merasa cukup.\n\n#Nourbit #KajianIslam #NasihatHati #Dzikir #IslamicReminder",
            }
            result = generate_post_caption(candidate, preferred_provider="deepseek")
        payload = call.call_args[0][2]
        self.assertIn("Nourbit", payload)
        self.assertIn("Follow Nourbit", payload)
        self.assertEqual(result["source"], "llm_deepseek")

    def test_generate_post_caption_falls_back_locally_on_llm_error(self):
        candidate = {
            "profile_id": "nourbit",
            "title_hook": "Jalan Menuju Hati Tenang",
            "hook_subtitle": "Pengingat singkat.",
            "transcript_span": "Hati tenang datang dari ingat kepada Allah.",
        }
        with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-key"}, clear=True), patch(
            "media_engine.post_copy.call_llm_json",
            side_effect=LLMError("timeout"),
        ):
            result = generate_post_caption(candidate, preferred_provider="deepseek")
        self.assertEqual(result["source"], "heuristic_local")
        self.assertIn("Jalan Menuju Hati Tenang", result["post_caption"])

    def test_enrich_post_copy_writes_override(self):
        candidate = {
            "profile_id": "nourbit",
            "source_id": "nourbit_vid",
            "title_hook": "Satu",
            "hook_subtitle": "Dua",
            "transcript_span": "Konten transcript yang cukup panjang untuk caption.",
            "curation_metadata": {},
        }
        with patch.dict("os.environ", {}, clear=True):
            enrich_post_copy_for_candidate(candidate, profile_id="nourbit")
        metadata = candidate["curation_metadata"]
        self.assertTrue(str(metadata.get("post_caption_override") or "").strip())
        self.assertIn(metadata.get("post_caption_source"), {"heuristic_local", "llm_deepseek", "llm_openai"})

    def test_distinguishable_captions_for_same_title(self):
        first = {
            "profile_id": "nourbit",
            "title_hook": "Syukur Hakiki Itu Apa?",
            "hook_subtitle": "Refleksi awal.",
            "transcript_span": "Syukur hakiki berarti merasa cukup dengan nikmat Allah tanpa mengeluh.",
        }
        second = {
            "profile_id": "nourbit",
            "title_hook": "Syukur Hakiki Itu Apa?",
            "hook_subtitle": "Sudut pandang lain.",
            "transcript_span": "Orang yang bersyukur hakiki tidak membandingkan rezekinya dengan orang lain.",
        }
        with patch.dict("os.environ", {}, clear=True):
            enrich_post_copy_for_candidate(first, profile_id="nourbit")
            enrich_post_copy_for_candidate(second, profile_id="nourbit")
        first_caption = first["curation_metadata"]["post_caption_override"]
        second_caption = second["curation_metadata"]["post_caption_override"]
        self.assertNotEqual(first_caption, second_caption)


if __name__ == "__main__":
    unittest.main()
