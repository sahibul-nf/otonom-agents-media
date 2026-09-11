import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from media_engine import credential_vault as vault
from media_engine.postiz_client import (
    PostizError,
    build_create_post_body,
    candidate_api_bases,
    channel_id_for_platform,
    delete_post,
    extract_remote_id,
    integrations_for_platform,
    list_posts,
    map_platform,
    map_postiz_delivery_status,
    normalize_postiz_api_url,
    sanitize_api_key,
    settings_for_platform,
    uses_postiz,
    validate_channel,
)
from media_engine.postiz_sync import reconcile_profile_schedules, same_schedule_slot
from media_engine.schedule_publisher import rollup_schedule_status


class PostizClientTests(unittest.TestCase):
    def test_normalize_api_postiz_host(self):
        self.assertEqual(
            normalize_postiz_api_url("https://api-postiz.nourdaily.com/"),
            "https://api-postiz.nourdaily.com/public/v1",
        )
        self.assertEqual(
            normalize_postiz_api_url("https://api-postiz.nourdaily.com/public/v1"),
            "https://api-postiz.nourdaily.com/public/v1",
        )
        self.assertEqual(
            normalize_postiz_api_url("https://postiz.nourdaily.com/api/public/v1"),
            "https://postiz.nourdaily.com/api/public/v1",
        )

    def test_candidate_bases_include_frontend_api_proxy(self):
        bases = candidate_api_bases("https://api-postiz.nourdaily.com")
        self.assertIn("https://api-postiz.nourdaily.com/public/v1", bases)
        self.assertIn("https://api-postiz.nourdaily.com/api/public/v1", bases)
        self.assertIn("https://postiz.nourdaily.com/api/public/v1", bases)

    def test_sanitize_strips_bearer(self):
        self.assertEqual(sanitize_api_key("Bearer abc123"), "abc123")

    def test_youtube_settings_require_title(self):
        settings = settings_for_platform("youtube_shorts", title="Iman", caption="body")
        self.assertEqual(settings["__type"], "youtube")
        self.assertEqual(settings["title"], "Iman")

    def test_create_post_body_includes_uploaded_media(self):
        body = build_create_post_body(
            integration_id="int1",
            caption="Hello",
            media={"id": "m1", "path": "https://uploads.example/v.mp4"},
            platform="telegram_channel",
            title="Hook",
            date_iso="2026-09-08T08:00:00.000Z",
        )
        self.assertEqual(body["type"], "now")
        self.assertEqual(body["posts"][0]["integration"]["id"], "int1")
        self.assertEqual(body["posts"][0]["value"][0]["image"][0]["id"], "m1")
        self.assertEqual(body["posts"][0]["settings"]["__type"], "telegram")

    def test_create_post_body_schedule_type(self):
        body = build_create_post_body(
            integration_id="int1",
            caption="Hello",
            media={"id": "m1", "path": "https://uploads.example/v.mp4"},
            platform="youtube_shorts",
            title="Hook",
            post_type="schedule",
            date_iso="2026-09-09T02:00:00+07:00",
        )
        self.assertEqual(body["type"], "schedule")
        self.assertEqual(body["date"], "2026-09-08T19:00:00.000Z")

    def test_extract_remote_id_from_list_payload(self):
        remote = extract_remote_id([{"postId": "abc", "integration": "yt1"}])
        self.assertEqual(remote, "abc")

    def test_extract_remote_id_skips_media_uuid(self):
        media_id = "media-uuid"
        remote = extract_remote_id({"id": media_id, "posts": [{"id": "post-1"}]}, exclude={media_id})
        self.assertEqual(remote, "post-1")

    def test_extract_remote_id_prefers_cuid_over_media_uuid(self):
        media_id = "ef744c8f-f747-4449-a960-f07e146a74ea"
        post_id = "cmtty4e5j0000o57xio46nplv"
        remote = extract_remote_id(
            {
                "id": media_id,
                "posts": [{"id": post_id, "integrationId": "yt1"}],
            }
        )
        self.assertEqual(remote, post_id)

    def test_delete_post_swallows_integration_id_500(self):
        with patch(
            "media_engine.postiz_client._request_json",
            side_effect=PostizError("Postiz DELETE failed: HTTP 500: Cannot read properties of undefined (reading 'integrationId')"),
        ):
            delete_post("gone-id", profile_id="nourbit")

    def test_rollup_keeps_accepted_until_live(self):
        status = rollup_schedule_status(
            ["youtube_shorts", "facebook_reels"],
            {
                "youtube_shorts": {"status": "accepted"},
                "facebook_reels": {"status": "queued"},
            },
        )
        self.assertEqual(status, "accepted")
        self.assertEqual(
            rollup_schedule_status(
                ["youtube_shorts"],
                {"youtube_shorts": {"status": "live"}},
            ),
            "published",
        )

    def test_same_schedule_slot_ignores_timezone_format(self):
        self.assertTrue(
            same_schedule_slot("2026-09-09T19:30:00+07:00", "2026-09-09T12:30:00+00:00")
        )
        self.assertFalse(
            same_schedule_slot("2026-09-09T19:30:00+07:00", "2026-09-09T20:30:00+07:00")
        )

    def test_map_postiz_queue_vs_published(self):
        self.assertEqual(map_postiz_delivery_status({"state": "QUEUE"}), "queued")
        self.assertEqual(map_postiz_delivery_status({"status": "PUBLISHED"}), "live")
        self.assertEqual(map_postiz_delivery_status({"releaseState": "error"}), "failed")
        self.assertEqual(
            map_postiz_delivery_status(
                {
                    "state": "ERROR",
                    "releaseURL": "https://www.facebook.com/reel/123",
                }
            ),
            "live",
        )

    def test_list_posts_requires_date_range(self):
        with patch("media_engine.postiz_client._request_json") as mock_request:
            mock_request.return_value = {"posts": [{"id": "cmtty4e5j0000o57xio46nplv", "state": "PUBLISHED"}]}
            posts = list_posts("nourbit")
        self.assertEqual(len(posts), 1)
        called_path = mock_request.call_args.args[1]
        self.assertIn("startDate=", called_path)
        self.assertIn("endDate=", called_path)

    def test_rollup_ignores_unattempted_native_pending(self):
        status = rollup_schedule_status(
            ["facebook_reels", "telegram_channel", "tiktok"],
            {
                "facebook_reels": {"status": "live", "backend": "postiz", "remote_id": "cmtty4e5j0000o57xio46nplv"},
                "telegram_channel": {"status": "pending"},
                "tiktok": {"status": "pending"},
            },
        )
        self.assertEqual(status, "published")

    def test_reconcile_downgrades_false_published(self):
        from media_engine.db import initialize

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        initialize(conn)
        conn.execute(
            "INSERT INTO media_profiles VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            ("nourbit", "Nourbit", "niche", "[]", "lecture_clean", "cta", "wm"),
        )
        conn.execute(
            "INSERT INTO source_manifests VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            ("src", "nourbit", "url", "community", "authorized_community", "ok", "[]", 1, "", "[]"),
        )
        conn.execute(
            """
            INSERT INTO clip_candidates
              (id, profile_id, source_id, start_ms, end_ms, title_hook, viral_reason,
               transcript_span, risk_flags_json, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("clip", "nourbit", "src", 0, 1000, "Hook", "Reason", "Text", "[]", "published"),
        )
        remote_id = "cmtty4e5j0000o57xio46nplv"
        conn.execute(
            """
            INSERT INTO scheduled_posts
              (id, candidate_id, profile_id, scheduled_at, status, publish_mode, platforms_json, platform_results_json, published_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "sched",
                "clip",
                "nourbit",
                "2026-09-09T17:00:00+07:00",
                "published",
                "scheduled_publish",
                '["facebook_reels"]',
                json.dumps(
                    {
                        "facebook_reels": {
                            "platform": "facebook_reels",
                            "status": "live",
                            "backend": "postiz",
                            "remote_id": remote_id,
                            "post_type": "schedule",
                        }
                    }
                ),
                "2026-09-09T10:00:00+00:00",
            ),
        )
        conn.commit()
        with patch("media_engine.postiz_sync.postiz_api_key", return_value="key"), patch(
            "media_engine.postiz_sync.list_posts",
            return_value=[{"id": remote_id, "state": "QUEUE"}],
        ):
            reconcile_profile_schedules(conn, "nourbit")
        schedule = conn.execute("SELECT status, platform_results_json, published_at FROM scheduled_posts WHERE id = 'sched'").fetchone()
        clip = conn.execute("SELECT status FROM clip_candidates WHERE id = 'clip'").fetchone()
        self.assertEqual(schedule["status"], "scheduled")
        self.assertEqual(json.loads(schedule["platform_results_json"])["facebook_reels"]["status"], "queued")
        self.assertEqual(schedule["published_at"], "")
        self.assertEqual(clip["status"], "scheduled")
        conn.close()

    def test_reconcile_marks_live_when_postiz_published(self):
        from media_engine.db import initialize

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        initialize(conn)
        conn.execute(
            "INSERT INTO media_profiles VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            ("nourbit", "Nourbit", "niche", "[]", "lecture_clean", "cta", "wm"),
        )
        conn.execute(
            "INSERT INTO source_manifests VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            ("src", "nourbit", "url", "community", "authorized_community", "ok", "[]", 1, "", "[]"),
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
        remote_id = "cmtty4e5j0000o57xio46nplv"
        conn.execute(
            """
            INSERT INTO scheduled_posts
              (id, candidate_id, profile_id, scheduled_at, status, publish_mode, platforms_json, platform_results_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "sched",
                "clip",
                "nourbit",
                "2026-09-09T17:00:00+07:00",
                "scheduled",
                "scheduled_publish",
                '["facebook_reels"]',
                json.dumps(
                    {
                        "facebook_reels": {
                            "platform": "facebook_reels",
                            "status": "queued",
                            "backend": "postiz",
                            "remote_id": remote_id,
                            "post_type": "schedule",
                        }
                    }
                ),
            ),
        )
        conn.commit()
        with patch("media_engine.postiz_sync.postiz_api_key", return_value="key"), patch(
            "media_engine.postiz_sync.list_posts",
            return_value=[{"id": remote_id, "state": "PUBLISHED", "releaseURL": "https://fb.example/p"}],
        ):
            reconcile_profile_schedules(conn, "nourbit")
        schedule = conn.execute("SELECT status, platform_results_json FROM scheduled_posts WHERE id = 'sched'").fetchone()
        clip = conn.execute("SELECT status FROM clip_candidates WHERE id = 'clip'").fetchone()
        result = json.loads(schedule["platform_results_json"])["facebook_reels"]
        self.assertEqual(schedule["status"], "published")
        self.assertEqual(result["status"], "live")
        self.assertEqual(result["remote_url"], "https://fb.example/p")
        self.assertEqual(clip["status"], "published")
        conn.close()

    def test_integrations_prefer_matching_identifier(self):
        items = [
            {"id": "yt1", "name": "Shorts", "identifier": "youtube"},
            {"id": "tt1", "name": "TikTok", "identifier": "tiktok"},
        ]
        youtube = integrations_for_platform("youtube_shorts", items)
        self.assertEqual([row["id"] for row in youtube], ["yt1"])


class PostizVaultTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.vault_dir = Path(self.tmp.name) / "credentials"
        self.vault_dir.mkdir(parents=True)
        self.patcher = patch.object(vault, "VAULT_DIR", self.vault_dir)
        self.patcher.start()

    def tearDown(self) -> None:
        self.patcher.stop()
        self.tmp.cleanup()

    def test_channel_map_and_uses_postiz_are_workspace_scoped(self):
        vault.set_profile_secrets(
            "nourbit",
            {
                "POSTIZ_API_URL": "https://api-postiz.nourdaily.com",
                "POSTIZ_API_KEY": "key-n",
            },
        )
        map_platform("nourbit", "tiktok", {"id": "int_tt", "name": "Nourbit TT", "identifier": "tiktok"})
        self.assertEqual(channel_id_for_platform("tiktok", "nourbit"), "int_tt")
        self.assertTrue(uses_postiz("tiktok", "nourbit"))
        self.assertFalse(uses_postiz("tiktok", "workspace"))
        self.assertFalse(uses_postiz("youtube_shorts", "nourbit"))

        with patch.dict(os.environ, {"PUBLISH_BACKEND": "native"}, clear=False):
            self.assertFalse(uses_postiz("tiktok", "nourbit"))

    def test_credential_status_ready_when_postiz_mapped(self):
        vault.set_profile_secrets("nourbit", {"POSTIZ_API_KEY": "key-n"})
        map_platform("nourbit", "youtube_shorts", {"id": "yt1", "name": "Nourbit YT"})
        status = vault.credential_status_for_profile("nourbit")
        self.assertTrue(status["postiz"]["connected"])
        self.assertTrue(status["platforms"]["youtube_shorts"]["ready"])
        self.assertEqual(status["platforms"]["youtube_shorts"]["backend"], "postiz")
        self.assertFalse(status["platforms"]["tiktok"]["ready"])

    def test_validate_channel_blocks_disabled_integration(self):
        vault.set_profile_secrets("nourbit", {"POSTIZ_API_KEY": "key-n"})
        map_platform("nourbit", "youtube_shorts", {"id": "yt1", "name": "Nourbit YT"})
        with patch(
            "media_engine.postiz_client.list_integrations",
            return_value=[{"id": "yt1", "identifier": "youtube", "disabled": True}],
        ):
            with self.assertRaises(PostizError) as ctx:
                validate_channel("youtube_shorts", "nourbit")
        self.assertIn("Reconnect youtube_shorts", str(ctx.exception))


class PostizDuePublishTests(unittest.TestCase):
    def test_due_publish_routes_to_postiz(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        tmp.write(b"fake")
        tmp.close()
        candidate = {"id": "clip1", "profile_id": "nourbit", "title_hook": "Hook"}
        source = {"id": "src"}
        target = {"platform": "youtube_shorts", "mode": "review_required", "profile_id": "nourbit"}
        render = {"output_path": tmp.name}
        payload_video = {"video_path": tmp.name, "caption": "hi", "title": "Hook"}
        guard = MagicMock()
        guard.allowed = True

        with patch("media_engine.schedule_publisher.already_published", return_value=False), patch(
            "media_engine.schedule_publisher.in_retry_backoff", return_value=False
        ), patch("media_engine.schedule_publisher.can_publish_candidate", return_value=guard), patch(
            "media_engine.schedule_publisher.build_payload",
            return_value=payload_video,
        ), patch("media_engine.schedule_publisher.uses_postiz", return_value=True), patch(
            "media_engine.schedule_publisher.publish_live_payload"
        ) as mock_native, patch(
            "media_engine.schedule_publisher.publish_postiz_video",
            return_value={"platform": "youtube_shorts", "status": "accepted", "backend": "postiz", "remote_id": "p1"},
        ) as mock_postiz, patch(
            "media_engine.schedule_publisher.record_publish_attempt",
            return_value={"id": "pub_test"},
        ):
            result = publish_candidate_platform(MagicMock(), candidate, source, target, render, dry_run=False)

        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["remote_id"], "p1")
        mock_postiz.assert_called_once()
        mock_native.assert_not_called()
        Path(tmp.name).unlink(missing_ok=True)

    def test_due_publish_skips_platforms_already_on_postiz_calendar(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/media_engine.sqlite"
            video_path = f"{tmpdir}/clip.mp4"
            Path(video_path).write_bytes(b"video")
            import sqlite3
            from media_engine.db import initialize as init_db

            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            init_db(conn)
            conn.execute(
                "INSERT INTO media_profiles VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                ("nourbit", "Nourbit", "niche", "[]", "lecture_clean", "cta", "wm"),
            )
            conn.execute(
                "INSERT INTO source_manifests VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                ("src", "nourbit", "url", "community", "authorized_community", "ok", "[]", 1, "", "[]"),
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
                  (id, candidate_id, profile_id, scheduled_at, status, publish_mode, platforms_json, platform_results_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "sched",
                    "clip",
                    "nourbit",
                    "2026-05-15T09:00+07:00",
                    "scheduled",
                    "scheduled_publish",
                    '["telegram_channel", "youtube_shorts"]',
                    json.dumps(
                        {
                            "youtube_shorts": {
                                "platform": "youtube_shorts",
                                "status": "queued",
                                "backend": "postiz",
                                "remote_id": "postiz_yt",
                                "post_type": "schedule",
                            }
                        }
                    ),
                ),
            )
            conn.commit()
            conn.close()

            from datetime import datetime
            from zoneinfo import ZoneInfo

            now = datetime(2026, 5, 15, 10, 0, tzinfo=ZoneInfo("Asia/Jakarta"))
            with patch("media_engine.schedule_publisher.publish_live_payload") as mock_native, patch(
                "media_engine.schedule_publisher.publish_postiz_video"
            ) as mock_postiz:
                mock_native.return_value = {"platform": "telegram_channel", "status": "published", "remote_id": "tg1"}
                result = process_due_publishes(db_path=db_path, now=now, limit=5)

            youtube = result["processed"][0]["platform_results"]["youtube_shorts"]
            self.assertEqual(youtube["status"], "queued")
            self.assertEqual(youtube["reason"], "already on Postiz calendar")
            self.assertEqual(result["processed"][0]["status"], "scheduled")
            mock_postiz.assert_not_called()
            mock_native.assert_called_once()


if __name__ == "__main__":
    unittest.main()
