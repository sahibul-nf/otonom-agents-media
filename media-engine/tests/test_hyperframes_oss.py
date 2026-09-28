import unittest

from media_engine.hyperframes_oss import (
    copy_oss_files_to_project,
    installed_catalog_items,
    placement_timeline,
    resolve_oss_selections,
)
from media_engine.hyperframes_renderer import build_hyperframes_index_html
from media_engine.hyperframes_previews import _brand_studio_preview_contract


class HyperframesOssTests(unittest.TestCase):
    def test_manifest_lists_social_blocks(self):
        ids = {item["id"] for item in installed_catalog_items()}
        self.assertIn("yt-lower-third", ids)
        self.assertIn("tiktok-follow", ids)

    def test_yt_lower_third_embeds_oss_block_not_pill(self):
        contract = _brand_studio_preview_contract(
            "spiritual_reflective",
            "short_9_16",
            1080,
            1920,
            "Sample caption line.",
            {"caption": {}, "brand": {"watermark_text": "TechTalk"}},
            {"cta_overlay": "yt-lower-third", "caption_style": "caption-editorial-emphasis"},
        )
        html = build_hyperframes_index_html(contract, "spiritual_reflective", "short_9_16")
        self.assertIn('data-composition-src="compositions/yt-lower-third.html"', html)
        self.assertIn("TechTalk", html)
        self.assertNotIn("brand-social-pill", html)

    def test_tiktok_follow_embeds_portrait_block(self):
        contract = _brand_studio_preview_contract(
            "velocity_business_promo",
            "short_9_16",
            1080,
            1920,
            "Bold kinetic hook.",
            {"caption": {}, "brand": {"watermark_text": "Volt Clips"}},
            {"cta_overlay": "tiktok-follow"},
        )
        html = build_hyperframes_index_html(contract, "velocity_business_promo", "short_9_16")
        self.assertIn('data-composition-src="compositions/tiktok-follow.html"', html)
        self.assertIn('data-width="1080"', html)
        self.assertIn('data-height="1920"', html)
        self.assertNotIn("brand-social-pill", html)

    def test_texture_components_merge_grain_overlay(self):
        contract = _brand_studio_preview_contract(
            "story_handwritten",
            "short_9_16",
            1080,
            1920,
            "Warm story line.",
            {"caption": {}, "brand": {}},
            {"texture_effects": ["grain-overlay"]},
        )
        html = build_hyperframes_index_html(contract, "story_handwritten", "short_9_16")
        self.assertIn('id="grain-overlay"', html)

    def test_resolve_selections_places_cta_near_end(self):
        selections = resolve_oss_selections(
            {"cta_overlay": "yt-lower-third"},
            duration_ms=8000,
            host_width=1080,
            host_height=1920,
        )
        blocks = selections["blocks"]
        self.assertEqual(len(blocks), 1)
        self.assertGreater(blocks[0].start_s, 5.0)
        self.assertLessEqual(blocks[0].duration_s, 2.2)

    def test_placement_timeline_intro_overlay_exits_before_cta(self):
        for total_s in (5.0, 8.0):
            timeline = placement_timeline(
                total_s,
                cta_id="instagram-follow",
                intro_block_id="",
                show_recipe_overlay=True,
            )
            self.assertLess(timeline.overlay_exit_s, timeline.cta_start_s)
            self.assertGreaterEqual(timeline.cta_start_s, total_s - 2.2)

    def test_lower_third_intro_dedupes_yt_cta_at_end(self):
        selections = resolve_oss_selections(
            {"intro_layout": "lower-third-hook", "cta_overlay": "yt-lower-third"},
            duration_ms=8000,
            host_width=1080,
            host_height=1920,
        )
        yt_blocks = [block for block in selections["blocks"] if block.block_id == "yt-lower-third"]
        self.assertEqual(len(yt_blocks), 1)
        self.assertGreater(yt_blocks[0].start_s, 5.0)

    def test_production_duration_clamps_cta_hold(self):
        selections = resolve_oss_selections(
            {"cta_overlay": "instagram-follow"},
            duration_ms=45000,
            host_width=1080,
            host_height=1920,
        )
        block = selections["blocks"][0]
        self.assertLessEqual(block.duration_s, 2.2)
        self.assertGreater(block.start_s, 42.0)

    def test_intro_none_skips_recipe_overlay_timeline(self):
        selections = resolve_oss_selections(
            {"intro_layout": "none", "cta_overlay": "instagram-follow"},
            duration_ms=8000,
            host_width=1080,
            host_height=1920,
        )
        timeline = selections["timeline"]
        self.assertFalse(timeline.show_recipe_overlay)
        self.assertEqual(timeline.overlay_exit_s, 0.0)
        self.assertGreater(timeline.cta_start_s, 5.0)

    def test_story_handwritten_intro_exits_before_instagram_cta(self):
        selections = resolve_oss_selections(
            {"intro_layout": "template-hook", "cta_overlay": "instagram-follow"},
            duration_ms=8000,
            host_width=1080,
            host_height=1920,
        )
        timeline = selections["timeline"]
        self.assertTrue(timeline.show_recipe_overlay)
        self.assertLess(timeline.overlay_exit_s, timeline.cta_start_s)
        self.assertLessEqual(timeline.overlay_exit_s, 2.2)
        self.assertGreaterEqual(timeline.cta_start_s - timeline.overlay_exit_s, 2.0)

    def test_initials_avatar_written_when_no_custom_logo(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            selections = resolve_oss_selections(
                {"cta_overlay": "instagram-follow"},
                duration_ms=8000,
                host_width=1080,
                host_height=1920,
            )
            contract = {
                "style": {"brand": {"watermark_text": "Tech Talk"}},
                "watermarkText": "Tech Talk",
            }
            copied = copy_oss_files_to_project(project_dir, selections, contract)
            self.assertIn("assets/avatar.svg", copied)
            svg = (project_dir / "assets" / "avatar.svg").read_text(encoding="utf-8")
            self.assertIn("TT", svg)

    def test_landscape_block_on_portrait_uses_bottom_strip_not_full_frame(self):
        selections = resolve_oss_selections(
            {"cta_overlay": "yt-lower-third"},
            duration_ms=5000,
            host_width=1080,
            host_height=1920,
        )
        block = selections["blocks"][0]
        self.assertEqual(block.render_width, 1080)
        self.assertLess(block.render_height, 1920)
        self.assertIn("bottom:0", block.wrapper_style)
        self.assertNotIn("inset:0", block.wrapper_style)

    def test_sanitize_social_blocks_use_inspect_safe_slide_offsets(self):
        from media_engine.hyperframes_oss import HYPERFRAMES_DIR, _brand_vars, _sanitize_vendored_html

        raw = (HYPERFRAMES_DIR / "compositions/tiktok-follow.html").read_text(encoding="utf-8")
        brand = _brand_vars({"style": {"brand": {"watermark_text": "Brand Clips"}}, "watermarkText": "Brand Clips"})
        sanitized = _sanitize_vendored_html(raw, brand)
        self.assertNotIn("y: 300", sanitized)
        self.assertIn("visibility: hidden", sanitized)

    def test_x_post_cta_is_deferred_in_production_selections(self):
        selections = resolve_oss_selections(
            {"cta_overlay": "x-post"},
            duration_ms=8000,
            host_width=1080,
            host_height=1920,
        )
        self.assertFalse(selections["blocks"])
        self.assertEqual(selections["timeline"].cta_block_id, "")

    def test_x_post_geometry_when_enabled_directly(self):
        from media_engine.hyperframes_oss import DISABLED_CTA_OVERLAYS, placement_timeline

        self.assertIn("x-post", DISABLED_CTA_OVERLAYS)
        timeline = placement_timeline(8.0, cta_id="instagram-follow")
        self.assertEqual(timeline.cta_block_id, "instagram-follow")

    def test_portrait_tiktok_block_uses_full_native_canvas(self):
        selections = resolve_oss_selections(
            {"cta_overlay": "tiktok-follow"},
            duration_ms=5000,
            host_width=1080,
            host_height=1920,
        )
        block = selections["blocks"][0]
        self.assertEqual(block.render_width, 1080)
        self.assertEqual(block.render_height, 1920)
        self.assertIn("inset:0", block.wrapper_style)


if __name__ == "__main__":
    unittest.main()
