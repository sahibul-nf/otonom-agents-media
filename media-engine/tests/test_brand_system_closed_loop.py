"""Brand system closed-loop: save path, starter resolve, Create wiring."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from media_engine import generation_jobs as generation_jobs_module
from media_engine import hyperframes_templates
from media_engine.hyperframes_renderer import build_hyperframes_index_html
from media_engine.hyperframes_templates import resolve_hyperframes_template, resolve_starter_template_id
from media_engine.rendering import build_premium_render_contract
from media_engine.styles import delete_brand_template, load_style, save_brand_system_template


class BrandSystemClosedLoopTests(unittest.TestCase):
    def test_resolve_starter_aliases(self):
        self.assertEqual(resolve_starter_template_id("eva_neon_cyber"), "neon_seize_future")
        self.assertEqual(resolve_starter_template_id("play_mode_social"), "cove_callout_pill")
        self.assertEqual(resolve_starter_template_id("missing"), "spiritual_reflective")

    def test_saved_brand_templates_expose_style_path_and_starter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profiles = root / "profiles"
            profiles.mkdir()
            payload = {
                "id": "custom_demo_brand",
                "label": "Demo Brand",
                "caption": {"highlight_word_color": "#ff2a85", "font_family": "Poppins", "font_size": 56},
                "brand": {"watermark_text": "Demo WM"},
                "brand_system": {
                    "starter_template": "eva_neon_cyber",
                    "caption_style": "caption-neon-glow",
                    "texture_effect": "shimmer-sweep",
                    "cta_overlay": "instagram-follow",
                    "intro_layout": "headline-slam",
                    "transition_family": "whip-pan",
                    "motion_intensity": "energetic",
                },
            }
            (profiles / "custom_demo_brand.json").write_text(json.dumps(payload), encoding="utf-8")
            with patch.object(hyperframes_templates, "ROOT", root):
                templates = hyperframes_templates._saved_brand_system_templates()
            self.assertEqual(len(templates), 1)
            item = templates[0]
            self.assertEqual(item["id"], "brand:custom_demo_brand")
            self.assertEqual(item["brand_template_path"], "profiles/custom_demo_brand.json")
            self.assertEqual(item["starter_template"], "neon_seize_future")
            self.assertEqual(item["recipe_module"], "neon_seize_future")

            with patch.object(hyperframes_templates, "ROOT", root):
                resolved = resolve_hyperframes_template("brand:custom_demo_brand")
            self.assertEqual(resolved["starter_template"], "neon_seize_future")
            self.assertEqual(resolved["recipe_module"], "neon_seize_future")
            self.assertEqual(resolved["brand_template_path"], "profiles/custom_demo_brand.json")

    def test_save_overwrite_keeps_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profiles = root / "profiles"
            profiles.mkdir()
            (profiles / "default_workspace_style.json").write_text(
                json.dumps({"id": "default_workspace_style", "caption": {}, "brand": {}}),
                encoding="utf-8",
            )
            with patch("media_engine.styles.ROOT", root), patch("media_engine.styles.PROFILES_DIR", profiles), patch(
                "media_engine.styles.DEFAULT_STYLE_PATH", profiles / "default_workspace_style.json"
            ):
                first = save_brand_system_template(
                    "My Brand Kit",
                    {"caption": {"font_family": "Sora"}, "brand": {"watermark_text": "Kit"}},
                    {"starter_template": "spiritual_reflective", "texture_effect": "grain-overlay"},
                )
                second = save_brand_system_template(
                    "My Brand Kit",
                    {"caption": {"font_family": "Inter"}, "brand": {"watermark_text": "Kit Updated"}},
                    {"starter_template": "eva_neon_cyber", "texture_effect": "vignette"},
                    target_path=first["path"],
                )
            self.assertEqual(first["path"], second["path"])
            loaded = json.loads((root / first["path"]).read_text(encoding="utf-8"))
            self.assertEqual(loaded["caption"]["font_family"], "Inter")
            self.assertEqual(loaded["brand_system"]["starter_template"], "eva_neon_cyber")
            self.assertEqual(loaded["brand"]["watermark_text"], "Kit Updated")

    def test_normalize_generation_wires_brand_style_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profiles = root / "profiles"
            profiles.mkdir()
            style_path = profiles / "custom_wired_brand.json"
            style_path.write_text(
                json.dumps(
                    {
                        "id": "custom_wired_brand",
                        "label": "Wired",
                        "brand_system": {"starter_template": "play_mode_social", "texture_effect": "grain-overlay"},
                        "caption": {},
                        "brand": {},
                    }
                ),
                encoding="utf-8",
            )
            (profiles / "default_workspace_style.json").write_text(json.dumps({"id": "default"}), encoding="utf-8")
            with patch.object(hyperframes_templates, "ROOT", root), patch.object(generation_jobs_module, "ROOT", root):
                config = generation_jobs_module.normalize_generation_payload(
                    {
                        "source_url": "https://youtube.com/watch?v=abc",
                        "hyperframes_template": "brand:custom_wired_brand",
                        "brand_system_template_id": "brand:custom_wired_brand",
                        "brand_template": "profiles/default_workspace_style.json",
                    }
                )
            self.assertEqual(config["brand_template"], "profiles/custom_wired_brand.json")
            self.assertEqual(config["hyperframes_template"], "brand:custom_wired_brand")

    def test_render_contract_prefers_style_watermark(self):
        candidate = {
            "id": "c1",
            "start_ms": 0,
            "end_ms": 25000,
            "title_hook": "Hook",
            "viral_reason": "reason",
            "hook_subtitle": "sub",
            "transcript_span": "hello world",
            "timed_captions": [
                {"startMs": 0, "endMs": 12000, "text": "hello", "words": [{"text": "hello", "startMs": 0, "endMs": 12000}]},
                {"startMs": 12000, "endMs": 24000, "text": "world", "words": [{"text": "world", "startMs": 12000, "endMs": 24000}]},
            ],
        }
        profile = {"id": "workspace", "watermark_text": "Profile WM", "cta_text": "Follow"}
        style = {
            "caption": {
                "preset": "mozi",
                "max_words_per_caption": 3,
                "highlight_word_color": "#00ff36",
                "font_family": "Poppins",
                "font_size": 54,
                "background_color": "#111111",
                "stroke_width": 8,
            },
            "brand": {"watermark_text": "Style WM"},
            "brand_system": {"texture_effect": "grain-overlay", "cta_overlay": "instagram-follow"},
        }
        with tempfile.NamedTemporaryFile(suffix=".mp4") as media:
            contract = build_premium_render_contract(
                candidate,
                profile,
                media.name,
                "https://example.com",
                "Source",
                style=style,
            )
        self.assertEqual(contract["watermarkText"], "Style WM")
        html = build_hyperframes_index_html(contract, "spiritual_reflective", "short_9_16")
        self.assertIn("Poppins", html)
        self.assertIn("brand-grain", html)
        self.assertIn("brand-social-pill", html)
        self.assertIn("Style WM", html)

    def test_delete_brand_template_removes_custom_file_and_catalog_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profiles = root / "profiles"
            profiles.mkdir()
            (profiles / "default_workspace_style.json").write_text(json.dumps({"id": "default"}), encoding="utf-8")
            style_path = profiles / "custom_delete_me.json"
            style_path.write_text(
                json.dumps(
                    {
                        "id": "custom_delete_me",
                        "label": "Delete Me",
                        "brand_system": {"starter_template": "spiritual_reflective"},
                        "caption": {},
                        "brand": {},
                    }
                ),
                encoding="utf-8",
            )
            preview_root = root / "artifacts" / "hyperframes_template_previews" / "brand__custom_delete_me" / "short_9_16"
            preview_root.mkdir(parents=True)
            (preview_root / "preview.mp4").write_bytes(b"preview")
            with patch("media_engine.styles.ROOT", root), patch("media_engine.styles.PROFILES_DIR", profiles), patch(
                "media_engine.styles.DEFAULT_STYLE_PATH", profiles / "default_workspace_style.json"
            ), patch.object(hyperframes_templates, "ROOT", root), patch(
                "media_engine.hyperframes_previews.PREVIEW_ROOT", root / "artifacts" / "hyperframes_template_previews"
            ):
                self.assertEqual(len(hyperframes_templates._saved_brand_system_templates()), 1)
                result = delete_brand_template(path="profiles/custom_delete_me.json")
                self.assertEqual(result["brand_id"], "brand:custom_delete_me")
                self.assertFalse(style_path.exists())
                self.assertEqual(hyperframes_templates._saved_brand_system_templates(), [])
                from media_engine.hyperframes_previews import clear_template_preview_cache

                self.assertTrue(clear_template_preview_cache("brand:custom_delete_me"))
                self.assertFalse(preview_root.exists())

    def test_delete_brand_template_rejects_builtin_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profiles = root / "profiles"
            profiles.mkdir()
            default_path = profiles / "default_workspace_style.json"
            default_path.write_text(json.dumps({"id": "default"}), encoding="utf-8")
            with patch("media_engine.styles.ROOT", root), patch("media_engine.styles.PROFILES_DIR", profiles), patch(
                "media_engine.styles.DEFAULT_STYLE_PATH", default_path
            ):
                with self.assertRaises(ValueError):
                    delete_brand_template(path="profiles/default_workspace_style.json")


if __name__ == "__main__":
    unittest.main()
