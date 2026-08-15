import json
import sqlite3
import unittest
from datetime import datetime, timedelta

from media_engine.autonomy import (
    MANUAL_HOLD_REASON,
    evaluate_quality_gate,
    get_autonomy_settings,
    reconcile_caption_holds,
    update_autonomy_settings,
)
from media_engine.db import initialize
from media_engine.scheduler import DEFAULT_TZ, process_due_auto_schedule
from media_engine.transcript_quality import correct_asr_words


class AutonomyTests(unittest.TestCase):
    def _conn(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        initialize(conn)
        conn.execute(
            "INSERT INTO media_profiles VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            ("nourbit", "Nourbit", "niche", "[]", "preset", "cta", "wm"),
        )
        conn.execute(
            """
            INSERT INTO source_manifests
              (id, profile_id, source_url, owner_type, permission_status,
               allowed_use_json, publish_restrictions_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("source", "nourbit", "https://example.com", "public", "review_required", "{}", "{}"),
        )
        return conn

    def test_quality_gate_marks_high_score_clip_pending_auto_schedule(self):
        conn = self._conn()
        settings = get_autonomy_settings(conn, "nourbit")
        candidate = {
            "score": {"overall_score": 88, "hook_score": 84, "asr_confidence": 93},
            "curation_metadata": {"boundary_confidence": 86},
            "asr_metadata": {"low_confidence_word_count": 0, "word_count": 40},
        }

        gate = evaluate_quality_gate(candidate, settings, now=datetime(2026, 5, 15, 9, 0, tzinfo=DEFAULT_TZ))

        self.assertTrue(gate["passed"])
        self.assertEqual(gate["status"], "pending_auto_schedule")
        self.assertIn("2026-05-15T21:00", gate["review_deadline_at"])
        conn.close()

    def test_typical_whisper_clip_is_ready_to_review_not_held(self):
        conn = self._conn()
        settings = get_autonomy_settings(conn, "nourbit")
        candidate = {
            "score": {"overall_score": 70, "hook_score": 45, "asr_confidence": 84},
            "curation_metadata": {"boundary_confidence": 58},
            "asr_metadata": {
                "caption_composer": {"word_count": 468, "low_confidence_word_count": 74},
            },
        }

        gate = evaluate_quality_gate(candidate, settings)

        self.assertFalse(gate["passed"])
        self.assertEqual(gate["status"], "rendered")
        self.assertEqual(gate["hold_reason"], "")
        conn.close()

    def test_quality_gate_holds_only_catastrophic_caption_confidence(self):
        conn = self._conn()
        settings = get_autonomy_settings(conn, "nourbit")
        candidate = {
            "score": {"overall_score": 90, "hook_score": 90, "asr_confidence": 42},
            "curation_metadata": {"boundary_confidence": 90},
            "asr_metadata": {"low_confidence_word_count": 0, "word_count": 80},
        }

        gate = evaluate_quality_gate(candidate, settings)

        self.assertFalse(gate["passed"])
        self.assertEqual(gate["status"], "held")
        self.assertEqual(gate["hold_reason"], "catastrophic_asr")
        conn.close()

    def test_quality_gate_holds_when_most_words_are_uncertain(self):
        conn = self._conn()
        settings = get_autonomy_settings(conn, "nourbit")
        candidate = {
            "score": {"overall_score": 80, "hook_score": 80, "asr_confidence": 70},
            "curation_metadata": {"boundary_confidence": 80},
            "asr_metadata": {
                "caption_composer": {"word_count": 200, "low_confidence_word_count": 90},
            },
        }

        gate = evaluate_quality_gate(candidate, settings)

        self.assertEqual(gate["status"], "held")
        self.assertEqual(gate["hold_reason"], "catastrophic_uncertain_ratio")
        conn.close()

    def test_reconcile_releases_legacy_four_word_holds(self):
        conn = self._conn()
        conn.execute(
            """
            INSERT INTO clip_candidates
              (id, profile_id, source_id, start_ms, end_ms, title_hook, viral_reason,
               transcript_span, risk_flags_json, score_json, asr_metadata_json,
               quality_gate_json, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "clip_legacy_hold",
                "nourbit",
                "source",
                0,
                120_000,
                "Hook",
                "Reason",
                "Transcript",
                "[]",
                json.dumps({"overall_score": 70, "hook_score": 55, "asr_confidence": 84}),
                json.dumps({"caption_composer": {"word_count": 468, "low_confidence_word_count": 74}}),
                json.dumps({"passed": False, "status": "held"}),
                "held",
            ),
        )
        conn.execute(
            """
            INSERT INTO clip_candidates
              (id, profile_id, source_id, start_ms, end_ms, title_hook, viral_reason,
               transcript_span, risk_flags_json, curation_metadata_json, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "clip_manual_hold",
                "nourbit",
                "source",
                0,
                60_000,
                "Manual",
                "Reason",
                "Transcript",
                "[]",
                json.dumps({"hold_reason": MANUAL_HOLD_REASON}),
                "held",
            ),
        )
        conn.commit()

        released = reconcile_caption_holds(conn)

        self.assertEqual(released, 1)
        statuses = {
            row["id"]: row["status"]
            for row in conn.execute("SELECT id, status FROM clip_candidates").fetchall()
        }
        self.assertEqual(statuses["clip_legacy_hold"], "rendered")
        self.assertEqual(statuses["clip_manual_hold"], "held")
        conn.close()

    def test_due_auto_schedule_only_schedules_after_deadline(self):
        conn = self._conn()
        update_autonomy_settings(conn, "nourbit", {"autonomy_mode": "assisted", "review_grace_hours": 12})
        deadline = datetime(2026, 5, 15, 9, 0, tzinfo=DEFAULT_TZ)
        conn.execute(
            """
            INSERT INTO clip_candidates
              (id, profile_id, source_id, start_ms, end_ms, title_hook, viral_reason,
               transcript_span, risk_flags_json, quality_gate_json, review_deadline_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "clip_auto",
                "nourbit",
                "source",
                0,
                60_000,
                "Hook",
                "Reason",
                "Transcript",
                "[]",
                json.dumps({"passed": True}),
                deadline.isoformat(timespec="minutes"),
                "pending_auto_schedule",
            ),
        )
        conn.commit()

        early = process_due_auto_schedule(conn, "nourbit", now=deadline - timedelta(minutes=1))
        due = process_due_auto_schedule(conn, "nourbit", now=deadline + timedelta(minutes=1))

        self.assertEqual(early, [])
        self.assertEqual(len(due), 1)
        status = conn.execute("SELECT status FROM clip_candidates WHERE id = 'clip_auto'").fetchone()["status"]
        self.assertEqual(status, "scheduled")
        conn.close()

    def test_asr_word_correction_preserves_timestamps(self):
        words = [
            {"text": "Alloh", "startMs": 0, "endMs": 200, "confidence": 0.9},
            {"text": "qolbu", "startMs": 220, "endMs": 500, "confidence": 0.5},
        ]

        corrected, metadata = correct_asr_words(words)

        self.assertEqual([word["text"] for word in corrected], ["Allah", "qalbu"])
        self.assertEqual(corrected[0]["startMs"], 0)
        self.assertEqual(corrected[1]["endMs"], 500)
        self.assertEqual(metadata["correction_count"], 2)
        self.assertEqual(metadata["low_confidence_word_count"], 1)


if __name__ == "__main__":
    unittest.main()
