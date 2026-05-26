import unittest

from media_engine.hyperframes_templates import (
    DEFAULT_TEMPLATE_ID,
    dimensions_for_format,
    list_hyperframes_templates,
    normalize_hyperframes_format,
    normalize_hyperframes_template,
    resolve_hyperframes_template,
)


class HyperframesTemplateTests(unittest.TestCase):
    def test_lists_curated_template_pack(self):
        templates = list_hyperframes_templates()

        self.assertGreaterEqual(len(templates), 13)
        self.assertEqual({template["status"] for template in templates}, {"ready"})
        self.assertTrue(any(template["id"] == "data_market_explainer" for template in templates))
        self.assertTrue(any(template["id"] == "warm_grain_editorial" for template in templates))

    def test_explicit_override_wins(self):
        template = resolve_hyperframes_template("product_brand_promo", genres=["kajian"])

        self.assertEqual(template["id"], "product_brand_promo")

    def test_auto_selects_by_genre(self):
        self.assertEqual(resolve_hyperframes_template("auto", genres=["crypto"])["id"], "data_market_explainer")
        self.assertEqual(resolve_hyperframes_template("auto", genres=["interview"])["id"], "podcast_talking_head")
        self.assertEqual(resolve_hyperframes_template("auto", genres=["geopolitics"])["id"], "news_geo_brief")

    def test_unknown_values_fall_back_to_auto_then_default(self):
        self.assertEqual(normalize_hyperframes_template("missing"), "auto")
        self.assertEqual(resolve_hyperframes_template("missing", genres=["unknown"])["id"], DEFAULT_TEMPLATE_ID)

    def test_legacy_specific_template_aliases_to_public_template(self):
        self.assertEqual(normalize_hyperframes_template("nourbit_reflective"), "spiritual_reflective")

    def test_templates_expose_preview_contract(self):
        template = list_hyperframes_templates()[0]

        self.assertEqual(template["preview_seconds"], 15)
        self.assertIn("short_9_16", template["preview_urls"])
        self.assertIn("lint", template["production_checks"])
        self.assertIn("/api/media/hyperframes-template-preview", template["preview_urls"]["short_9_16"])

    def test_format_dimensions(self):
        self.assertEqual(normalize_hyperframes_format("bad"), "auto")
        self.assertEqual(dimensions_for_format("short_9_16"), (1080, 1920, "short_9_16"))
        self.assertEqual(dimensions_for_format("long_16_9"), (1920, 1080, "long_16_9"))
        self.assertEqual(dimensions_for_format("auto"), (1080, 1920, "short_9_16"))


if __name__ == "__main__":
    unittest.main()
