"""Tests for publish platform orientation filtering."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from media_engine.db import connect, initialize, seed_profile
from media_engine.publish_delivery import (
    candidate_delivery_orientation,
    filter_platforms_for_orientation,
    platform_compatible_with_orientation,
)
from media_engine.scheduler import schedule_candidate_next, update_schedule_platforms
from media_engine.workspace_profiles import ensure_default_publish_targets, sync_missing_publish_targets


class PublishDeliveryTests(unittest.TestCase):
    def test_longform_metadata_is_landscape(self):
        candidate = {
            "caption_source": "ingest_longform",
            "curation_metadata_json": json.dumps({"kind": "longform_ingest"}),
        }
        self.assertEqual(candidate_delivery_orientation(candidate), "landscape")

    def test_short_clip_defaults_portrait(self):
        candidate = {"curation_metadata_json": "{}"}
        self.assertEqual(candidate_delivery_orientation(candidate), "portrait")

    def test_landscape_blocks_vertical_targets(self):
        platforms = ["telegram_channel", "youtube_shorts", "youtube_video", "facebook_reels", "tiktok"]
        filtered = filter_platforms_for_orientation(platforms, "landscape")
        self.assertEqual(filtered, ["telegram_channel", "youtube_video"])
        self.assertFalse(platform_compatible_with_orientation("youtube_shorts", "landscape"))

    def test_portrait_blocks_youtube_video(self):
        platforms = ["telegram_channel", "youtube_shorts", "youtube_video"]
        filtered = filter_platforms_for_orientation(platforms, "portrait")
        self.assertEqual(filtered, ["telegram_channel", "youtube_shorts"])
        self.assertFalse(platform_compatible_with_orientation("youtube_video", "portrait"))


class SchedulerOrientationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.sqlite"
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
        ensure_default_publish_targets(self.conn, "nourbit", display_name="Nourbit")

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def test_schedule_longform_filters_to_youtube_video(self):
        self.conn.execute(
            "INSERT INTO source_manifests VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            ("src_long", "nourbit", "url", "community", "authorized_community", "ok", "[]", 1, "", "[]"),
        )
        self.conn.execute(
            """
            INSERT INTO clip_candidates
              (id, profile_id, source_id, status, title_hook, viral_reason, transcript_span,
               start_ms, end_ms, caption_source, curation_metadata_json, risk_flags_json)
            VALUES ('clip_long', 'nourbit', 'src_long', 'approved', 'Long title', 'reason', 'span',
                    0, 60000, 'ingest_longform', ?, '[]')
            """,
            (json.dumps({"kind": "longform_ingest"}),),
        )
        self.conn.commit()
        result = schedule_candidate_next(self.conn, "clip_long")
        row = self.conn.execute(
            "SELECT platforms_json FROM scheduled_posts WHERE id = ?",
            (result["id"],),
        ).fetchone()
        platforms = json.loads(row["platforms_json"])
        self.assertIn("youtube_video", platforms)
        self.assertNotIn("youtube_shorts", platforms)
        self.assertNotIn("facebook_reels", platforms)

    def test_update_schedule_platforms_rejects_incompatible(self):
        self.conn.execute(
            "INSERT INTO source_manifests VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            ("src_short", "nourbit", "url", "community", "authorized_community", "ok", "[]", 1, "", "[]"),
        )
        self.conn.execute(
            """
            INSERT INTO clip_candidates
              (id, profile_id, source_id, status, title_hook, viral_reason, transcript_span,
               start_ms, end_ms, caption_source, curation_metadata_json, risk_flags_json)
            VALUES ('clip_short', 'nourbit', 'src_short', 'approved', 'Hook', 'reason', 'span',
                    0, 30000, 'whisper', '{}', '[]')
            """
        )
        self.conn.execute(
            """
            INSERT INTO scheduled_posts
              (id, candidate_id, profile_id, scheduled_at, status, publish_mode, platforms_json)
            VALUES ('sched_1', 'clip_short', 'nourbit', '2026-08-26T09:00+07:00', 'scheduled', 'scheduled_publish', '[]')
            """
        )
        self.conn.commit()
        with self.assertRaises(ValueError):
            update_schedule_platforms(self.conn, "sched_1", ["youtube_video"])


class WorkspacePublishTargetSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.sqlite"
        self.conn = connect(self.db_path)
        initialize(self.conn)
        seed_profile(
            self.conn,
            {
                "id": "legacy",
                "name": "Legacy",
                "niche": "Tech",
                "languages": ["id"],
                "default_render_preset": "short_clean",
                "cta_text": "",
                "watermark_text": "",
                "publish_targets": [
                    {
                        "platform": "telegram_channel",
                        "account_label": "Legacy Telegram",
                        "mode": "review_required",
                    },
                    {
                        "platform": "youtube_shorts",
                        "account_label": "Legacy Shorts",
                        "mode": "review_required",
                    },
                ],
            },
        )

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def test_sync_missing_publish_targets_adds_youtube_video(self):
        created = sync_missing_publish_targets(self.conn, "legacy", display_name="Legacy")
        self.assertIn("youtube_video", created)
        platforms = [
            row[0]
            for row in self.conn.execute(
                "SELECT platform FROM publish_targets WHERE profile_id = ? ORDER BY platform",
                ("legacy",),
            ).fetchall()
        ]
        self.assertIn("youtube_video", platforms)


if __name__ == "__main__":
    unittest.main()
