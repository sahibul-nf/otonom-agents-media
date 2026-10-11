"""LLM Brand Studio (#80) validation + workspace default."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from media_engine.brand_studio_llm import (
    BrandStudioLlmError,
    generate_brand_from_prompt,
    heuristic_brand_from_prompt,
    set_workspace_default_template,
    validate_brand_studio_payload,
)
from media_engine.hyperframes_templates import TEMPLATE_BY_ID


class BrandStudioLlmTests(unittest.TestCase):
    def test_validate_maps_unknown_starter_to_default(self):
        result = validate_brand_studio_payload(
            {
                "starter_template": "totally_fake_recipe",
                "caption_style": "not-a-real-caption",
                "cta_overlay": "x-post",
                "highlight_color": "#abc",
                "label": "Test",
            }
        )
        self.assertIn(result["starter_template"], TEMPLATE_BY_ID)
        self.assertEqual(result["brand_system"]["caption_style"], "caption-editorial-emphasis")
        self.assertEqual(result["brand_system"]["cta_overlay"], "none")
        self.assertEqual(result["style"]["caption"]["highlight_word_color"], "#aabbcc")

    def test_heuristic_neon_picks_eva(self):
        result = heuristic_brand_from_prompt("Neon cyber glow for short clips")
        self.assertEqual(result["starter_template"], "eva_neon_cyber")
        self.assertEqual(result["brand_system"]["caption_style"], "caption-neon-glow")

    def test_generate_uses_heuristic_without_llm(self):
        with mock.patch("media_engine.brand_studio_llm.llm_provider_ready", return_value={"ready": False}):
            result = generate_brand_from_prompt(
                "Calm soft gold edutainment for finance beginners",
                llm_provider="auto",
                allow_heuristic_fallback=True,
            )
        self.assertEqual(result["source"], "heuristic")
        self.assertTrue(result["brand_system"]["starter_template"])

    def test_generate_rejects_short_prompt(self):
        with self.assertRaises(BrandStudioLlmError):
            generate_brand_from_prompt("hi")

    def test_set_workspace_default_to_custom(self):
        with tempfile.TemporaryDirectory() as tmp:
            profiles = Path(tmp) / "profiles"
            profiles.mkdir()
            custom = profiles / "custom_prompt_look.json"
            custom.write_text(json.dumps({"id": "custom_prompt_look", "label": "Look"}), encoding="utf-8")
            workspace = profiles / "default_workspace_style.json"
            workspace.write_text(
                json.dumps({"label": "WS", "hyperframes": {"default_template": "spiritual_reflective"}}),
                encoding="utf-8",
            )

            def fake_resolve(path=None):
                if path is None:
                    return workspace
                text = str(path)
                if "custom_prompt_look" in text:
                    return custom
                return Path(text)

            with mock.patch("media_engine.brand_studio_llm.PROFILES_DIR", profiles):
                with mock.patch("media_engine.brand_studio_llm.DEFAULT_STYLE_PATH", workspace):
                    with mock.patch("media_engine.brand_studio_llm.resolve_style_path", side_effect=fake_resolve):
                        with mock.patch(
                            "media_engine.brand_studio_llm.load_style",
                            return_value=json.loads(workspace.read_text(encoding="utf-8")),
                        ):
                            result = set_workspace_default_template("brand:custom_prompt_look")
            self.assertEqual(result["default_template"], "brand:custom_prompt_look")
            saved = json.loads(workspace.read_text(encoding="utf-8"))
            self.assertEqual(saved["hyperframes"]["default_template"], "brand:custom_prompt_look")


if __name__ == "__main__":
    unittest.main()
