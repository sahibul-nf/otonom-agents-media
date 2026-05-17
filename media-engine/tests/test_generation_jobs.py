import tempfile
import unittest

from media_engine.duration_presets import duration_preset_options, resolve_duration_preset
from media_engine.db import connect, initialize
from media_engine.generation_jobs import build_generation_command, list_brand_templates, normalize_generation_payload, reconcile_generation_jobs


class GenerationJobTests(unittest.TestCase):
    def test_duration_presets_expose_canonical_options(self):
        options = duration_preset_options()

        self.assertEqual([item["id"] for item in options], ["auto", "under_30s", "seconds_30_60", "minutes_1_3", "minutes_3_plus"])
        self.assertEqual([item["range_label"] for item in options], ["0-3 min", "Under 30s", "30s-60s", "1-3 min", "3+ min"])
        self.assertEqual(resolve_duration_preset("45-120s").id, "minutes_1_3")
        self.assertEqual(resolve_duration_preset("quick_hit").id, "seconds_30_60")
        self.assertEqual(resolve_duration_preset("unknown").id, "auto")

    def test_normalize_generation_payload_defaults_for_nourbit(self):
        payload = normalize_generation_payload({"source_url": "https://youtube.com/watch?v=test"})

        self.assertEqual(payload["profile_id"], "nourbit")
        self.assertEqual(payload["count"], 5)
        self.assertEqual(payload["clip_length_preset"], "auto")
        self.assertEqual(payload["clip_min_seconds"], 20)
        self.assertEqual(payload["clip_max_seconds"], 180)
        self.assertEqual(payload["genres"], ["kajian", "spiritual_reflection", "advice"])
        self.assertEqual(payload["renderer"], "remotion")
        self.assertEqual(payload["caption_source"], "whisper")
        self.assertEqual(payload["speech_language"], "id")
        self.assertEqual(payload["transcript_languages"], "id,en")
        self.assertEqual(payload["llm_provider"], "deepseek")

    def test_normalize_generation_payload_canonicalizes_legacy_clip_length(self):
        payload = normalize_generation_payload({"source_url": "https://youtube.com/watch?v=test", "clip_length_preset": "30-60s"})

        self.assertEqual(payload["clip_length_preset"], "seconds_30_60")

    def test_normalize_generation_payload_accepts_custom_duration_and_genres(self):
        payload = normalize_generation_payload(
            {
                "source_url": "https://youtube.com/watch?v=test",
                "clip_length_preset": "custom",
                "clip_min_seconds": 40,
                "clip_max_seconds": 110,
                "genres": ["story", "advice", "unknown", "story"],
            }
        )

        self.assertEqual(payload["clip_length_preset"], "custom")
        self.assertEqual(payload["clip_min_seconds"], 40)
        self.assertEqual(payload["clip_max_seconds"], 110)
        self.assertEqual(payload["genres"], ["story", "advice"])

    def test_normalize_generation_payload_clamps_count_and_choices(self):
        payload = normalize_generation_payload(
            {
                "source_url": "https://youtube.com/watch?v=test",
                "count": 99,
                "renderer": "bad",
                "quality": "bad",
                "llm_provider": "bad",
                "speech_language": "bad",
                "transcript_languages": "bad,ar,id",
            }
        )

        self.assertEqual(payload["count"], 10)
        self.assertEqual(payload["renderer"], "remotion")
        self.assertEqual(payload["quality"], "production")
        self.assertEqual(payload["llm_provider"], "deepseek")
        self.assertEqual(payload["speech_language"], "id")
        self.assertEqual(payload["transcript_languages"], "ar,id")

    def test_build_generation_command_uses_premium_batch(self):
        payload = normalize_generation_payload({"source_url": "https://youtube.com/watch?v=test", "count": 2})
        command = build_generation_command(payload)

        self.assertIn("media_engine.cli", command)
        self.assertIn("premium-batch", command)
        self.assertIn("--count", command)
        self.assertIn("2", command)
        self.assertIn("--clip-length-preset", command)
        self.assertIn("auto", command)
        self.assertIn("--clip-min-seconds", command)
        self.assertIn("--clip-max-seconds", command)
        self.assertIn("--genres", command)
        self.assertIn("--speech-language", command)
        self.assertIn("--transcript-languages", command)

    def test_brand_templates_include_nourbit_style(self):
        templates = list_brand_templates()
        self.assertTrue(any(item["path"] == "profiles/nourbit_opus_style.json" for item in templates))

    def test_reconcile_generation_jobs_marks_stale_running_jobs_failed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = connect(f"{tmpdir}/media_engine.sqlite")
            initialize(conn)
            conn.execute(
                "INSERT INTO media_profiles (id, name, niche, languages_json, default_render_preset, cta_text, watermark_text) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("nourbit", "Nourbit", "kajian", "[]", "premium", "cta", "watermark"),
            )
            conn.execute(
                """
                INSERT INTO generation_jobs
                (id, profile_id, source_id, source_url, count, brand_template, renderer, quality, caption_source, asr_model, llm_provider, status, progress, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', '-30 minutes'))
                """,
                ("gen_stale", "nourbit", "source_a", "https://youtube.com/watch?v=test", 5, "profiles/nourbit_opus_style.json", "remotion", "production", "whisper", "medium", "deepseek", "running", 95),
            )
            changed = reconcile_generation_jobs(conn, stale_minutes=15)
            row = conn.execute("SELECT status, progress, error, log_text FROM generation_jobs WHERE id = ?", ("gen_stale",)).fetchone()
            conn.close()

        self.assertEqual(changed, 1)
        self.assertEqual(row["status"], "failed")
        self.assertEqual(row["progress"], 100)
        self.assertIn("lost heartbeat", row["error"])
        self.assertIn("stale heartbeat timeout", row["log_text"])

    def test_reconcile_generation_jobs_keeps_fresh_running_jobs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            conn = connect(f"{tmpdir}/media_engine.sqlite")
            initialize(conn)
            conn.execute(
                "INSERT INTO media_profiles (id, name, niche, languages_json, default_render_preset, cta_text, watermark_text) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("nourbit", "Nourbit", "kajian", "[]", "premium", "cta", "watermark"),
            )
            conn.execute(
                """
                INSERT INTO generation_jobs
                (id, profile_id, source_id, source_url, count, brand_template, renderer, quality, caption_source, asr_model, llm_provider, status, progress, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                ("gen_fresh", "nourbit", "source_a", "https://youtube.com/watch?v=test", 5, "profiles/nourbit_opus_style.json", "remotion", "production", "whisper", "medium", "deepseek", "running", 40),
            )
            changed = reconcile_generation_jobs(conn, stale_minutes=15)
            row = conn.execute("SELECT status, progress FROM generation_jobs WHERE id = ?", ("gen_fresh",)).fetchone()
            conn.close()

        self.assertEqual(changed, 0)
        self.assertEqual(row["status"], "running")
        self.assertEqual(row["progress"], 40)


if __name__ == "__main__":
    unittest.main()
