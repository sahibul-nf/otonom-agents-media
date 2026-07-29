"""Tests for channel watch → auto-clip enqueue and delivery settings."""

from __future__ import annotations

import json
import sqlite3
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from media_engine.autonomy import evaluate_quality_gate, get_autonomy_settings, update_autonomy_settings
from media_engine.channel_watcher import (
    add_watch_channel,
    list_watch_channels,
    normalize_channel_url,
    poll_watch_channel,
    update_publish_target,
    update_watch_channel,
)
from media_engine.db import initialize
from media_engine.scheduler import DEFAULT_TZ, enabled_delivery_platforms, process_due_auto_schedule


class ChannelWatcherTests(unittest.TestCase):
    def _conn(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        initialize(conn)
        conn.execute(
            "INSERT INTO media_profiles VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            ("nourbit", "Nourbit", "niche", "[]", "preset", "cta", "wm"),
        )
        conn.execute(
            """
            INSERT INTO publish_targets
              (profile_id, platform, account_label, mode, require_approval, ai_disclosure_required, daily_cap, enabled)
            VALUES (?, ?, ?, ?, 1, 0, ?, 1)
            """,
            ("nourbit", "facebook_reels", "Nourbit FB", "review_required", 2),
        )
        conn.execute(
            """
            INSERT INTO publish_targets
              (profile_id, platform, account_label, mode, require_approval, ai_disclosure_required, daily_cap, enabled)
            VALUES (?, ?, ?, ?, 1, 0, ?, 1)
            """,
            ("nourbit", "youtube_shorts", "Nourbit YT", "review_required", 1),
        )
        return conn

    def test_normalize_channel_url_handle(self):
        url = normalize_channel_url("https://www.youtube.com/@nouraniyyahofficial")
        self.assertEqual(url, "https://www.youtube.com/@nouraniyyahofficial/videos")

    def test_add_watch_channel_bootstraps_seen_without_enqueue(self):
        conn = self._conn()
        videos = [{"id": "vid_old", "title": "Old", "url": "https://www.youtube.com/watch?v=vid_old"}]
        with patch("media_engine.channel_watcher.list_channel_video_ids", return_value=videos):
            channel = add_watch_channel(
                conn,
                channel_url="https://youtube.com/@nouraniyyahofficial",
                profile_id="nourbit",
                label="Nouraniyyah",
            )
        self.assertEqual(channel["last_seen_video_id"], "vid_old")
        self.assertTrue(channel["enabled"])
        self.assertEqual(len(list_watch_channels(conn, "nourbit")), 1)
        conn.close()

    def test_poll_enqueues_only_new_videos(self):
        conn = self._conn()
        with patch(
            "media_engine.channel_watcher.list_channel_video_ids",
            return_value=[{"id": "vid_a", "title": "A", "url": "https://www.youtube.com/watch?v=vid_a"}],
        ):
            channel = add_watch_channel(
                conn,
                channel_url="https://youtube.com/@nouraniyyahofficial",
                profile_id="nourbit",
                label="Nouraniyyah",
            )

        newer = [
            {"id": "vid_b", "title": "B", "url": "https://www.youtube.com/watch?v=vid_b"},
            {"id": "vid_a", "title": "A", "url": "https://www.youtube.com/watch?v=vid_a"},
        ]
        fake_job = {"id": "gen_test", "status": "queued"}
        with (
            patch("media_engine.channel_watcher.list_channel_video_ids", return_value=newer),
            patch("media_engine.channel_watcher.create_generation_job", return_value=fake_job) as create_job,
        ):
            result = poll_watch_channel(conn, channel["id"], enqueue=True, force=True)

        self.assertEqual([v["id"] for v in result["new_videos"]], ["vid_b"])
        self.assertEqual(len(result["jobs"]), 1)
        create_job.assert_called_once()
        payload = create_job.call_args.args[0]
        self.assertEqual(payload["source_url"], "https://www.youtube.com/watch?v=vid_b")
        self.assertEqual(payload["profile_id"], "nourbit")
        updated = list_watch_channels(conn, "nourbit")[0]
        self.assertEqual(updated["last_seen_video_id"], "vid_b")
        self.assertEqual(updated["last_clip_job_id"], "gen_test")
        conn.close()

    def test_pause_skips_poll_unless_forced(self):
        conn = self._conn()
        with patch(
            "media_engine.channel_watcher.list_channel_video_ids",
            return_value=[{"id": "vid_a", "title": "A", "url": "https://www.youtube.com/watch?v=vid_a"}],
        ):
            channel = add_watch_channel(
                conn,
                channel_url="https://youtube.com/@nouraniyyahofficial",
                profile_id="nourbit",
            )
        update_watch_channel(conn, channel["id"], {"enabled": False})
        result = poll_watch_channel(conn, channel["id"], enqueue=True, force=False)
        self.assertEqual(result["skipped"], "paused")
        conn.close()

    def test_full_autonomy_deadline_is_immediate(self):
        conn = self._conn()
        update_autonomy_settings(conn, "nourbit", {"autonomy_mode": "full", "review_grace_hours": 12})
        settings = get_autonomy_settings(conn, "nourbit")
        gate = evaluate_quality_gate(
            {
                "score": {"overall_score": 90, "hook_score": 90, "asr_confidence": 95},
                "curation_metadata": {"boundary_confidence": 90},
                "asr_metadata": {"low_confidence_word_count": 0},
            },
            settings,
            now=datetime(2026, 5, 15, 9, 0, tzinfo=DEFAULT_TZ),
        )
        self.assertEqual(gate["status"], "pending_auto_schedule")
        self.assertIn("2026-05-15T09:00", gate["review_deadline_at"])
        conn.close()

    def test_delivery_daily_cap_filters_platforms(self):
        conn = self._conn()
        conn.execute(
            """
            INSERT INTO source_manifests
              (id, profile_id, source_url, owner_type, permission_status,
               allowed_use_json, publish_restrictions_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("source", "nourbit", "https://example.com", "public", "review_required", "{}", "{}"),
        )
        conn.execute(
            """
            INSERT INTO clip_candidates
              (id, profile_id, source_id, start_ms, end_ms, title_hook, viral_reason,
               transcript_span, risk_flags_json, status)
            VALUES (?, ?, ?, 0, 1000, 'H', 'R', 'T', '[]', 'scheduled')
            """,
            ("clip1", "nourbit", "source"),
        )
        now = datetime(2026, 5, 15, 12, 0, tzinfo=DEFAULT_TZ)
        conn.execute(
            """
            INSERT INTO scheduled_posts
              (id, candidate_id, profile_id, scheduled_at, status, publish_mode, platforms_json)
            VALUES (?, ?, ?, ?, 'scheduled', 'scheduled_publish', ?)
            """,
            ("sched1", "clip1", "nourbit", now.isoformat(timespec="minutes"), json.dumps(["youtube_shorts"])),
        )
        conn.commit()
        platforms = enabled_delivery_platforms(conn, "nourbit", now=now)
        self.assertIn("facebook_reels", platforms)
        self.assertNotIn("youtube_shorts", platforms)

        update_publish_target(conn, {"id": conn.execute("SELECT id FROM publish_targets WHERE platform='facebook_reels'").fetchone()["id"], "daily_cap": 1, "enabled": True})
        # Still capacity on FB (0 posts today)
        platforms = enabled_delivery_platforms(conn, "nourbit", now=now)
        self.assertEqual(platforms, ["facebook_reels"])
        conn.close()

    def test_full_mode_schedules_when_due(self):
        conn = self._conn()
        update_autonomy_settings(conn, "nourbit", {"autonomy_mode": "full", "review_grace_hours": 12})
        conn.execute(
            """
            INSERT INTO source_manifests
              (id, profile_id, source_url, owner_type, permission_status,
               allowed_use_json, publish_restrictions_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("source", "nourbit", "https://example.com", "public", "review_required", "{}", "{}"),
        )
        deadline = datetime(2026, 5, 15, 9, 0, tzinfo=DEFAULT_TZ)
        conn.execute(
            """
            INSERT INTO clip_candidates
              (id, profile_id, source_id, start_ms, end_ms, title_hook, viral_reason,
               transcript_span, risk_flags_json, quality_gate_json, review_deadline_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "clip_auto",
                "nourbit",
                "source",
                0,
                60_000,
                "Hook",
                "Reason",
                "Transcript",
                "[]",
                json.dumps({"passed": True}),
                deadline.isoformat(timespec="minutes"),
                "pending_auto_schedule",
            ),
        )
        conn.commit()
        due = process_due_auto_schedule(conn, "nourbit", now=deadline + timedelta(minutes=1))
        self.assertEqual(len(due), 1)
        conn.close()


if __name__ == "__main__":
    unittest.main()
