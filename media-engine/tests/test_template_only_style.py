import re
import tempfile
import unittest

from media_engine.hyperframes_recipes import LayoutContext, get_recipe
from media_engine.hyperframes_renderer import build_hyperframes_index_html
from media_engine.hyperframes_templates import hyperframes_template_ids
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

    def test_style_from_recipe_karaoke_is_readable(self):
        style = style_from_recipe("quintessence_serif")
        caption = style["caption"]
        self.assertGreaterEqual(caption["font_size"], 40)
        self.assertLessEqual(caption["font_size"], 50)
        self.assertGreaterEqual(caption["font_size"], 36)
        self.assertGreater(float(caption["stroke_width"]), 0)
        self.assertNotIn(str(caption["background_color"]).lower(), {"transparent", "none", ""})

    def test_load_style_for_render_auto_uses_readable_karaoke(self):
        style = load_style_for_render("auto", hyperframes_template="velocity_business_promo")
        caption = style["caption"]
        self.assertGreaterEqual(caption["font_size"], 40)
        self.assertLessEqual(caption["font_size"], 50)
        self.assertGreater(float(caption["stroke_width"]), 0)

    def test_style_from_recipe_uses_recipe_shell_defaults(self):
        style = style_from_recipe("techtalk_intel_brief")
        self.assertTrue(style.get("template_only"))
        self.assertEqual(style["brand"]["watermark_text"], "")
        self.assertFalse(style["brand"]["cta_enabled"])
        self.assertIn("shell_components", style)

    def test_recipe_css_does_not_shrink_caption_text(self):
        layout = LayoutContext(
            width=1080,
            height=1920,
            is_landscape=False,
            caption_font_size=48,
            text_color="#ffffff",
            highlight_color="#d8b45f",
            accent="#d8b45f",
            secondary_accent="#f8fafc",
        )
        for template_id in hyperframes_template_ids():
            css = get_recipe(template_id).css_block(layout)
            for block in re.finditer(r"\.caption-text\{([^}]*)\}", css):
                body = block.group(1)
                px = re.search(r"font-size:(\d+)px", body)
                em = re.search(r"font-size:([0-9.]+)em", body)
                if px:
                    self.assertGreaterEqual(int(px.group(1)), 36, template_id)
                if em:
                    self.assertGreaterEqual(float(em.group(1)), 1.0, template_id)

    def test_template_only_html_keeps_caption_card_and_stroke(self):
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
        style = style_from_recipe("quintessence_serif")
        with tempfile.NamedTemporaryFile(suffix=".mp4") as media:
            contract = build_premium_render_contract(
                candidate,
                {"id": "workspace", "watermark_text": "", "cta_text": ""},
                media.name,
                "https://example.com",
                "Source",
                style=style,
            )
        html = build_hyperframes_index_html(contract, hyperframes_template="quintessence_serif")
        self.assertIn("font-size: 48px", html)
        self.assertIn("-webkit-text-stroke:", html)
        self.assertIn("rgba(0,0,0,0.62)", html.replace(" ", ""))
        self.assertNotIn(".caption-text{font-size:1.1em", html)

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
