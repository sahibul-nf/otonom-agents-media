import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from media_engine import hyperframes_templates as hf_templates_module
from media_engine.hyperframes_templates import (
    DEFAULT_TEMPLATE_ID,
    dimensions_for_format,
    list_hyperframes_templates,
    normalize_hyperframes_format,
    normalize_hyperframes_template,
    resolve_hyperframes_template,
    hyperframes_template_ids,
    template_supports_format,
)


class HyperframesTemplateTests(unittest.TestCase):
    def test_lists_curated_template_pack(self):
        templates = list_hyperframes_templates()
        builtin = [template for template in templates if not str(template["id"]).startswith("brand:")]

        self.assertEqual(len(builtin), 20)
        self.assertEqual({template["status"] for template in builtin}, {"ready"})
        self.assertTrue(any(template["id"] == "energy_warm_question" for template in builtin))
        self.assertTrue(any(template["id"] == "spiritual_reflective" for template in builtin))
        self.assertTrue(any(template["id"] == "techtalk_intel_brief" for template in builtin))

    def test_explicit_override_wins(self):
        template = resolve_hyperframes_template("prism_pro_pricing", genres=["kajian"])

        self.assertEqual(template["id"], "prism_pro_pricing")

    def test_auto_selects_by_genre(self):
        self.assertEqual(resolve_hyperframes_template("auto", genres=["crypto"])["id"], "velocity_business_promo")
        self.assertEqual(resolve_hyperframes_template("auto", genres=["podcast"])["id"], "grit_training_stamp")
        self.assertEqual(resolve_hyperframes_template("auto", genres=["geopolitics"])["id"], "byline_trust_quote")
        self.assertEqual(
            resolve_hyperframes_template("auto", genres=["explainer"], hyperframes_format="long_16_9")["id"],
            "techtalk_intel_brief",
        )
        self.assertEqual(
            resolve_hyperframes_template("auto", genres=["explainer"], hyperframes_format="short_9_16")["id"],
            DEFAULT_TEMPLATE_ID,
        )
        self.assertNotEqual(
            resolve_hyperframes_template("auto", genres=["story", "advice", "social_commentary"])["id"],
            "spiritual_reflective",
        )
        self.assertEqual(resolve_hyperframes_template("auto", genres=["kajian"])["id"], "spiritual_reflective")

    def test_intel_brief_is_long_form_only(self):
        intel = next(template for template in list_hyperframes_templates() if template["id"] == "techtalk_intel_brief")
        self.assertEqual(intel["formats"], ["long_16_9"])
        short_templates = list_hyperframes_templates("short_9_16")
        self.assertFalse(any(template["id"] == "techtalk_intel_brief" for template in short_templates))
        self.assertTrue(template_supports_format(intel, "long_16_9"))
        self.assertFalse(template_supports_format(intel, "short_9_16"))

    def test_unknown_values_fall_back_to_auto_then_default(self):
        self.assertEqual(normalize_hyperframes_template("missing"), "auto")
        self.assertEqual(resolve_hyperframes_template("missing", genres=["unknown"])["id"], DEFAULT_TEMPLATE_ID)

    def test_legacy_specific_template_aliases_to_public_template(self):
        self.assertEqual(normalize_hyperframes_template("nourbit_reflective"), "spiritual_reflective")
        self.assertEqual(normalize_hyperframes_template("podcast_talking_head"), "grit_training_stamp")
        self.assertEqual(normalize_hyperframes_template("techtalk_explainer"), "techtalk_intel_brief")
        self.assertEqual(normalize_hyperframes_template("techtalk"), "techtalk_intel_brief")

    def test_removed_template_ids_alias_to_replacement(self):
        self.assertEqual(resolve_hyperframes_template("podcast_talking_head")["id"], "grit_training_stamp")
        self.assertEqual(resolve_hyperframes_template("data_market_explainer")["id"], "velocity_business_promo")
        self.assertEqual(resolve_hyperframes_template("techtalk_explainer")["id"], "techtalk_intel_brief")

    def test_templates_expose_preview_contract(self):
        template = list_hyperframes_templates()[0]

        self.assertEqual(template["preview_seconds"], 15)
        self.assertIn("short_9_16", template["preview_urls"])
        self.assertIn("short_9_16", template["preview_cache_ready"])
        self.assertIn(template["preview_status"], {"ready", "partial", "generating"})
        self.assertIn("lint", template["production_checks"])
        self.assertIn("/api/media/hyperframes-template-preview", template["preview_urls"]["short_9_16"])

    def test_spot_check_recipes_have_distinct_style_meta(self):
        from media_engine.hyperframes_recipes import recipe_style_meta

        checked = ("byline_trust_quote", "energy_warm_question", "neon_seize_future", "grit_training_stamp", "quintessence_serif")
        metas = [recipe_style_meta(template_id) for template_id in checked]
        font_families = {meta.font_family for meta in metas}
        motion_presets = {meta.motion_preset for meta in metas}

        self.assertEqual(len(font_families), len(checked))
        self.assertEqual(len(motion_presets), len(checked))

    def test_recipes_expose_distinct_shell_css(self):
        from media_engine.hyperframes_recipes import get_recipe
        from media_engine.hyperframes_recipes._base import LayoutContext

        layout = LayoutContext(
            width=1080,
            height=1920,
            is_landscape=False,
            caption_font_size=54,
            text_color="#ffffff",
            highlight_color="#d8b45f",
            accent="#d8b45f",
            secondary_accent="#8ee6c8",
        )
        spiritual = get_recipe("spiritual_reflective").shell_css(layout)
        neon = get_recipe("neon_seize_future").shell_css(layout)
        self.assertIn(".cta", spiritual)
        self.assertIn(".cta", neon)
        self.assertNotEqual(spiritual, neon)

    def test_format_dimensions(self):
        self.assertEqual(normalize_hyperframes_format("bad"), "auto")
        self.assertEqual(dimensions_for_format("short_9_16"), (1080, 1920, "short_9_16"))
        self.assertEqual(dimensions_for_format("long_16_9"), (1920, 1080, "long_16_9"))
        self.assertEqual(dimensions_for_format("auto"), (1080, 1920, "short_9_16"))

    def test_builtin_template_count(self):
        self.assertEqual(len(hyperframes_template_ids()), 20)

    def test_techtalk_recipe_overlay(self):
        from media_engine.hyperframes_recipes import LayoutContext, get_recipe

        recipe = get_recipe("techtalk_intel_brief")
        layout = LayoutContext(
            width=1920,
            height=1080,
            is_landscape=True,
            caption_font_size=48,
            text_color="#f8fafc",
            highlight_color="#2dd4bf",
            accent="#2dd4bf",
            secondary_accent="#e2e8f0",
        )
        html = recipe.render_overlay(
            {"titleHook": "Bitcoin is scarce", "hookSubtitle": "21 juta unit", "watermarkText": "TechTalk"},
            {"id": "techtalk_intel_brief"},
            layout,
        )
        self.assertIn("techtalk-brief", html)
        self.assertIn("Bitcoin is scarce", html)
        self.assertIn("TechTalk", html)
        self.assertIn("techtalk-chips", html)
        self.assertEqual(recipe.style_meta().motion_preset, "brief-slide")

        broll_html = recipe.render_overlay(
            {
                "titleHook": "How it works",
                "hookSubtitle": "Supply schedule",
                "watermarkText": "TechTalk",
                "viralReason": "explainer broll scene",
            },
            {"id": "techtalk_intel_brief"},
            layout,
        )
        self.assertIn("techtalk-bars", broll_html)
        self.assertIn("Signal snapshot", broll_html)

        default_html = recipe.render_overlay(
            {"titleHook": "Key takeaway", "hookSubtitle": "Brief"},
            {"id": "techtalk_intel_brief"},
            layout,
        )
        self.assertIn("Intel Brief", default_html)

    def test_techtalk_render_html_keeps_motion_css_in_style_block(self):
        from media_engine.hyperframes_renderer import build_hyperframes_index_html
        from media_engine.rendering import build_premium_render_contract

        candidate = {
            "id": "clip_techtalk",
            "start_ms": 0,
            "end_ms": 60_000,
            "title_hook": "Fed pivot changes the tape",
            "viral_reason": "Reason",
            "transcript_span": "Fed pivot",
            "timed_captions": [
                {
                    "text": "Fed pivot",
                    "startMs": 0,
                    "endMs": 60_000,
                    "words": [{"text": "Fed", "startMs": 0, "endMs": 30_000}, {"text": "pivot", "startMs": 30_000, "endMs": 60_000}],
                }
            ],
        }
        profile = {"id": "techtalk", "watermark_text": "Intel Brief", "cta_text": ""}
        contract = build_premium_render_contract(candidate, profile, "source.mp4", "https://youtu.be/test", "Source: Channel")
        contract = {
            **contract,
            "shellComponents": {"hook": False, "watermark": False, "source": False, "cta": False},
        }

        html = build_hyperframes_index_html(contract, hyperframes_template="techtalk_intel_brief")
        gsap_script = html.split('<script src="https://cdn.jsdelivr.net/npm/gsap')[1].split("</script>")[0]

        self.assertNotIn(".techtalk-brief", gsap_script)
        self.assertIn("@keyframes techtalkBriefIn", html)
        self.assertIn(".techtalk-brief{animation:techtalkBriefIn", html)

    def test_templates_expose_shell_component_defaults(self):
        byline = next(template for template in list_hyperframes_templates() if template["id"] == "byline_trust_quote")
        velocity = next(template for template in list_hyperframes_templates() if template["id"] == "velocity_business_promo")
        spiritual = next(template for template in list_hyperframes_templates() if template["id"] == "spiritual_reflective")

        self.assertEqual(byline["shell_components"], {"hook": False, "watermark": True, "source": True, "cta": False})
        self.assertEqual(velocity["shell_components"], {"hook": False, "watermark": True, "source": True, "cta": False})
        self.assertEqual(spiritual["shell_components"], {"hook": False, "watermark": True, "source": False, "cta": True})

    def test_renderer_omits_disabled_shell_nodes(self):
        from media_engine.hyperframes_renderer import build_hyperframes_index_html
        from media_engine.rendering import build_premium_render_contract

        candidate = {
            "id": "clip_shell",
            "start_ms": 0,
            "end_ms": 60_000,
            "title_hook": "Headline",
            "viral_reason": "Reason",
            "transcript_span": "word one two",
            "timed_captions": [
                {
                    "text": "word one two",
                    "startMs": 0,
                    "endMs": 25_000,
                    "words": [
                        {"text": "word", "startMs": 0, "endMs": 8_000},
                        {"text": "one", "startMs": 8_000, "endMs": 16_000},
                        {"text": "two", "startMs": 16_000, "endMs": 25_000},
                    ],
                }
            ],
        }
        profile = {"id": "nourbit", "watermark_text": "Brand", "cta_text": "Follow for more"}
        contract = build_premium_render_contract(candidate, profile, "source.mp4", "https://youtu.be/test", "Source: Channel")
        contract = {
            **contract,
            "style": {
                **contract["style"],
                "shell_components": {"hook": False, "watermark": True, "source": False, "cta": False},
            },
        }

        html = build_hyperframes_index_html(contract, hyperframes_template="spiritual_reflective")

        self.assertNotIn('id="hook"', html)
        self.assertNotIn('id="cta"', html)
        self.assertIn("brand-row", html)
        self.assertNotIn('class="source"', html)

    def test_renderer_honors_shell_component_overrides(self):
        from media_engine.hyperframes_renderer import build_hyperframes_index_html
        from media_engine.rendering import build_premium_render_contract

        candidate = {
            "id": "clip_shell_override",
            "start_ms": 0,
            "end_ms": 60_000,
            "title_hook": "Override Hook",
            "viral_reason": "Reason",
            "transcript_span": "alpha beta",
            "timed_captions": [
                {
                    "text": "alpha beta",
                    "startMs": 0,
                    "endMs": 25_000,
                    "words": [
                        {"text": "alpha", "startMs": 0, "endMs": 12_000},
                        {"text": "beta", "startMs": 12_000, "endMs": 25_000},
                    ],
                }
            ],
        }
        profile = {"id": "nourbit", "watermark_text": "Brand", "cta_text": "Subscribe"}
        contract = build_premium_render_contract(candidate, profile, "source.mp4", "https://youtu.be/test", "Source: Channel")
        contract = {
            **contract,
            "shellComponents": {"hook": True, "watermark": False, "source": True, "cta": True},
        }

        html = build_hyperframes_index_html(contract, hyperframes_template="byline_trust_quote")

        self.assertIn("z-index: 220", html)
        self.assertIn("#grain-overlay", html)

        self.assertIn('id="hook"', html)
        self.assertIn("Override Hook", html)
        self.assertIn('id="cta"', html)
        self.assertIn('<div class="brand-row"><span class="source">', html)

    def test_list_includes_saved_brand_system_profiles(self):
        templates = list_hyperframes_templates()
        brand_ids = {item["id"] for item in templates if item.get("source") == "brand_system"}
        self.assertIn("brand:custom_spiritual_reflective_brand_template", brand_ids)

    def test_brand_auto_resolves_starter_even_when_hidden_from_catalog(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profiles = root / "profiles"
            profiles.mkdir()
            custom = profiles / "custom_nourbit_brand.json"
            custom.write_text(
                json.dumps(
                    {
                        "id": "custom_nourbit_brand",
                        "label": "Nourbit Brand",
                        "brand_system": {"starter_template": "energy_warm_question", "cta_overlay": "tiktok-follow"},
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(hf_templates_module, "ROOT", root):
                brand_id = "brand:custom_nourbit_brand"
                self.assertEqual(normalize_hyperframes_template(brand_id), brand_id)
                resolved = resolve_hyperframes_template(brand_id)
                self.assertEqual(resolved["recipe_module"], "energy_warm_question")
                self.assertEqual(resolved["starter_template"], "energy_warm_question")


if __name__ == "__main__":
    unittest.main()
