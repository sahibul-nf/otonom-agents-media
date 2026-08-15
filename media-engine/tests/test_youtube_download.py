import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from media_engine.generation_jobs import _failure_summary
from media_engine.youtube_pipeline import download_youtube_section, humanize_youtube_download_error


class YoutubeDownloadTests(unittest.TestCase):
    def test_humanize_403_mentions_cookies_and_update(self):
        message = humanize_youtube_download_error(
            "HTTP error 403 Forbidden\nError opening input files: Server returned 403 Forbidden\nERROR: ffmpeg exited with code 8"
        )
        self.assertIn("403", message)
        self.assertIn("yt-dlp", message)
        self.assertIn("MEDIA_ENGINE_YTDLP_COOKIES", message)

    def test_failure_summary_prefers_youtube_block_over_ffmpeg_exit(self):
        output = "\n".join(
            [
                "[media-engine] downloading source clip",
                "HTTP error 403 Forbidden",
                "Error opening input file https://rr3---sn-n25jxm-cuie.googlevideo.com/videoplayback",
                "ERROR: ffmpeg exited with code 8",
                "RuntimeError: YouTube blocked the clip download (HTTP 403). Update yt-dlp in media-engine/.venv-tools, or set MEDIA_ENGINE_YTDLP_COOKIES to a cookies.txt export from a signed-in browser, then retry.",
            ]
        )
        summary = _failure_summary(output, 1)
        self.assertIn("YouTube blocked", summary)
        self.assertNotIn("ffmpeg exited", summary)

    @patch("media_engine.youtube_pipeline.find_ytdlp", return_value="yt-dlp")
    @patch("media_engine.youtube_pipeline.subprocess.run")
    def test_download_retries_on_403_then_succeeds(self, run_mock, _find):
        fail = Mock(returncode=1, stdout="", stderr="HTTP error 403 Forbidden\nERROR: ffmpeg exited with code 8")
        success = Mock(returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "workspace" / "clip_x" / "source"

            def run_side_effect(cmd, **_kwargs):
                if run_mock.call_count == 1:
                    return fail
                out_dir.mkdir(parents=True, exist_ok=True)
                (out_dir / "source_abc.mp4").write_bytes(b"mp4")
                return success

            run_mock.side_effect = run_side_effect
            with patch("media_engine.youtube_pipeline.ARTIFACTS_DIR", Path(tmp)):
                path = download_youtube_section(
                    "https://www.youtube.com/watch?v=seqhQpImJDo",
                    "workspace",
                    {"id": "clip_x", "start_ms": 0, "end_ms": 30_000},
                )
                self.assertTrue(path.endswith("source_abc.mp4"))
                self.assertEqual(run_mock.call_count, 2)
                first_cmd = run_mock.call_args_list[0].args[0]
                second_cmd = run_mock.call_args_list[1].args[0]
                self.assertIn("--no-update", first_cmd)
                self.assertIn("--extractor-args", first_cmd)
                self.assertNotEqual(first_cmd[first_cmd.index("-f") + 1], second_cmd[second_cmd.index("-f") + 1])


if __name__ == "__main__":
    unittest.main()
