"""Tests for YouTube source URL normalize + resolve metadata."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from media_engine.source_resolve import normalize_youtube_video_url, resolve_youtube_source


class SourceResolveTests(unittest.TestCase):
    def test_normalize_watch_and_short_urls(self):
        self.assertEqual(
            normalize_youtube_video_url("https://www.youtube.com/watch?v=Ow5mweU_fx0&si=abc"),
            "https://www.youtube.com/watch?v=Ow5mweU_fx0",
        )
        self.assertEqual(
            normalize_youtube_video_url("https://youtu.be/Ow5mweU_fx0?si=abc"),
            "https://www.youtube.com/watch?v=Ow5mweU_fx0",
        )
        self.assertEqual(
            normalize_youtube_video_url("youtube.com/shorts/Ow5mweU_fx0"),
            "https://www.youtube.com/watch?v=Ow5mweU_fx0",
        )

    def test_normalize_rejects_channel(self):
        with self.assertRaises(ValueError):
            normalize_youtube_video_url("https://www.youtube.com/@somechannel")

    def test_normalize_rejects_incomplete_id(self):
        with self.assertRaises(ValueError) as ctx:
            normalize_youtube_video_url("https://youtu.be/d")
        self.assertIn("incomplete", str(ctx.exception).lower())

    @patch("media_engine.source_resolve.find_ytdlp", return_value="yt-dlp")
    @patch("media_engine.source_resolve.subprocess.run")
    def test_resolve_success_with_soft_warning(self, run_mock: MagicMock, _ytdlp: MagicMock):
        run_mock.return_value = MagicMock(
            returncode=0,
            stdout="Ow5mweU_fx0\tHello World\tChannel Name\tUploader\t90\thttps://i.ytimg.com/vi/Ow5mweU_fx0/hqdefault.jpg\thttps://www.youtube.com/watch?v=Ow5mweU_fx0\n",
            stderr="",
        )
        payload = resolve_youtube_source("https://youtu.be/Ow5mweU_fx0")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["video_id"], "Ow5mweU_fx0")
        self.assertEqual(payload["title"], "Hello World")
        self.assertEqual(payload["channel"], "Channel Name")
        self.assertEqual(payload["duration_seconds"], 90)
        self.assertTrue(payload["thumbnail_url"])
        self.assertTrue(any("short" in warning.lower() or "3 minutes" in warning.lower() for warning in payload["warnings"]))

    @patch("media_engine.source_resolve.find_ytdlp", return_value="yt-dlp")
    @patch("media_engine.source_resolve.subprocess.run")
    def test_resolve_unavailable(self, run_mock: MagicMock, _ytdlp: MagicMock):
        run_mock.return_value = MagicMock(returncode=1, stdout="", stderr="ERROR: Video unavailable")
        with self.assertRaises(ValueError) as ctx:
            resolve_youtube_source("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.assertIn("unavailable", str(ctx.exception).lower())

    @patch("media_engine.source_resolve.find_ytdlp", return_value="yt-dlp")
    @patch("media_engine.source_resolve.subprocess.run")
    def test_resolve_humanizes_truncated_id(self, run_mock: MagicMock, _ytdlp: MagicMock):
        # Bypass normalize length check by mocking a path that still hits yt-dlp.
        run_mock.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="ERROR: [youtube:truncated_id] d: Incomplete YouTube ID d. URL https://www.youtube.com/watch?v=d looks truncated.",
        )
        with patch("media_engine.source_resolve.normalize_youtube_video_url", return_value="https://www.youtube.com/watch?v=d"):
            with self.assertRaises(ValueError) as ctx:
                resolve_youtube_source("https://youtu.be/d")
        self.assertIn("incomplete", str(ctx.exception).lower())
        self.assertNotIn("ERROR:", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
