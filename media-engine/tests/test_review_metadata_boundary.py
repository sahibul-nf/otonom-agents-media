import json
import sqlite3
import unittest
from unittest.mock import patch

from media_engine.clip_boundaries import update_clip_boundary
from media_engine.db import initialize
from media_engine.metadata_refresh import refresh_candidate_metadata, save_candidate_hook_metadata


def make_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    initialize(conn)
    conn.execute(
        "INSERT INTO media_profiles VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
        ("nourbit", "Nourbit", "niche", "[]", "lecture_clean", "cta", "wm"),
    )
    conn.execute(
        "INSERT INTO source_manifests VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
        ("src", "nourbit", "https://youtube.com/watch?v=test", "community", "public_third_party", "", "[]", 1, "", "[]"),
    )
    conn.execute(
        """
        INSERT INTO clip_candidates
          (id, profile_id, source_id, start_ms, end_ms, title_hook, hook_subtitle,
           viral_reason, transcript_span, risk_flags_json, score_json,
           curation_metadata_json, caption_corrections_json, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "clip",
            "nourbit",
            "src",
            120_000,
            210_000,
            "Allah Tidak Pernah Jauh",
            "Potongan singkat untuk menenangkan hati dan meluruskan arah.",
            "Potongan singkat untuk menenangkan hati dan meluruskan arah.",
            "Saat hati gelisah, dzikir kepada Allah membuat manusia ingat bahwa Allah selalu dekat dan tidak meninggalkan hambanya.",
            "[]",
            "{}",
            '{"llm_provider":"none"}',
            "{}",
            "rendered",
        ),
    )
    conn.commit()
    return conn


class ReviewMetadataBoundaryTests(unittest.TestCase):
    def test_local_metadata_refresh_replaces_generic_fallback(self):
        conn = make_conn()

        result = refresh_candidate_metadata(conn, "clip", mode="local")
        row = conn.execute("SELECT title_hook, hook_subtitle, viral_reason, status FROM clip_candidates WHERE id = 'clip'").fetchone()
        metadata = json.loads(conn.execute("SELECT curation_metadata_json FROM clip_candidates WHERE id = 'clip'").fetchone()[0])

        self.assertEqual(row["status"], "rendered")
        self.assertNotEqual(row["hook_subtitle"], "Potongan singkat untuk menenangkan hati dan meluruskan arah.")
        self.assertEqual(result["hook_subtitle"], row["hook_subtitle"])
        self.assertEqual(metadata["metadata_refresh_mode"], "local")
        self.assertIn("overall_score", json.loads(conn.execute("SELECT score_json FROM clip_candidates WHERE id = 'clip'").fetchone()[0]))
        conn.close()

    def test_smart_metadata_falls_back_when_llm_is_generic(self):
        conn = make_conn()
        with patch("media_engine.metadata_refresh.available_metadata_provider", return_value="deepseek"), patch(
            "media_engine.metadata_refresh.call_llm_json",
            return_value={
                "title_hook": "Allah Tidak Pernah Jauh",
                "hook_subtitle": "Potongan singkat untuk menenangkan hati dan meluruskan arah.",
                "viral_reason": "Potongan singkat untuk menenangkan hati dan meluruskan arah.",
            },
        ):
            result = refresh_candidate_metadata(conn, "clip", mode="smart")
        self.assertNotEqual(result["title_hook"], "Allah Tidak Pernah Jauh")
        self.assertNotEqual(result["hook_subtitle"], "Potongan singkat untuk menenangkan hati dan meluruskan arah.")
        conn.close()

    def test_smart_metadata_rejects_blessing_litany_llm(self):
        conn = make_conn()
        with patch("media_engine.metadata_refresh.available_metadata_provider", return_value="openai"), patch(
            "media_engine.metadata_refresh.call_llm_json",
            return_value={
                "title_hook": "Allah Berkahi Keluarga Allah Pasangan Keturunan Allah Berkahi",
                "hook_subtitle": "Hadratu qutblah Engkau ya Allah sehingga kami merasakan dekatnya nikmatnya.",
                "viral_reason": "Doa keluarga.",
            },
        ):
            result = refresh_candidate_metadata(conn, "clip", mode="smart")
        self.assertNotIn("Pasangan", result["title_hook"])
        self.assertNotIn("hadratu", result["hook_subtitle"].lower())
        conn.close()

    def test_smart_metadata_accepts_paraphrased_llm_title(self):
        conn = make_conn()
        with patch("media_engine.metadata_refresh.available_metadata_provider", return_value="openai"), patch(
            "media_engine.metadata_refresh.call_llm_json",
            return_value={
                "title_hook": "Kenal Allah di Dunia",
                "hook_subtitle": "Doa agar hijab hati terangkat supaya kita mengenal Allah sebelum akhirat.",
                "viral_reason": "Hook spiritual yang merangkum inti clip, bukan klausa pembuka ASR.",
            },
        ):
            result = refresh_candidate_metadata(conn, "clip", mode="smart")
        self.assertEqual(result["title_hook"], "Kenal Allah di Dunia")
        self.assertIn("hijab hati", result["hook_subtitle"].lower())
        conn.close()

    def test_manual_hook_metadata_persists_and_marks_source(self):
        conn = make_conn()
        result = save_candidate_hook_metadata(
            conn,
            "clip",
            "Kenal Allah di Dunia",
            "Doa agar hati terangkat sebelum akhirat.",
        )
        row = conn.execute(
            "SELECT title_hook, hook_subtitle, viral_reason, curation_metadata_json FROM clip_candidates WHERE id = 'clip'",
        ).fetchone()
        metadata = json.loads(row["curation_metadata_json"])

        self.assertEqual(result["title_hook"], "Kenal Allah di Dunia")
        self.assertEqual(row["title_hook"], "Kenal Allah di Dunia")
        self.assertEqual(row["hook_subtitle"], "Doa agar hati terangkat sebelum akhirat.")
        self.assertEqual(metadata["title_source"], "manual_edit")
        self.assertEqual(metadata["subtitle_source"], "manual_edit")
        conn.close()

    def test_boundary_update_rejects_published_and_invalid_duration(self):
        conn = make_conn()
        with self.assertRaises(ValueError):
            update_clip_boundary(conn, "clip", 10_000, 10_000)
        with self.assertRaises(ValueError):
            update_clip_boundary(conn, "clip", 10_000, 15_000)
        conn.execute("UPDATE clip_candidates SET status = 'published' WHERE id = 'clip'")
        conn.commit()
        with self.assertRaises(ValueError):
            update_clip_boundary(conn, "clip", 100_000, 130_000)
        conn.close()

    def test_boundary_update_holds_scheduled_clip_and_marks_manual_captions_stale(self):
        conn = make_conn()
        conn.execute("UPDATE clip_candidates SET status = 'scheduled', caption_corrections_json = ? WHERE id = 'clip'", ('{"manual_edit": true, "edited_captions": [{"text": "old"}]}',))
        conn.execute(
            "INSERT INTO scheduled_posts (id, candidate_id, profile_id, scheduled_at, status) VALUES (?, ?, ?, ?, ?)",
            ("sched", "clip", "nourbit", "2026-05-20T09:00:00+07:00", "scheduled"),
        )
        conn.commit()

        result = update_clip_boundary(conn, "clip", 130_000, 190_000)
        row = conn.execute("SELECT status, start_ms, end_ms, caption_corrections_json FROM clip_candidates WHERE id = 'clip'").fetchone()
        schedule_count = conn.execute("SELECT count(*) FROM scheduled_posts WHERE candidate_id = 'clip'").fetchone()[0]
        corrections = json.loads(row["caption_corrections_json"])

        self.assertEqual(result["status"], "held")
        self.assertEqual(row["start_ms"], 130_000)
        self.assertEqual(row["end_ms"], 190_000)
        self.assertTrue(corrections["manual_edit_stale"])
        self.assertEqual(schedule_count, 0)
        conn.close()


if __name__ == "__main__":
    unittest.main()
