import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from media_engine.db import initialize
from media_engine.credentials import credential_status
from media_engine.live_publishers import (
    LivePublishError,
    prepare_telegram_video,
    publish_facebook_reel,
    publish_telegram_video,
    publish_tiktok_video,
    publish_youtube_short,
)
from media_engine.publishers import build_payload, create_dry_run_attempt
from media_engine.post_copy import build_post_caption, generate_post_caption, sanitize_post_caption
from media_engine.llm import LLMError


def json_dumps(value):
    return json.dumps(value).encode("utf-8")


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

    def test_post_caption_is_short_and_has_at_most_five_hashtags(self):
        candidate = {
            "id": "clip1",
            "title_hook": "Hook yang cukup panjang untuk menguji batas caption platform sosial",
            "hook_subtitle": "Deskripsi yang menjelaskan isi video dengan cukup spesifik dan tetap pendek.",
            "viral_reason": "Reason",
        }

        caption = build_post_caption(candidate, {"metadata_json": "{}"})

        self.assertLessEqual(len(caption), 400)
        self.assertLessEqual(caption.count("#"), 5)

    def test_post_caption_override_is_sanitized(self):
        candidate = {
            "id": "clip1",
            "title_hook": "Hook",
            "viral_reason": "Reason",
            "curation_metadata": {
                "post_caption_override": " ".join(["panjang"] * 90)
                + " #Satu #Dua #Tiga #Empat #Lima #Enam #Tujuh"
            },
        }

        caption = build_post_caption(candidate, {"metadata_json": "{}"})

        self.assertLessEqual(len(caption), 400)
        self.assertIn("#Satu #Dua #Tiga #Empat #Lima", caption)
        self.assertNotIn("#Enam", caption)

    def test_sanitize_post_caption_keeps_only_five_unique_hashtags(self):
        caption = sanitize_post_caption("Isi post #A #B #C #D #E #F #A")

        self.assertEqual(caption.count("#"), 5)

    def test_generate_post_caption_uses_llm_when_available(self):
        candidate = {
            "id": "clip1",
            "title_hook": "Rahasia Hati Tenang",
            "hook_subtitle": "Pengingat lembut tentang hati yang sering diam-diam bergeser.",
            "viral_reason": "Reason",
            "transcript_span": "Hati yang tenang itu lahir dari ingat kepada Allah dan menjaga arah niat.",
        }
        with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-key"}, clear=True), patch(
            "media_engine.post_copy.call_llm_json",
            return_value={"post_caption": "Tenangkan hati dengan mengingat Allah dan menjaga niat.\n\n#Nourbit #KajianIslam #NasihatHati #Dzikir #IslamicReminder #Extra"},
        ) as call:
            result = generate_post_caption(candidate, preferred_provider="deepseek")

        self.assertEqual(result["source"], "llm_deepseek")
        self.assertLessEqual(result["char_count"], 400)
        self.assertEqual(result["hashtag_count"], 5)
        self.assertIn("Tenangkan hati", result["post_caption"])
        call.assert_called_once()

    def test_generate_post_caption_fails_without_key(self):
        candidate = {
            "id": "clip1",
            "title_hook": "Rahasia Hati Tenang",
            "hook_subtitle": "Pengingat lembut tentang hati yang sering diam-diam bergeser.",
            "viral_reason": "Reason",
            "transcript_span": "Hati yang tenang itu lahir dari ingat kepada Allah dan menjaga arah niat.",
        }
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(LLMError):
                generate_post_caption(candidate, preferred_provider="deepseek")

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

    def test_credential_status_accepts_env_aliases(self):
        with patch.dict(
            "os.environ",
            {
                "TELEGRAM_BOT_TOKEN": "token",
                "TELEGRAM_CHAT_ID": "@channel",
                "META_PAGE_ACCESS_TOKEN": "page-token",
                "NOURBIT_FACEBOOK_PAGE_ID": "page-id",
            },
            clear=True,
        ):
            status = credential_status()

        self.assertTrue(status["platforms"]["telegram_channel"]["ready"])
        self.assertTrue(status["platforms"]["facebook_reels"]["ready"])

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

    def test_telegram_prepare_uses_original_when_under_limit(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4") as video:
            video.write(b"small")
            video.flush()

            result = prepare_telegram_video(video.name, target_bytes=1024)

        self.assertFalse(result["compressed"])
        self.assertEqual(result["upload_size"], 5)

    def test_telegram_publish_uses_prepared_upload_path(self):
        calls = []

        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return json_dumps({"ok": True, "result": {"message_id": 123, "chat": {"id": "@channel"}}})

        def fake_urlopen(request, timeout=0):
            calls.append(request.data)
            return FakeResponse()

        with tempfile.NamedTemporaryFile(suffix=".mp4") as original, tempfile.NamedTemporaryFile(suffix=".mp4") as prepared:
            original.write(b"original")
            original.flush()
            prepared.write(b"prepared")
            prepared.flush()
            with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHANNEL_ID": "@channel"}, clear=True):
                with patch("media_engine.live_publishers.prepare_telegram_video") as prepare:
                    prepare.return_value = {
                        "path": prepared.name,
                        "compressed": True,
                        "original_path": original.name,
                        "original_size": 8,
                        "upload_size": 8,
                        "limit": 1024,
                    }
                    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                        result = publish_telegram_video({"video_path": original.name, "caption": "Caption"})

        self.assertEqual(result["message_id"], 123)
        self.assertTrue(result["upload"]["compressed"])
        self.assertIn(b"prepared", calls[0])

    def test_public_third_party_attempt_is_ready_when_candidate_approved(self):
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
        self.assertEqual(attempt["status"], "ready")
        self.assertEqual(attempt["error"], "")
        conn.close()

    def test_youtube_publish_uses_oauth_and_resumable_upload(self):
        responses = [
            ({"access_token": "access"}, {}),
            ({}, {"Location": "https://upload.youtube.test/session"}),
            ({"id": "yt123"}, {}),
        ]

        class FakeResponse:
            def __init__(self, body, headers):
                self.body = body
                self.headers = headers
                self.status = 200
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return json_dumps(self.body)

        def fake_urlopen(request, timeout=0):
            body, headers = responses.pop(0)
            return FakeResponse(body, headers)

        with tempfile.NamedTemporaryFile(suffix=".mp4") as video:
            video.write(b"video")
            video.flush()
            with patch.dict("os.environ", {"YOUTUBE_CLIENT_ID": "id", "YOUTUBE_CLIENT_SECRET": "secret", "YOUTUBE_REFRESH_TOKEN": "refresh"}, clear=True):
                with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                    result = publish_youtube_short({"video_path": video.name, "title": "Hook", "caption": "Caption"})

        self.assertEqual(result["platform"], "youtube_shorts")
        self.assertEqual(result["remote_id"], "yt123")

    def test_tiktok_publish_init_and_upload(self):
        responses = [
            ({"data": {"upload_url": "https://upload.tiktok.test", "publish_id": "tk123"}}, {}),
            ({}, {}),
        ]

        class FakeResponse:
            status = 200
            def __init__(self, body):
                self.body = body
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return json_dumps(self.body)

        def fake_urlopen(request, timeout=0):
            body, _headers = responses.pop(0)
            return FakeResponse(body)

        with tempfile.NamedTemporaryFile(suffix=".mp4") as video:
            video.write(b"video")
            video.flush()
            with patch.dict("os.environ", {"TIKTOK_ACCESS_TOKEN": "token"}, clear=True):
                with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                    result = publish_tiktok_video({"video_path": video.name, "caption": "Caption"})

        self.assertEqual(result["platform"], "tiktok")
        self.assertEqual(result["remote_id"], "tk123")

    def test_facebook_reel_publish_start_upload_finish(self):
        responses = [
            ({"video_id": "fb123", "upload_url": "https://upload.facebook.test"}, {}),
            ({}, {}),
            ({"success": True}, {}),
        ]

        class FakeResponse:
            status = 200
            def __init__(self, body):
                self.body = body
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return json_dumps(self.body)

        def fake_urlopen(request, timeout=0):
            body, _headers = responses.pop(0)
            return FakeResponse(body)

        with tempfile.NamedTemporaryFile(suffix=".mp4") as video:
            video.write(b"video")
            video.flush()
            with patch.dict("os.environ", {"META_PAGE_ID": "page", "META_PAGE_ACCESS_TOKEN": "token"}, clear=True):
                with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                    result = publish_facebook_reel({"video_path": video.name, "caption": "Caption"})

        self.assertEqual(result["platform"], "facebook_reels")
        self.assertEqual(result["remote_id"], "fb123")


if __name__ == "__main__":
    unittest.main()
