import os
import unittest
from unittest.mock import patch

from media_engine.hyperframes_renderer import (
    DEFAULT_FFMPEG_ENCODE_TIMEOUT_MS,
    DEFAULT_FFMPEG_STREAMING_TIMEOUT_MS,
    _hyperframes_subprocess_env,
    _sanitize_cli_output,
)


class HyperframesRendererEnvTests(unittest.TestCase):
    def test_subprocess_env_sets_longer_ffmpeg_timeouts_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            env = _hyperframes_subprocess_env()
        self.assertEqual(env["FFMPEG_STREAMING_TIMEOUT_MS"], DEFAULT_FFMPEG_STREAMING_TIMEOUT_MS)
        self.assertEqual(env["FFMPEG_ENCODE_TIMEOUT_MS"], DEFAULT_FFMPEG_ENCODE_TIMEOUT_MS)

    def test_subprocess_env_respects_operator_override(self):
        with patch.dict(
            os.environ,
            {"FFMPEG_STREAMING_TIMEOUT_MS": "999", "FFMPEG_ENCODE_TIMEOUT_MS": "888"},
            clear=True,
        ):
            env = _hyperframes_subprocess_env()
        self.assertEqual(env["FFMPEG_STREAMING_TIMEOUT_MS"], "999")
        self.assertEqual(env["FFMPEG_ENCODE_TIMEOUT_MS"], "888")

    def test_sanitize_cli_output_strips_progress_spam(self):
        raw = (
            "\x1b[2K ███████████████████░░░░░░ 79% Streaming frame 2269/2270\r\n"
            "Failed: Streaming encode failed: FFmpeg exited with code 255\r\n"
            "ffmpeg stderr (tail): Exiting normally, received signal 15.\r\n"
        )
        cleaned = _sanitize_cli_output(raw)
        self.assertNotIn("Streaming frame", cleaned)
        self.assertIn("FFmpeg exited with code 255", cleaned)
        self.assertIn("signal 15", cleaned)


if __name__ == "__main__":
    unittest.main()
