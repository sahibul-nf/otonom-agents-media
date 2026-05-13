import sqlite3
import unittest
from unittest.mock import patch

from media_engine.db import initialize
from media_engine.credentials import credential_status
from media_engine.live_publishers import LivePublishError, publish_telegram_video
from media_engine.publishers import build_payload, create_dry_run_attempt


class PublisherTests(unittest.TestCase):
    def test_build_tiktok_payload_defaults_private(self):
        candidate = {"id": "clip1", "title_hook": "Hook", "viral_reason": "Reason"}
        render_job = {"output_path": "/tmp/clip.mp4", "metadata_json": '{"subtitle": "Warm subtitle"}'}
        payload = build_payload("tiktok", candidate, render_job)
        self.assertEqual(payload["visibility"], "private")
        self.assertTrue(payload["dry_run"])
        self.assertIn("Hook", payload["caption"])
        self.assertIn("Warm subtitle", payload["caption"])
        self.assertIn("#KajianIslam", payload["caption"])

    def test_build_telegram_payload_uses_send_video_contract(self):
        candidate = {"id": "clip1", "title_hook": "Hook", "viral_reason": "Reason"}
        render_job = {"output_path": "/tmp/clip.mp4", "metadata_json": '{"subtitle": "Subtitle"}'}
        payload = build_payload("telegram_channel", candidate, render_job)

        self.assertEqual(payload["endpoint"], "telegram-bot-api/sendVideo")
        self.assertTrue(payload["supports_streaming"])
        self.assertLessEqual(len(payload["caption"]), 1024)

    def test_credential_status_marks_ready_without_exposing_values(self):
        with patch.dict(
            "os.environ",
            {
                "TELEGRAM_BOT_TOKEN": "token",
                "TELEGRAM_CHANNEL_ID": "@channel",
            },
            clear=True,
        ):
            status = credential_status()

        self.assertTrue(status["platforms"]["telegram_channel"]["ready"])
        self.assertFalse(status["platforms"]["youtube_shorts"]["ready"])
        self.assertNotIn("token", str(status))

    def test_telegram_live_publish_requires_rendered_file(self):
        with patch.dict(
            "os.environ",
            {
                "TELEGRAM_BOT_TOKEN": "token",
                "TELEGRAM_CHANNEL_ID": "@channel",
            },
            clear=True,
        ):
            with self.assertRaises(LivePublishError):
                publish_telegram_video({"video_path": "/tmp/does-not-exist.mp4", "caption": "Caption"})

    def test_blocked_attempt_is_recorded(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        initialize(conn)
        conn.execute("INSERT INTO media_profiles VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)", ("nourbit", "Nourbit", "niche", "[]", "lecture_clean", "cta", "wm"))
        conn.execute("INSERT INTO source_manifests VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)", ("src", "nourbit", "url", "community", "public_third_party", "", "[]", 0, "", "[]"))
        conn.execute(
            """
            INSERT INTO clip_candidates
              (id, profile_id, source_id, start_ms, end_ms, title_hook, viral_reason,
               transcript_span, risk_flags_json, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("clip", "nourbit", "src", 0, 1000, "Hook", "Reason", "Text", "[]", "approved"),
        )
        source = {"permission_status": "public_third_party", "permission_evidence": ""}
        target = {"platform": "facebook_reels", "mode": "auto_publish", "require_approval": 1}
        candidate = {"id": "clip", "title_hook": "Hook", "status": "approved"}
        attempt = create_dry_run_attempt(conn, source, target, candidate, {"output_path": "/tmp/clip.mp4"})
        self.assertEqual(attempt["status"], "blocked")
        self.assertIn("public third-party", attempt["error"])
        conn.close()


if __name__ == "__main__":
    unittest.main()
