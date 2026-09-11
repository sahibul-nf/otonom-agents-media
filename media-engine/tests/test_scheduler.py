import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from unittest.mock import patch

from media_engine.db import initialize
from media_engine.schedule_publisher import archive_legacy_permission_attempts, process_due_publishes
from media_engine.scheduler import list_scheduled_posts, schedule_candidate_next, unschedule_candidate, update_schedule, update_schedule_platforms


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        initialize(self.conn)
        self.conn.execute(
            "INSERT INTO media_profiles VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            ("nourbit", "Nourbit", "niche", "[]", "lecture_clean", "cta", "wm"),
        )
        self.conn.execute(
            "INSERT INTO source_manifests VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            ("src", "nourbit", "url", "community", "authorized_community", "ok", "[]", 1, "", "[]"),
        )
        self._uses_postiz = [
            patch("media_engine.postiz_sync.uses_postiz", return_value=False),
            patch("media_engine.schedule_publisher.uses_postiz", return_value=False),
        ]
        for item in self._uses_postiz:
            item.start()

    def tearDown(self):
        for item in self._uses_postiz:
            item.stop()
        self.conn.close()

    def add_clip(self, candidate_id="clip", status="approved"):
        self.conn.execute(
            """
            INSERT INTO clip_candidates
              (id, profile_id, source_id, start_ms, end_ms, title_hook, viral_reason,
               transcript_span, risk_flags_json, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (candidate_id, "nourbit", "src", 0, 1000, "Hook", "Reason", "Text", "[]", status),
        )
        self.conn.commit()

    def test_schedule_next_uses_two_daily_slots(self):
        tz = ZoneInfo("Asia/Jakarta")
        self.add_clip("clip1")
        self.add_clip("clip2")
        self.add_clip("clip3")
        now = datetime(2026, 5, 15, 8, 0, tzinfo=tz)

        first = schedule_candidate_next(self.conn, "clip1", now=now)
        second = schedule_candidate_next(self.conn, "clip2", now=now)
        third = schedule_candidate_next(self.conn, "clip3", now=now)

        self.assertIn("2026-05-15T09:00", first["scheduled_at"])
        self.assertIn("2026-05-15T19:30", second["scheduled_at"])
        self.assertIn("2026-05-16T09:00", third["scheduled_at"])

    def test_schedule_next_accepts_custom_datetime(self):
        tz = ZoneInfo("Asia/Jakarta")
        self.add_clip()
        now = datetime(2026, 5, 15, 8, 0, tzinfo=tz)
        scheduled = schedule_candidate_next(
            self.conn,
            "clip",
            now=now,
            scheduled_at="2026-05-20T14:45:00+07:00",
        )
        self.assertIn("2026-05-20T14:45", scheduled["scheduled_at"])
        with self.assertRaises(ValueError):
            schedule_candidate_next(self.conn, "clip", now=now, scheduled_at="2026-05-15T07:00:00+07:00")

    def test_only_approved_clips_can_be_scheduled(self):
        self.add_clip(status="rendered")
        with self.assertRaises(ValueError):
            schedule_candidate_next(self.conn, "clip")

    def test_unschedule_returns_candidate_to_approved(self):
        self.add_clip()
        schedule_candidate_next(self.conn, "clip", now=datetime(2026, 5, 15, 8, 0, tzinfo=ZoneInfo("Asia/Jakarta")))
        unschedule_candidate(self.conn, "clip")

        row = self.conn.execute("SELECT status FROM clip_candidates WHERE id = 'clip'").fetchone()
        self.assertEqual(row["status"], "approved")
        self.assertEqual(list_scheduled_posts(self.conn), [])

    def test_unschedule_blocks_when_a_destination_is_live(self):
        self.add_clip()
        scheduled = schedule_candidate_next(
            self.conn,
            "clip",
            platforms=["facebook_reels"],
            now=datetime(2026, 5, 15, 8, 0, tzinfo=ZoneInfo("Asia/Jakarta")),
        )
        self.conn.execute(
            "UPDATE scheduled_posts SET platform_results_json = ? WHERE id = ?",
            (
                '{"facebook_reels": {"status": "live", "backend": "postiz", "remote_id": "cmtty4e5j0000o57xio46nplv"}}',
                scheduled["id"],
            ),
        )
        self.conn.commit()
        with self.assertRaises(ValueError):
            unschedule_candidate(self.conn, "clip")

    def test_update_schedule_platforms_overrides_targets(self):
        self.add_clip("clip")
        scheduled = schedule_candidate_next(
            self.conn,
            "clip",
            platforms=["telegram_channel", "youtube_shorts", "facebook_reels"],
            now=datetime(2026, 5, 15, 8, 0, tzinfo=ZoneInfo("Asia/Jakarta")),
        )

        updated = update_schedule_platforms(self.conn, scheduled["id"], ["telegram_channel", "tiktok"])
        item = list_scheduled_posts(self.conn)[0]

        self.assertEqual(updated["platforms"], ["telegram_channel", "tiktok"])
        self.assertEqual(item["platforms"], ["telegram_channel", "tiktok"])

    def test_update_schedule_persists_time(self):
        self.add_clip("clip")
        scheduled = schedule_candidate_next(
            self.conn,
            "clip",
            platforms=["telegram_channel"],
            now=datetime(2026, 5, 15, 8, 0, tzinfo=ZoneInfo("Asia/Jakarta")),
        )
        updated = update_schedule(self.conn, scheduled["id"], "2027-05-16T11:15+07:00")
        item = list_scheduled_posts(self.conn)[0]
        self.assertIn("2027-05-16T11:15", updated["scheduled_at"])
        self.assertIn("2027-05-16T11:15", item["scheduled_at"])
        self.assertEqual(updated["status"], "scheduled")

    def test_legacy_permission_attempts_are_archived(self):
        self.add_clip("clip")
        self.conn.execute(
            """
            INSERT INTO publish_attempts
              (id, candidate_id, platform, mode, status, payload_json, error)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "pub",
                "clip",
                "telegram_channel",
                "review_required",
                "blocked",
                "{}",
                "public third-party sources require permission evidence before platform publishing",
            ),
        )
        self.conn.commit()

        count = archive_legacy_permission_attempts(self.conn)
        status = self.conn.execute("SELECT status FROM publish_attempts WHERE id = 'pub'").fetchone()["status"]

        self.assertEqual(count, 1)
        self.assertEqual(status, "legacy_blocked")

    def test_due_publish_processes_platforms_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/media_engine.sqlite"
            video_path = f"{tmpdir}/clip.mp4"
            Path(video_path).write_bytes(b"video")
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            initialize(conn)
            conn.execute(
                "INSERT INTO media_profiles VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                ("nourbit", "Nourbit", "niche", "[]", "lecture_clean", "cta", "wm"),
            )
            conn.execute(
                "INSERT INTO source_manifests VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                ("src", "nourbit", "url", "community", "public_third_party", "", "[]", 1, "", "[]"),
            )
            for platform in ["telegram_channel", "youtube_shorts"]:
                conn.execute(
                    """
                    INSERT INTO publish_targets
                      (profile_id, platform, account_label, mode, require_approval, ai_disclosure_required, daily_cap)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("nourbit", platform, platform, "review_required", 1, 0, 2),
                )
            conn.execute(
                """
                INSERT INTO clip_candidates
                  (id, profile_id, source_id, start_ms, end_ms, title_hook, viral_reason,
                   transcript_span, risk_flags_json, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("clip", "nourbit", "src", 0, 1000, "Hook", "Reason", "Text", "[]", "scheduled"),
            )
            conn.execute(
                """
                INSERT INTO render_jobs
                  (id, candidate_id, preset, crop_strategy, caption_style, status, output_path, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("render", "clip", "premium", "center", "caption", "rendered", video_path, "{}"),
            )
            conn.execute(
                """
                INSERT INTO scheduled_posts
                  (id, candidate_id, profile_id, scheduled_at, status, publish_mode, platforms_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "sched",
                    "clip",
                    "nourbit",
                    "2026-05-15T09:00+07:00",
                    "scheduled",
                    "scheduled_publish",
                    '["telegram_channel", "youtube_shorts"]',
                ),
            )
            conn.commit()
            conn.close()

            calls = []

            def fake_publish(platform, payload, **_kwargs):
                calls.append(platform)
                return {"platform": platform, "status": "published", "remote_id": f"{platform}_id"}

            now = datetime(2026, 5, 15, 10, 0, tzinfo=ZoneInfo("Asia/Jakarta"))
            with patch("media_engine.schedule_publisher.publish_live_payload", side_effect=fake_publish):
                first = process_due_publishes(db_path=db_path, now=now, limit=5)
                second = process_due_publishes(db_path=db_path, now=now, limit=5)

            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT status, platform_results_json FROM scheduled_posts WHERE id = 'sched'").fetchone()
            attempts = conn.execute("SELECT count(*) AS count FROM publish_attempts WHERE status = 'published'").fetchone()["count"]
            conn.close()

        self.assertEqual(first["processed"][0]["status"], "published")
        self.assertEqual(second["count"], 0)
        self.assertEqual(calls, ["telegram_channel", "youtube_shorts"])
        self.assertEqual(row["status"], "published")
        self.assertEqual(attempts, 2)

    def test_due_publish_records_partial_failure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/media_engine.sqlite"
            video_path = f"{tmpdir}/clip.mp4"
            Path(video_path).write_bytes(b"video")
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            initialize(conn)
            conn.execute("INSERT INTO media_profiles VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)", ("nourbit", "Nourbit", "niche", "[]", "lecture_clean", "cta", "wm"))
            conn.execute("INSERT INTO source_manifests VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)", ("src", "nourbit", "url", "community", "public_third_party", "", "[]", 1, "", "[]"))
            for platform in ["telegram_channel", "youtube_shorts"]:
                conn.execute("INSERT INTO publish_targets (profile_id, platform, account_label, mode, require_approval, ai_disclosure_required, daily_cap) VALUES (?, ?, ?, ?, ?, ?, ?)", ("nourbit", platform, platform, "review_required", 1, 0, 2))
            conn.execute("INSERT INTO clip_candidates (id, profile_id, source_id, start_ms, end_ms, title_hook, viral_reason, transcript_span, risk_flags_json, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", ("clip", "nourbit", "src", 0, 1000, "Hook", "Reason", "Text", "[]", "scheduled"))
            conn.execute("INSERT INTO render_jobs (id, candidate_id, preset, crop_strategy, caption_style, status, output_path, metadata_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", ("render", "clip", "premium", "center", "caption", "rendered", video_path, "{}"))
            conn.execute("INSERT INTO scheduled_posts (id, candidate_id, profile_id, scheduled_at, status, publish_mode, platforms_json) VALUES (?, ?, ?, ?, ?, ?, ?)", ("sched", "clip", "nourbit", "2026-05-15T09:00+07:00", "scheduled", "scheduled_publish", '["telegram_channel", "youtube_shorts"]'))
            conn.commit()
            conn.close()

            def fake_publish(platform, payload, **_kwargs):
                if platform == "youtube_shorts":
                    from media_engine.live_publishers import LivePublishError
                    raise LivePublishError("youtube down")
                return {"platform": platform, "status": "published", "remote_id": "telegram_id"}

            now = datetime(2026, 5, 15, 10, 0, tzinfo=ZoneInfo("Asia/Jakarta"))
            with patch("media_engine.schedule_publisher.publish_live_payload", side_effect=fake_publish):
                result = process_due_publishes(db_path=db_path, now=now, limit=5)

            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT status, last_error FROM scheduled_posts WHERE id = 'sched'").fetchone()
            conn.close()

        self.assertEqual(result["processed"][0]["status"], "partial_failed")
        self.assertEqual(row["status"], "partial_failed")
        self.assertIn("youtube down", row["last_error"])


if __name__ == "__main__":
    unittest.main()
