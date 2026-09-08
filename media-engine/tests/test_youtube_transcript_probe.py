import sys
import types
import unittest
from unittest.mock import MagicMock, patch

from media_engine.generation_jobs import build_generation_command, normalize_generation_payload
from media_engine.source_resolve import resolve_youtube_source
from media_engine.youtube_pipeline import (
    fetch_curation_transcript_entries,
    humanize_youtube_transcript_error,
    probe_youtube_transcript,
)


class YoutubeTranscriptProbeTests(unittest.TestCase):
    def test_humanize_github_boilerplate(self):
        message = humanize_youtube_transcript_error(
            RuntimeError(
                "If you are sure that the described cause is not responsible for this error "
                "please create an issue at https://github.com/jdepoix/youtube-transcript-api/issues"
            )
        )
        self.assertIn("No YouTube subtitles", message)
        self.assertNotIn("github.com", message)

    def test_probe_available_lists_languages(self):
        transcript = type("T", (), {"language_code": "id"})()
        mock_api = MagicMock()
        mock_api.list.return_value = [transcript]
        mock_errors = types.ModuleType("youtube_transcript_api._errors")
        mock_errors.TranscriptsDisabled = type("TranscriptsDisabled", (Exception,), {})
        mock_errors.NoTranscriptFound = type("NoTranscriptFound", (Exception,), {})
        mock_errors.VideoUnavailable = type("VideoUnavailable", (Exception,), {})
        mock_errors.AgeRestricted = type("AgeRestricted", (Exception,), {})
        mock_module = types.ModuleType("youtube_transcript_api")
        mock_module.YouTubeTranscriptApi = MagicMock(return_value=mock_api)
        with patch.dict(
            sys.modules,
            {
                "youtube_transcript_api": mock_module,
                "youtube_transcript_api._errors": mock_errors,
            },
        ):
            result = probe_youtube_transcript("abc12345678")
        self.assertEqual(result["status"], "available")
        self.assertIn("id", result["languages"])

    @patch("media_engine.youtube_pipeline.fetch_youtube_transcript")
    @patch("media_engine.youtube_pipeline.download_youtube_media_for_transcription")
    @patch("media_engine.asr.load_or_create_asr_words")
    def test_fetch_curation_auto_falls_back_to_audio(self, mock_asr, mock_download, mock_youtube):
        mock_youtube.side_effect = RuntimeError("No YouTube subtitles are available for this video yet.")
        mock_download.return_value = "/tmp/source.m4a"
        words = []
        for index in range(120):
            start = index * 300
            words.append({"text": f"kata{index}", "startMs": start, "endMs": start + 250, "confidence": 0.9})
        mock_asr.return_value = (words, {"engine": "faster-whisper"})
        entries, meta = fetch_curation_transcript_entries(
            "https://www.youtube.com/watch?v=testvideo12",
            languages=["id", "en"],
            curation_source="auto",
            profile_id="nourbit",
        )
        self.assertEqual(meta["resolved_via"], "audio")
        self.assertGreaterEqual(len(entries), 1)
        mock_download.assert_called_once()

    @patch("media_engine.youtube_pipeline.fetch_youtube_transcript")
    def test_fetch_curation_youtube_only_raises(self, mock_youtube):
        mock_youtube.side_effect = RuntimeError("No YouTube subtitles are available for this video yet.")
        with self.assertRaises(RuntimeError):
            fetch_curation_transcript_entries(
                "https://www.youtube.com/watch?v=testvideo12",
                languages=["id", "en"],
                curation_source="youtube",
            )

    def test_generation_payload_includes_curation_source(self):
        payload = normalize_generation_payload(
            {
                "source_url": "https://www.youtube.com/watch?v=test",
                "profile_id": "nourbit",
                "source_id": "nourbit_test",
                "count": 3,
                "curation_source": "audio",
            }
        )
        command = build_generation_command(payload)
        self.assertIn("--curation-source", command)
        self.assertIn("audio", command)

    @patch("media_engine.source_resolve.probe_youtube_transcript")
    @patch("media_engine.source_resolve.find_ytdlp", return_value="yt-dlp")
    @patch("media_engine.source_resolve.subprocess.run")
    def test_resolve_source_includes_transcript_probe(self, mock_run, _mock_ytdlp, mock_probe):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "vid12345678\tTitle\tChannel\tUploader\t3600\tthumb\thttps://youtube.com/watch?v=vid12345678\n"
        mock_run.return_value.stderr = ""
        mock_probe.return_value = {
            "status": "missing",
            "message": "No YouTube subtitles are available for this video yet.",
            "languages": [],
            "requested_languages": ["id", "en", "ar"],
        }
        payload = resolve_youtube_source("https://www.youtube.com/watch?v=vid12345678")
        self.assertEqual(payload["transcript"]["status"], "missing")
        self.assertTrue(any("Transcribe from audio" in warning for warning in payload["warnings"]))


if __name__ == "__main__":
    unittest.main()
