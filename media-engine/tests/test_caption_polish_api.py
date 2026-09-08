import json
import sqlite3
import unittest
from unittest.mock import patch

from media_engine.caption_pipeline import polish_candidate_captions
from media_engine.db import initialize


def make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    initialize(conn)
    conn.execute(
        "INSERT INTO media_profiles VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
        ("nourbit", "Nourbit", "devotional", "[]", "lecture_clean", "cta", "wm"),
    )
    conn.execute(
        "INSERT INTO source_manifests VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
        ("src", "nourbit", "https://youtube.com/watch?v=test", "community", "public_third_party", "", "[]", 1, "", "[]"),
    )
    return conn


def insert_candidate(conn: sqlite3.Connection, candidate_id: str = "clip_1") -> None:
    conn.execute(
        """
        INSERT INTO clip_candidates
          (id, profile_id, source_id, start_ms, end_ms, title_hook, hook_subtitle,
           viral_reason, transcript_span, risk_flags_json, score_json,
           curation_metadata_json, caption_corrections_json, asr_metadata_json, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            candidate_id,
            "nourbit",
            "src",
            0,
            30_000,
            "Saksi Cinta",
            "",
            "Reason",
            "mentakbir kena cinta",
            "[]",
            "{}",
            "{}",
            "{}",
            json.dumps({"detected_language": "id"}),
            "rendered",
        ),
    )
    conn.execute(
        """
        INSERT INTO render_jobs
          (id, candidate_id, preset, crop_strategy, caption_style, status, output_path, metadata_json)
        VALUES (?, ?, 'short', 'center', 'karaoke', 'completed', 'artifacts/test.mp4', ?)
        """,
        (
            "render_1",
            candidate_id,
            json.dumps(
                {
                    "captions": [
                        {
                            "text": "mentakbir kena cinta",
                            "startMs": 0,
                            "endMs": 900,
                            "words": [
                                {"text": "mentakbir", "startMs": 0, "endMs": 300},
                                {"text": "kena", "startMs": 300, "endMs": 600},
                                {"text": "cinta", "startMs": 600, "endMs": 900},
                            ],
                        }
                    ]
                }
            ),
        ),
    )
    conn.commit()


class CaptionPolishApiTests(unittest.TestCase):
    def test_polish_candidate_captions_persists_ai_polish_metadata(self):
        conn = make_conn()
        insert_candidate(conn)
        row = conn.execute("SELECT * FROM clip_candidates WHERE id = 'clip_1'").fetchone()
        render_metadata = json.loads(
            conn.execute("SELECT metadata_json FROM render_jobs WHERE candidate_id = 'clip_1'").fetchone()["metadata_json"]
        )
        candidate = dict(row)
        candidate["caption_corrections"] = {}
        candidate["asr_metadata"] = json.loads(candidate["asr_metadata_json"])
        captions = render_metadata["captions"]

        with patch(
            "media_engine.caption_pipeline.call_llm_json",
            return_value={"text": "Mentadbir karena cinta."},
        ):
            result = polish_candidate_captions(
                candidate,
                captions,
                llm_provider="deepseek",
                profile_id="nourbit",
                niche="devotional",
            )

        conn.execute(
            """
            UPDATE clip_candidates
            SET caption_corrections_json = ?, caption_source = 'ai_polish', status = 'held'
            WHERE id = 'clip_1'
            """,
            (json.dumps(result["caption_corrections"], ensure_ascii=False),),
        )
        conn.commit()
        saved = conn.execute(
            "SELECT caption_corrections_json, caption_source, status FROM clip_candidates WHERE id = 'clip_1'"
        ).fetchone()
        corrections = json.loads(saved["caption_corrections_json"])

        self.assertEqual(saved["caption_source"], "ai_polish")
        self.assertEqual(saved["status"], "held")
        self.assertTrue(corrections["ai_polish"])
        self.assertGreater(len(corrections["edited_captions"]), 0)
        joined = " ".join(item["text"] for item in corrections["edited_captions"])
        self.assertIn("Mentadbir", joined)
        self.assertIn("karena", joined)
        conn.close()


if __name__ == "__main__":
    unittest.main()
