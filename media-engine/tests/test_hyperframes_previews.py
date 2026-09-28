import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from media_engine import hyperframes_previews
from media_engine.hyperframes_renderer import build_hyperframes_index_html


class HyperframesPreviewTests(unittest.TestCase):
    def test_preview_status_reports_cached_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            preview_root = Path(tmp)
            with patch.object(hyperframes_previews, "PREVIEW_ROOT", preview_root):
                path = hyperframes_previews.preview_path("spiritual_reflective", "short_9_16")
                path.parent.mkdir(parents=True)
                path.write_bytes(b"preview")
                (path.parent / "preview-metadata.json").write_text(
                    '{"contract_version": %d}' % hyperframes_previews.PREVIEW_CONTRACT_VERSION,
                    encoding="utf-8",
                )

                status = hyperframes_previews.preview_status("spiritual_reflective", "short_9_16")

        self.assertTrue(status["ready"])
        self.assertEqual(status["size"], len(b"preview"))
        self.assertIn("spiritual_reflective", status["path"])
        self.assertIn("renderer_ready", status)

    def test_preview_status_marks_stale_contract_as_not_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            preview_root = Path(tmp)
            with patch.object(hyperframes_previews, "PREVIEW_ROOT", preview_root):
                path = hyperframes_previews.preview_path("spiritual_reflective", "short_9_16")
                path.parent.mkdir(parents=True)
                path.write_bytes(b"preview")
                (path.parent / "preview-metadata.json").write_text('{"contract_version": 1}', encoding="utf-8")

                status = hyperframes_previews.preview_status("spiritual_reflective", "short_9_16")

        self.assertFalse(status["ready"])

    def test_schedule_builtin_preview_prewarm_skips_when_renderer_off(self):
        hyperframes_previews._prewarm_scheduled = False
        with patch.object(hyperframes_previews, "preview_renderer_ready", return_value=(False, "off")):
            with patch.object(hyperframes_previews, "ensure_hyperframes_template_preview") as ensure:
                hyperframes_previews.schedule_builtin_preview_prewarm()
                hyperframes_previews.schedule_builtin_preview_prewarm()
        ensure.assert_not_called()

    def test_prewarm_skips_brand_templates_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            preview_root = Path(tmp)

            def fake_ensure(template_id: str, hyperframes_format: str) -> Path:
                path = preview_root / template_id.replace(":", "__") / hyperframes_format / "preview.mp4"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"preview")
                return path

            with patch.object(hyperframes_previews, "PREVIEW_ROOT", preview_root), patch.object(
                hyperframes_previews,
                "ensure_hyperframes_template_preview",
                side_effect=fake_ensure,
            ):
                result = hyperframes_previews.prewarm_hyperframes_template_previews(include_brand=False)

        self.assertGreaterEqual(result["total"], 13)
        self.assertEqual(result["ready"], result["total"])
        self.assertFalse(any(str(item["template"]).startswith("brand:") for item in result["items"]))

    def test_prewarm_can_target_single_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            preview_root = Path(tmp)

            def fake_ensure(template_id: str, hyperframes_format: str) -> Path:
                path = preview_root / template_id.replace(":", "__") / hyperframes_format / "preview.mp4"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"preview")
                return path

            with patch.object(hyperframes_previews, "PREVIEW_ROOT", preview_root), patch.object(
                hyperframes_previews,
                "ensure_hyperframes_template_preview",
                side_effect=fake_ensure,
            ):
                result = hyperframes_previews.prewarm_hyperframes_template_previews(
                    include_brand=False,
                    template_id="byline_trust_quote",
                )

        self.assertEqual(result["total"], 2)
        self.assertTrue(all(item["template"] == "byline_trust_quote" for item in result["items"]))

    def test_preview_copy_varies_by_template_category(self):
        spiritual = hyperframes_previews._preview_copy_for_template({"category": "Spiritual", "label": "Spiritual Reflective", "best_for": "Devotional"})
        data = hyperframes_previews._preview_copy_for_template({"category": "Data", "label": "Velocity Business Promo", "best_for": "Finance"})
        promo = hyperframes_previews._preview_copy_for_template({"category": "Promo", "label": "Energy Warm Question", "best_for": "Creator"})

        self.assertNotEqual(spiritual["captionText"], data["captionText"])
        self.assertNotEqual(data["captionText"], promo["captionText"])
        self.assertEqual(spiritual["captions"][0]["text"], "Allah selalu dekat")
        self.assertIn("Fed", data["captions"][0]["text"])
        self.assertEqual(spiritual["titleHook"], "Allah selalu dekat")
        self.assertNotEqual(spiritual["titleHook"], "Spiritual Reflective")

    def test_preview_contract_strips_shared_shell_chrome(self):
        contract = hyperframes_previews._preview_contract("spiritual_reflective", "short_9_16", 1080, 1920)

        self.assertEqual(contract["shellComponents"], hyperframes_previews.PREVIEW_SHELL_COMPONENTS)
        self.assertEqual(contract["ctaText"], "")
        self.assertEqual(contract["sourceAttribution"], "")
        self.assertNotEqual(contract["titleHook"], "Spiritual Reflective")
        self.assertIn("Allah", contract["titleHook"])

    def test_brand_studio_contract_is_five_seconds_with_watermark(self):
        style = {
            "caption": {
                "text_color": "#abcdef",
                "highlight_word_color": "#112233",
                "background_color": "#09090b",
            },
            "brand": {"watermark_text": "TechTalk"},
        }
        brand_system = {
            "caption_style": "caption-editorial-emphasis",
            "cta_overlay": "yt-lower-third",
        }
        contract = hyperframes_previews._brand_studio_preview_contract(
            "spiritual_reflective",
            "short_9_16",
            1080,
            1920,
            "AI agents will change everything.",
            style,
            brand_system,
        )

        self.assertEqual(contract["durationMs"], 8000)
        self.assertTrue(contract["shellComponents"]["watermark"])
        self.assertEqual(contract["watermarkText"], "TechTalk")
        self.assertEqual(contract["style"]["caption"]["text_color"], "#abcdef")
        self.assertIn("AI agents", contract["captionText"])
        self.assertNotIn("Allah", contract["captionText"])

    def test_brand_studio_cache_key_changes_when_highlight_color_changes(self):
        brand_system = {"caption_style": "caption-editorial-emphasis"}
        style_a = {"caption": {"highlight_word_color": "#111111"}, "brand": {}}
        style_b = {"caption": {"highlight_word_color": "#222222"}, "brand": {}}
        key_a = hyperframes_previews.brand_studio_preview_cache_key(
            "spiritual_reflective",
            "short_9_16",
            "Sample phrase",
            style_a,
            brand_system,
        )
        key_b = hyperframes_previews.brand_studio_preview_cache_key(
            "spiritual_reflective",
            "short_9_16",
            "Sample phrase",
            style_b,
            brand_system,
        )

        self.assertNotEqual(key_a, key_b)

    def test_brand_texture_layers_use_full_bleed_not_template_layer(self):
        contract = hyperframes_previews._brand_studio_preview_contract(
            "story_handwritten",
            "short_9_16",
            1080,
            1920,
            "Ketenangan hati hadir saat bersyukur.",
            {"caption": {"font_family": "Caveat"}, "brand": {"watermark_text": "Brand Clips"}},
            {"texture_effect": "vignette", "cta_overlay": "none"},
        )
        html = build_hyperframes_index_html(contract, "story_handwritten", "short_9_16")

        self.assertIn('id="hf-vignette"', html)
        self.assertNotIn('class="brand-texture-layer brand-vignette"', html)

    def test_brand_texture_none_skips_overlay_layers(self):
        contract = hyperframes_previews._brand_studio_preview_contract(
            "story_handwritten",
            "short_9_16",
            1080,
            1920,
            "Ketenangan hati hadir saat bersyukur.",
            {"caption": {"font_family": "Caveat"}, "brand": {"watermark_text": "Brand Clips"}},
            {"texture_effect": "none", "cta_overlay": "none"},
        )
        html = build_hyperframes_index_html(contract, "story_handwritten", "short_9_16")

        self.assertNotIn('id="hf-vignette"', html)
        self.assertNotIn('id="grain-overlay"', html)

    def test_brand_studio_html_has_overlay_lifecycle_and_single_cta(self):
        contract = hyperframes_previews._brand_studio_preview_contract(
            "spiritual_reflective",
            "short_9_16",
            1080,
            1920,
            "Ketenangan hati hadir saat bersyukur.",
            {"caption": {"font_family": "Lora"}, "brand": {"watermark_text": "Nourbit"}},
            {"texture_effect": "none", "cta_overlay": "yt-lower-third"},
        )
        html = build_hyperframes_index_html(contract, "spiritual_reflective", "short_9_16")

        self.assertIn("overlayLayers", html)
        self.assertIn('data-composition-src="compositions/yt-lower-third.html"', html)
        self.assertNotIn("brand-social-pill", html)
        self.assertNotIn("repeat: -1", html)
        self.assertNotIn('id="cta"', html)
        self.assertNotIn("Ketenangan hati hadir saat bersyukur.", html.split("caption-text")[0])

    def test_brand_studio_project_copies_oss_composition_files(self):
        contract = hyperframes_previews._brand_studio_preview_contract(
            "story_handwritten",
            "short_9_16",
            1080,
            1920,
            "Ketenangan hati hadir saat bersyukur.",
            {"caption": {"font_family": "Caveat"}, "brand": {"watermark_text": "Brand Clips"}},
            {"cta_overlay": "tiktok-follow", "texture_effects": ["vignette"]},
        )
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "project"
            hyperframes_previews._write_brand_studio_project(
                project_dir,
                contract,
                "story_handwritten",
                "short_9_16",
            )
            self.assertTrue((project_dir / "compositions" / "tiktok-follow.html").exists())
            self.assertTrue((project_dir / "compositions" / "components" / "vignette.html").exists())
            self.assertTrue((project_dir / "assets" / "avatar.jpg").exists())

    def test_brand_studio_overlay_slots_differ_from_caption(self):
        contract = hyperframes_previews._brand_studio_preview_contract(
            "story_handwritten",
            "short_9_16",
            1080,
            1920,
            "Ketenangan hati hadir saat bersyukur.",
            {"caption": {"font_family": "Caveat"}, "brand": {}},
            {"texture_effect": "none", "cta_overlay": "none"},
        )
        overlay_headline = contract["overlay"]["headline"]
        caption_text = contract["captions"][0]["text"]
        self.assertNotEqual(overlay_headline, caption_text)


if __name__ == "__main__":
    unittest.main()
