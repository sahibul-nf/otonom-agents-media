import tempfile
import unittest

from media_engine.rendering import build_premium_render_contract
from media_engine.styles import (
    TEMPLATE_ONLY_STYLE_TOKEN,
    is_template_only_style,
    load_style_for_render,
    normalize_brand_template_ref,
    style_from_recipe,
)


class TemplateOnlyStyleTests(unittest.TestCase):
    def test_sentinel_detection_and_normalization(self):
        self.assertTrue(is_template_only_style(""))
        self.assertTrue(is_template_only_style("auto"))
        self.assertTrue(is_template_only_style("profiles/default_workspace_style.json"))
        self.assertFalse(is_template_only_style("profiles/custom_acme.json"))
        self.assertEqual(normalize_brand_template_ref(None), TEMPLATE_ONLY_STYLE_TOKEN)
        self.assertEqual(normalize_brand_template_ref("profiles/default_workspace_style.json"), TEMPLATE_ONLY_STYLE_TOKEN)

    def test_style_from_recipe_uses_recipe_shell_defaults(self):
        style = style_from_recipe("techtalk_intel_brief")
        self.assertTrue(style.get("template_only"))
        self.assertEqual(style["brand"]["watermark_text"], "")
        self.assertFalse(style["brand"]["cta_enabled"])
        self.assertIn("shell_components", style)

    def test_load_style_for_render_auto_resolves_template(self):
        style = load_style_for_render("auto", hyperframes_template="techtalk_intel_brief")
        self.assertTrue(style.get("template_only"))
        self.assertNotEqual(style["caption"].get("font_family"), "Sora")

    def test_render_contract_skips_profile_watermark_when_template_only(self):
        candidate = {
            "id": "c1",
            "start_ms": 0,
            "end_ms": 25000,
            "title_hook": "Hook",
            "viral_reason": "Reason",
            "hook_subtitle": "sub",
            "transcript_span": "one two three",
            "timed_captions": [
                {"startMs": 0, "endMs": 12000, "text": "one", "words": [{"text": "one", "startMs": 0, "endMs": 12000}]},
                {"startMs": 12000, "endMs": 24000, "text": "two", "words": [{"text": "two", "startMs": 12000, "endMs": 24000}]},
            ],
        }
        profile = {"id": "workspace", "watermark_text": "Profile WM", "cta_text": "Follow"}
        style = style_from_recipe("spiritual_reflective")
        with tempfile.NamedTemporaryFile(suffix=".mp4") as media:
            contract = build_premium_render_contract(
                candidate,
                profile,
                media.name,
                "https://example.com",
                "Source",
                style=style,
            )
        self.assertEqual(contract["watermarkText"], "")
        self.assertEqual(contract["ctaText"], "")


if __name__ == "__main__":
    unittest.main()
