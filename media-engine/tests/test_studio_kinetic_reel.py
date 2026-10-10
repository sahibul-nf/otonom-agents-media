"""Tests for Studio Kinetic Reel engine: visual hierarchy, 3D proof card, depth cutout, and sound design."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from media_engine.hyperframes_recipes import LayoutContext, get_recipe, recipe_style_meta
from media_engine.hyperframes_renderer import build_hyperframes_index_html
from media_engine.hyperframes_templates import resolve_hyperframes_template
from media_engine.sound_design import (
    build_audio_ducking_filter_graph,
    ensure_default_sound_assets,
    get_sound_design_config,
)
from media_engine.subject_cutout import (
    generate_subject_depth_assets,
    is_rembg_available,
    resolve_depth_keyword,
)


class StudioKineticReelTests(unittest.TestCase):
    def setUp(self):
        self.contract = {
            "candidateId": "clip_kinetic_test",
            "durationMs": 45_000,
            "titleHook": "HOW TO SCALE 10X REVENUE",
            "subtitle": "Stop making this beginner mistake in your marketing strategy",
            "watermarkText": "Otonom Media",
            "ctaText": "Follow for more growth breakdowns",
            "proofMetric": "+340% MRR",
            "proofLabel": "VERIFIED GROWTH",
            "proofSub": "Client Case Study #12",
            "captions": [
                {
                    "text": "The SECRET to 10X growth is simple",
                    "startMs": 0,
                    "endMs": 2800,
                    "words": [
                        {"text": "The", "startMs": 0, "endMs": 400},
                        {"text": "SECRET", "startMs": 400, "endMs": 1000},
                        {"text": "to", "startMs": 1000, "endMs": 1300},
                        {"text": "10X", "startMs": 1300, "endMs": 1900},
                        {"text": "growth", "startMs": 1900, "endMs": 2400},
                        {"text": "is", "startMs": 2400, "endMs": 2600},
                        {"text": "simple", "startMs": 2600, "endMs": 2800},
                    ],
                }
            ],
            "soundDesign": {
                "enabled": True,
                "music_volume": 0.15,
                "hook_volume": 0.65,
            },
        }

    def test_recipe_registration_and_style_metadata(self):
        recipe = get_recipe("studio_kinetic_reel")
        self.assertIsNotNone(recipe)
        self.assertEqual(recipe.template_id, "studio_kinetic_reel")

        meta = recipe_style_meta("studio_kinetic_reel")
        self.assertIn("Outfit", meta.font_family)
        self.assertEqual(meta.caption_style, "Kinetic punch hierarchy")
        self.assertEqual(meta.motion_preset, "kinetic-reel")

    def test_typographic_hierarchy_punch_vs_filler_words(self):
        recipe = get_recipe("studio_kinetic_reel")
        layout = LayoutContext(
            width=1080,
            height=1920,
            is_landscape=False,
            caption_font_size=64,
            text_color="#ffffff",
            highlight_color="#facc15",
            accent="#00f5a0",
            secondary_accent="#00d2ff",
        )
        caption_html = recipe.render_caption_html(
            self.contract["captions"][0],
            0,
            layout,
            seconds_fn=lambda ms: f"{ms/1000:.3f}",
            attr_fn=str,
        )

        # Emphatic words 'SECRET' and metric '10X' must receive punch classification
        self.assertIn('class="word-span word-punch"', caption_html)
        self.assertIn('class="word-span word-filler"', caption_html)
        self.assertIn(">SECRET</span>", caption_html)
        self.assertIn(">10X</span>", caption_html)

        # CSS must define distinct font-weights and neon text-shadow
        css = recipe.css_block(layout)
        self.assertIn(".word-filler", css)
        self.assertIn(".word-punch", css)
        self.assertIn("text-shadow:", css)
        self.assertIn("rgba(0, 245, 160", css)

    def test_floating_tilted_3d_proof_card(self):
        recipe = get_recipe("studio_kinetic_reel")
        template = resolve_hyperframes_template("studio_kinetic_reel")
        layout = LayoutContext(
            width=1080,
            height=1920,
            is_landscape=False,
            caption_font_size=64,
            text_color="#ffffff",
            highlight_color="#facc15",
            accent="#00f5a0",
            secondary_accent="#00d2ff",
        )
        overlay_html = recipe.render_overlay(self.contract, template, layout)

        self.assertIn("proof-card-3d", overlay_html)
        self.assertIn("+340% MRR", overlay_html)
        self.assertIn("VERIFIED GROWTH", overlay_html)
        self.assertIn("Client Case Study #12", overlay_html)

        # 3D motion and keyframes
        motion_js = recipe.motion_block(self.contract, layout, hook_exit_s=2.5, cta_start_s=38.0)
        self.assertIn(".proof-card-3d", motion_js)
        self.assertIn("rotationY", motion_js)

    def test_text_behind_subject_depth_layer(self):
        keyword = resolve_depth_keyword(self.contract)
        self.assertEqual(keyword, "REVENUE")

        recipe = get_recipe("studio_kinetic_reel")
        template = resolve_hyperframes_template("studio_kinetic_reel")
        layout = LayoutContext(
            width=1080,
            height=1920,
            is_landscape=False,
            caption_font_size=64,
            text_color="#ffffff",
            highlight_color="#facc15",
            accent="#00f5a0",
            secondary_accent="#00d2ff",
        )
        overlay_html = recipe.render_overlay(self.contract, template, layout)

        self.assertIn("depth-behind-subject", overlay_html)
        self.assertIn("depth-giant-word", overlay_html)
        self.assertIn("REVENUE", overlay_html)

    def test_subject_cutout_matting_graceful_fallback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target_dir = Path(tmpdir)
            result = generate_subject_depth_assets("/nonexistent/video.mp4", target_dir, self.contract)
            self.assertTrue(result["enabled"])
            self.assertEqual(result["depth_keyword"], "REVENUE")
            # If rembg is not installed, must fallback cleanly without exception
            if not is_rembg_available():
                self.assertFalse(result["has_cutout_matte"])
                self.assertIn("graceful depth fallback", result["reason"])

    def test_sound_design_filter_graph_and_assets(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target_dir = Path(tmpdir)
            assets = ensure_default_sound_assets(target_dir)

            self.assertTrue(assets["hook_boom"].exists())
            self.assertTrue(assets["whoosh"].exists())
            self.assertTrue(assets["ambient_bed"].exists())
            self.assertGreater(assets["hook_boom"].stat().st_size, 500)

            cfg = get_sound_design_config(self.contract)
            self.assertTrue(cfg["enabled"])
            self.assertEqual(cfg["music_volume"], 0.15)
            self.assertEqual(cfg["hook_volume"], 0.65)

            filter_graph, out_label = build_audio_ducking_filter_graph(
                speech_label="0:a",
                music_input_index=1,
                hook_input_index=2,
                config=cfg,
            )
            self.assertIn("sidechaincompress", filter_graph)
            self.assertIn("amix=inputs=3", filter_graph)
            self.assertEqual(out_label, "[a_out]")

    def test_html_composition_renders_studio_kinetic_reel(self):
        html = build_hyperframes_index_html(
            self.contract,
            hyperframes_template="studio_kinetic_reel",
            hyperframes_format="short_9_16",
        )
        self.assertIn('recipe-studio-kinetic-reel', html)
        self.assertIn('proof-card-3d', html)
        self.assertIn('depth-giant-word', html)
        self.assertIn('word-punch', html)
        self.assertIn('word-filler', html)


if __name__ == "__main__":
    unittest.main()
