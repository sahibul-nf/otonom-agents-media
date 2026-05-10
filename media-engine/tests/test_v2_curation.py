import json
import sqlite3
import unittest

from media_engine.db import ensure_schema_upgrades
from media_engine.cli import build_parser, insert_candidate
from media_engine.llm import build_chat_payload, parse_strict_json
from media_engine.scoring import score_candidate_text
from media_engine.transcript_quality import correct_text_with_glossary
from media_engine.youtube_pipeline import TranscriptEntry, choose_nourbit_premium_candidates


class V2CurationTests(unittest.TestCase):
    def test_schema_upgrade_adds_candidate_metadata_columns(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE clip_candidates (
              id TEXT PRIMARY KEY,
              profile_id TEXT NOT NULL,
              source_id TEXT NOT NULL,
              start_ms INTEGER NOT NULL,
              end_ms INTEGER NOT NULL,
              title_hook TEXT NOT NULL,
              viral_reason TEXT NOT NULL,
              transcript_span TEXT NOT NULL,
              risk_flags_json TEXT NOT NULL,
              status TEXT NOT NULL
            );
            """
        )

        ensure_schema_upgrades(conn)
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(clip_candidates)")}

        self.assertIn("score_json", columns)
        self.assertIn("curation_metadata_json", columns)
        self.assertIn("caption_source", columns)
        conn.close()

    def test_llm_json_cleaner_rejects_prose_and_accepts_markdown_json(self):
        self.assertEqual(parse_strict_json("```json\n{\"clips\": []}\n```"), {"clips": []})
        with self.assertRaises(ValueError):
            parse_strict_json("Tentu, berikut hasilnya: {\"clips\": []}")

    def test_llm_payload_builder_has_provider_compatible_shape(self):
        payload = build_chat_payload("model-test", "system", "user")

        self.assertEqual(payload["model"], "model-test")
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertEqual(payload["response_format"], {"type": "json_object"})

    def test_nourbit_glossary_fixes_arabic_indonesian_typos(self):
        text = correct_text_with_glossary("Alloh mengingatkan qolbu untuk jikir dan istigfar kepada rosulullah.")

        self.assertIn("Allah", text)
        self.assertIn("qalbu", text)
        self.assertIn("dzikir", text)
        self.assertIn("istighfar", text)
        self.assertIn("Rasulullah", text)

    def test_scoring_ranks_stronger_clip_higher(self):
        strong = score_candidate_text(
            "Kenapa hati kita kesepian padahal Allah dekat dan dzikir membuat hati tenang?",
            "Kenapa Hati Masih Kesepian?",
            95_000,
        )
        weak = score_candidate_text("Ini bagian pembukaan biasa tanpa inti yang jelas.", "Pembukaan", 20_000)

        self.assertGreater(strong["overall_score"], weak["overall_score"])
        self.assertTrue(all(0 <= value <= 100 for value in strong.values()))
        json.dumps(strong)

    def test_multi_candidate_selector_returns_non_overlapping_scored_candidates(self):
        entries = [
            TranscriptEntry(index * 1000, (index + 1) * 1000, "Alloh hati jikir tenang kesepian ibadah")
            for index in range(360)
        ]

        candidates = choose_nourbit_premium_candidates(
            "nourbit",
            "source",
            entries,
            {"caption": {"max_words_per_caption": 3}, "ai": {"remove_filler_words": False}},
            count=3,
        )

        self.assertEqual(len(candidates), 3)
        for candidate in candidates:
            self.assertIn("overall_score", candidate["score"])
            self.assertEqual(candidate["caption_source"], "youtube_glossary")
            self.assertIn("Allah", candidate["transcript_span"])
            self.assertGreaterEqual(candidate["end_ms"] - candidate["start_ms"], 45_000)
            self.assertLessEqual(candidate["end_ms"] - candidate["start_ms"], 120_000)
        for previous, current in zip(candidates, candidates[1:]):
            self.assertFalse(
                previous["start_ms"] < current["end_ms"] and previous["end_ms"] > current["start_ms"]
            )

    def test_cli_parser_supports_v2_commands(self):
        args = build_parser().parse_args(
            [
                "premium-curate",
                "--youtube-url",
                "https://youtu.be/test",
                "--count",
                "5",
                "--llm-provider",
                "deepseek",
            ]
        )

        self.assertEqual(args.count, 5)
        self.assertEqual(args.llm_provider, "deepseek")

    def test_insert_candidate_persists_score_metadata(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE clip_candidates (
              id TEXT PRIMARY KEY,
              profile_id TEXT NOT NULL,
              source_id TEXT NOT NULL,
              start_ms INTEGER NOT NULL,
              end_ms INTEGER NOT NULL,
              title_hook TEXT NOT NULL,
              viral_reason TEXT NOT NULL,
              transcript_span TEXT NOT NULL,
              risk_flags_json TEXT NOT NULL,
              status TEXT NOT NULL
            );
            """
        )
        ensure_schema_upgrades(conn)

        insert_candidate(
            conn,
            {
                "id": "clip_meta",
                "profile_id": "nourbit",
                "source_id": "source",
                "start_ms": 0,
                "end_ms": 60_000,
                "title_hook": "Kenapa Hati Masih Kesepian?",
                "viral_reason": "reason",
                "transcript_span": "Allah dekat",
                "risk_flags": [],
                "score": {"overall_score": 88},
                "curation_metadata": {"llm_provider": "none"},
                "caption_source": "youtube_glossary",
                "status": "draft",
            },
        )
        row = conn.execute("SELECT * FROM clip_candidates WHERE id = 'clip_meta'").fetchone()

        self.assertEqual(json.loads(row["score_json"])["overall_score"], 88)
        self.assertEqual(json.loads(row["curation_metadata_json"])["llm_provider"], "none")
        self.assertEqual(row["caption_source"], "youtube_glossary")
        conn.close()


if __name__ == "__main__":
    unittest.main()
