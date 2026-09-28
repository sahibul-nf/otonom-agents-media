import unittest

from media_engine.hyperframes_catalog import CATALOG_ITEMS, OSS_SECTIONS, list_hyperframes_catalog


class HyperframesCatalogTests(unittest.TestCase):
    def test_catalog_exposes_official_oss_sections(self):
        payload = list_hyperframes_catalog()
        self.assertIn("oss_sections", payload)
        self.assertIn("oss_groups", payload)
        for section in OSS_SECTIONS:
            self.assertIn(section, payload["oss_sections"])

    def test_every_item_has_oss_section_and_lifecycle(self):
        for item in CATALOG_ITEMS:
            self.assertIn(item["oss_section"], OSS_SECTIONS)
            self.assertTrue(item.get("lifecycle"))

    def test_caption_items_use_word_timed_lifecycle(self):
        captions = [item for item in CATALOG_ITEMS if item["oss_section"] == "Captions"]
        self.assertTrue(captions)
        for item in captions:
            self.assertEqual(item["lifecycle"], "word-timed")


if __name__ == "__main__":
    unittest.main()
