import io
import json
import sqlite3
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from unittest.mock import patch

from media_engine.cli import cmd_premium_batch
from media_engine.db import initialize


class PremiumBatchResilienceTests(unittest.TestCase):
    def test_batch_continues_after_single_render_failure(self):
        candidates = [
            {"id": "clip_ok", "title_hook": "OK", "start_ms": 0, "end_ms": 60_000},
            {"id": "clip_bad", "title_hook": "Bad", "start_ms": 60_000, "end_ms": 120_000},
            {"id": "clip_ok2", "title_hook": "OK2", "start_ms": 120_000, "end_ms": 180_000},
        ]
        render_calls: list[str] = []

        def fake_render(conn, candidate, profile, youtube_url, attribution, renderer, style, args, **kwargs):
            render_calls.append(str(candidate["id"]))
            if candidate["id"] == "clip_bad":
                raise RuntimeError("HyperFrames layout check failed. text_box_overflow")
            return {"candidate_id": candidate["id"], "title_hook": candidate["title_hook"]}

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        initialize(conn)
        conn.execute(
            "INSERT INTO media_profiles VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            ("nourbit", "Nourbit", "kajian", "[]", "premium", "cta", "wm"),
        )
        conn.execute(
            """
            INSERT INTO source_manifests
              (id, profile_id, source_url, owner_type, permission_status, allowed_use_json, publish_restrictions_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("source", "nourbit", "https://example.com", "public", "review_required", "{}", "{}"),
        )
        conn.commit()

        args = Namespace(
            db=":memory:",
            env_file=None,
            profile="nourbit",
            source_id="source",
            youtube_url="https://www.youtube.com/watch?v=test",
            source_attribution="",
            renderer="hyperframes",
            hyperframes_template="auto",
            hyperframes_format="auto",
            brand_system_template_id="",
            quality="draft",
            caption_source="youtube",
            asr_model="medium",
            speech_language="auto",
            transcript_languages="auto",
            clip_length_preset="auto",
            clip_min_seconds=20,
            clip_max_seconds=180,
            genres="",
            niche="",
            workspace_name="",
            style=None,
            shell_components="",
            llm_provider="none",
            count=3,
            curation_source="youtube",
        )

        buffer = io.StringIO()
        with patch("media_engine.cli.connect", return_value=conn), patch("media_engine.cli.load_env_file"), patch(
            "media_engine.cli.load_profile_and_source",
            return_value=({"id": "nourbit", "niche": "kajian", "name": "Nourbit"}, {}),
        ), patch(
            "media_engine.cli.fetch_curation_transcript_entries",
            return_value=([], {"curation_source": "youtube", "resolved_via": "youtube"}),
        ), patch(
            "media_engine.cli.load_style_for_render", return_value={}
        ), patch(
            "media_engine.cli.choose_nourbit_premium_candidates", return_value=candidates
        ), patch(
            "media_engine.cli.enrich_candidates_metadata", side_effect=lambda items, **kwargs: items
        ), patch(
            "media_engine.cli.render_premium_candidate", side_effect=fake_render
        ), redirect_stdout(buffer):
            cmd_premium_batch(args)

        payload = json.loads(buffer.getvalue())
        self.assertEqual(render_calls, ["clip_ok", "clip_bad", "clip_ok2"])
        self.assertEqual(payload["count"], 2)
        self.assertEqual(len(payload["failures"]), 1)
        self.assertEqual(payload["failures"][0]["candidate_id"], "clip_bad")
        conn.close()


if __name__ == "__main__":
    unittest.main()
