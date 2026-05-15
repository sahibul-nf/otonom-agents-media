import unittest

from media_engine.generation_jobs import build_generation_command, list_brand_templates, normalize_generation_payload


class GenerationJobTests(unittest.TestCase):
    def test_normalize_generation_payload_defaults_for_nourbit(self):
        payload = normalize_generation_payload({"source_url": "https://youtube.com/watch?v=test"})

        self.assertEqual(payload["profile_id"], "nourbit")
        self.assertEqual(payload["count"], 5)
        self.assertEqual(payload["clip_length_preset"], "deep_context")
        self.assertEqual(payload["renderer"], "remotion")
        self.assertEqual(payload["caption_source"], "whisper")
        self.assertEqual(payload["llm_provider"], "deepseek")

    def test_normalize_generation_payload_clamps_count_and_choices(self):
        payload = normalize_generation_payload(
            {
                "source_url": "https://youtube.com/watch?v=test",
                "count": 99,
                "renderer": "bad",
                "quality": "bad",
                "llm_provider": "bad",
            }
        )

        self.assertEqual(payload["count"], 10)
        self.assertEqual(payload["renderer"], "remotion")
        self.assertEqual(payload["quality"], "production")
        self.assertEqual(payload["llm_provider"], "deepseek")

    def test_build_generation_command_uses_premium_batch(self):
        payload = normalize_generation_payload({"source_url": "https://youtube.com/watch?v=test", "count": 2})
        command = build_generation_command(payload)

        self.assertIn("media_engine.cli", command)
        self.assertIn("premium-batch", command)
        self.assertIn("--count", command)
        self.assertIn("2", command)
        self.assertIn("--clip-length-preset", command)
        self.assertIn("deep_context", command)

    def test_brand_templates_include_nourbit_style(self):
        templates = list_brand_templates()
        self.assertTrue(any(item["path"] == "profiles/nourbit_opus_style.json" for item in templates))


if __name__ == "__main__":
    unittest.main()
