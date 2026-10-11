"""Overlay GSAP lifecycle + CTA/catalog guards for #100."""

from __future__ import annotations

import unittest

from media_engine.hyperframes_catalog import list_hyperframes_catalog
from media_engine.hyperframes_renderer import _overlay_exit_seconds, _overlay_lifecycle_js
from media_engine.hyperframes_previews import _brand_studio_preview_contract
from media_engine.hyperframes_renderer import build_hyperframes_index_html


class OverlayLifecycleTimingTests(unittest.TestCase):
    def test_exit_before_first_caption_peak(self):
        captions = [{"startMs": 0, "endMs": 2400, "text": "hello"}]
        exit_s = _overlay_exit_seconds(5000, captions)
        self.assertGreaterEqual(exit_s, 1.5)
        self.assertLess(exit_s, 2.4 * 0.55 + 0.7)

    def test_lifecycle_js_has_stagger_ambient_and_exit(self):
        js = _overlay_lifecycle_js(6000, [{"startMs": 0, "endMs": 3000}], overlay_exit_s=2.0)
        self.assertIn("overlayLayers", js)
        self.assertIn("stagger: 0.07", js)
        self.assertIn("sine.inOut", js)
        self.assertIn("overlayExitS = 2.000", js)
        self.assertNotIn("repeat: -1", js)

    def test_catalog_lifecycle_policy_covers_overlay_modes(self):
        catalog = list_hyperframes_catalog()
        policy = catalog["lifecycle_policy"]
        self.assertIn("enter-ambient-exit", policy)
        self.assertIn("word-timed", policy)
        lifecycles = {item.get("lifecycle") for item in catalog["items"]}
        self.assertTrue(lifecycles & {"outro", "enter-ambient", "word-timed", "ambient"})
        self.assertTrue(all(item.get("lifecycle") for item in catalog["items"]))

    def test_cta_and_caption_dedupe_in_brand_studio_html(self):
        phrase = "Unique hook phrase for dedupe check XYZ"
        contract = _brand_studio_preview_contract(
            "spiritual_reflective",
            "short_9_16",
            1080,
            1920,
            phrase,
            {"caption": {"font_family": "Lora"}, "brand": {"watermark_text": "Nourbit"}},
            {"texture_effect": "none", "cta_overlay": "yt-lower-third"},
        )
        html = build_hyperframes_index_html(contract, "spiritual_reflective", "short_9_16")
        before_captions = html.split("caption-text")[0]
        self.assertNotIn(phrase, before_captions)
        self.assertNotIn("brand-social-pill", html)
        self.assertNotIn('id="cta"', html)
        self.assertIn("overlayLayers", html)


if __name__ == "__main__":
    unittest.main()
