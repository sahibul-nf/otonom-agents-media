"""Tests for one-click shorts from long-form."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from media_engine.db import connect, initialize, seed_profile
from media_engine.longform_shorts import (
    LongformShortsError,
    make_shorts_from_longform,
    resolve_longform_shorts_source,
)


class LongformShortsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db_path = self.root / "test.sqlite"
        self.conn = connect(self.db_path)
        initialize(self.conn)
        seed_profile(
            self.conn,
            {
                "id": "nourbit",
                "name": "Nourbit",
                "niche": "Tech",
                "languages": ["id"],
                "default_render_preset": "short_clean",
                "cta_text": "",
                "watermark_text": "",
                "publish_targets": [],
            },
        )
        self.local_path = self.root / "long.mp4"
        self.local_path.write_bytes(b"\x00" * 4096)
        self.candidate_id = "cand_long_test"
        self.source_id = "ingest_job_test"
        self.conn.execute(
            "INSERT INTO source_manifests VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (self.source_id, "nourbit", f"file://{self.local_path}", "community", "authorized_community", "ok", "[]", 1, "", "[]"),
        )
        self.conn.execute(
            """
            INSERT INTO clip_candidates
              (id, profile_id, source_id, start_ms, end_ms, title_hook, hook_subtitle, viral_reason,
               transcript_span, risk_flags_json, score_json, curation_metadata_json,
               caption_source, asr_metadata_json, render_quality_json, cost_json,
               quality_gate_json, caption_corrections_json, dedupe_key, review_deadline_at, status)
            VALUES (?, 'nourbit', ?, 0, 60000, 'Long title', '', 'reason', 'span', '[]', '{}', ?, 'ingest_longform',
                    '{}', '{}', '{}', '{}', '{}', 'ingest:cand_long_test', '', 'approved')
            """,
            (
                self.candidate_id,
                self.source_id,
                json.dumps({"kind": "longform_ingest", "job_id": "ingest_job_test"}),
            ),
        )
        self.conn.execute(
            """
            INSERT INTO render_jobs
              (id, candidate_id, preset, crop_strategy, caption_style, status, output_path, metadata_json)
            VALUES ('render_long', ?, 'explainer_long_16_9', 'none', 'ingest_longform', 'rendered', ?, '{}')
            """,
            (self.candidate_id, str(self.local_path)),
        )
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def test_resolve_prefers_published_youtube_url(self):
        self.conn.execute(
            """
            INSERT INTO publish_attempts
              (id, candidate_id, platform, mode, status, payload_json, error)
            VALUES (?, ?, 'youtube_video', 'review_required', 'published', ?, '')
            """,
            (
                "pub_test",
                self.candidate_id,
                json.dumps(
                    {
                        "live_result": {
                            "remote_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                            "remote_id": "dQw4w9WgXcQ",
                        }
                    }
                ),
            ),
        )
        self.conn.commit()
        resolved = resolve_longform_shorts_source(self.conn, self.candidate_id)
        self.assertEqual(resolved["source_type"], "youtube")
        self.assertIn("dQw4w9WgXcQ", resolved["source_url"])

    def test_resolve_local_path_when_no_youtube(self):
        resolved = resolve_longform_shorts_source(self.conn, self.candidate_id)
        self.assertEqual(resolved["source_type"], "local")
        self.assertTrue(Path(resolved["local_path"]).exists())

    def test_make_shorts_missing_source_errors(self):
        self.local_path.unlink()
        with self.assertRaises(LongformShortsError):
            resolve_longform_shorts_source(self.conn, self.candidate_id)

    @patch("media_engine.longform_shorts.create_generation_job")
    def test_make_shorts_youtube_enqueues_generation_job(self, create_job):
        self.conn.execute(
            """
            INSERT INTO publish_attempts
              (id, candidate_id, platform, mode, status, payload_json, error)
            VALUES (?, ?, 'youtube_video', 'review_required', 'published', ?, '')
            """,
            (
                "pub_test",
                self.candidate_id,
                json.dumps({"live_result": {"remote_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}}),
            ),
        )
        self.conn.commit()
        create_job.return_value = {"id": "gen_test123"}
        result = make_shorts_from_longform(self.candidate_id, db_path=self.db_path)
        self.assertEqual(result["route"], "generation_job")
        self.assertEqual(result["generation_job_id"], "gen_test123")
        create_job.assert_called_once()
        payload = create_job.call_args.args[0]
        self.assertEqual(payload["hyperframes_format"], "short_9_16")
        self.assertEqual(payload["brand_template"], "auto")


if __name__ == "__main__":
    unittest.main()
