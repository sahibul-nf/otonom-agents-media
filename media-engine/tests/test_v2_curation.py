import json
import sqlite3
import unittest
from contextlib import redirect_stderr
from io import StringIO

from media_engine.db import ensure_schema_upgrades
from media_engine.autonomy import is_duplicate_candidate, token_jaccard
from media_engine.cli import ProgressBar, build_parser, insert_candidate
from media_engine.db import initialize
from media_engine.env_loader import load_env_file
from media_engine.llm import build_chat_payload, parse_strict_json, provider_config
from media_engine.scoring import score_candidate_text
from media_engine.transcript_quality import correct_text_with_glossary
from media_engine.youtube_pipeline import (
    TranscriptEntry,
    build_candidate,
    choose_nourbit_premium_candidates,
    fetch_youtube_transcript,
    hook_subtitle_for_span,
    opening_strength,
    refine_end_boundary,
    refine_start_boundary,
    title_for_span,
    _transcript_cache_path,
)


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
        self.assertIn("asr_metadata_json", columns)
        self.assertIn("render_quality_json", columns)
        self.assertIn("cost_json", columns)
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

    def test_groq_provider_config_uses_whitelisted_env_name(self):
        config = provider_config("groq")

        self.assertEqual(config["api_key_env"], "GROQ_API_KEY")
        self.assertIn("groq.com", config["base_url"])

    def test_env_loader_only_loads_whitelisted_keys(self):
        import os
        import tempfile

        with tempfile.NamedTemporaryFile("w", delete=False) as handle:
            handle.write("GROQ" + "_API_KEY" + "=" + "test-key\nUNSAFE_VALUE=bad\nGROQ_MODEL=test-model\n")
            path = handle.name

        loaded = load_env_file(path)

        self.assertEqual(loaded["GROQ_API_KEY"], "***REDACTED***")
        self.assertEqual(os.environ["GROQ_MODEL"], "test-model")
        self.assertNotIn("UNSAFE_VALUE", loaded)

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

    def test_scoring_prefers_duration_near_strategy_target(self):
        text = "Allah membuat hati tenang dengan dzikir dan ibadah yang lurus."
        near_target = score_candidate_text(text, "Rahasia Hati yang Tenang", 95_000, ideal_min_ms=45_000, ideal_target_ms=95_000, ideal_max_ms=120_000)
        too_short = score_candidate_text(text, "Rahasia Hati yang Tenang", 46_000, ideal_min_ms=45_000, ideal_target_ms=95_000, ideal_max_ms=120_000)

        self.assertGreater(near_target["retention_score"], too_short["retention_score"])

    def test_token_jaccard_catches_near_duplicate_transcripts(self):
        existing = {
            "title_hook": "Allah Tidak Pernah Jauh",
            "transcript_span": "Allah membuat hati manusia tenang dengan dzikir dan tidak perlu merasa sepi.",
        }
        candidate = {
            "title_hook": "Hati Tidak Perlu Sepi",
            "transcript_span": "Hati manusia tidak perlu merasa sepi karena dzikir membuat hati tenang.",
        }

        self.assertGreater(token_jaccard(candidate["transcript_span"], existing["transcript_span"]), 0.5)
        self.assertTrue(is_duplicate_candidate(candidate, [existing], threshold=0.75))

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
            self.assertGreaterEqual(candidate["end_ms"] - candidate["start_ms"], 20_000)
            self.assertLessEqual(candidate["end_ms"] - candidate["start_ms"], 180_000)
            self.assertEqual(candidate["curation_metadata"]["duration_preset"], "auto")
        for previous, current in zip(candidates, candidates[1:]):
            self.assertFalse(
                previous["start_ms"] < current["end_ms"] and previous["end_ms"] > current["start_ms"]
            )

    def test_duration_preset_changes_candidate_window(self):
        entries = [
            TranscriptEntry(index * 1000, (index + 1) * 1000, "Allah hati dzikir tenang kesepian ibadah")
            for index in range(240)
        ]

        quick = choose_nourbit_premium_candidates(
            "nourbit",
            "source",
            entries,
            {"caption": {"max_words_per_caption": 3}, "ai": {"remove_filler_words": False}},
            count=1,
            duration_preset="under_30s",
        )[0]
        deep = choose_nourbit_premium_candidates(
            "nourbit",
            "source",
            entries,
            {"caption": {"max_words_per_caption": 3}, "ai": {"remove_filler_words": False}},
            count=1,
            duration_preset="minutes_1_3",
        )[0]

        self.assertLessEqual(quick["end_ms"] - quick["start_ms"], 30_000)
        self.assertGreaterEqual(deep["end_ms"] - deep["start_ms"], 60_000)
        self.assertEqual(quick["curation_metadata"]["duration_preset"], "under_30s")
        self.assertEqual(deep["curation_metadata"]["duration_preset"], "minutes_1_3")
        self.assertIn("duration_reason", quick["curation_metadata"])
        self.assertIn("boundary_confidence", quick["curation_metadata"])

    def test_initialize_canonicalizes_legacy_generation_job_duration(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        initialize(conn)
        conn.execute("INSERT INTO media_profiles VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)", ("nourbit", "Nourbit", "niche", "[]", "preset", "cta", "wm"))
        conn.execute(
            """
            INSERT INTO generation_jobs
              (id, profile_id, source_id, source_url, count, clip_length_preset, brand_template,
               renderer, quality, caption_source, asr_model, llm_provider, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("gen_legacy", "nourbit", "source", "url", 1, "45-120s", "profiles/nourbit_opus_style.json", "remotion", "production", "whisper", "medium", "deepseek", "queued"),
        )
        initialize(conn)

        row = conn.execute("SELECT clip_length_preset FROM generation_jobs WHERE id = 'gen_legacy'").fetchone()
        self.assertEqual(row["clip_length_preset"], "minutes_1_3")
        conn.close()

    def test_end_boundary_trims_late_new_sentence_opener(self):
        entries = [
            TranscriptEntry(0, 18_000, "Allah membuat hati tenang saat manusia tidak bisa memberi apa apa"),
            TranscriptEntry(18_000, 47_000, "maka jangan cari bahagia dari makhluk karena hati akan lelah"),
            TranscriptEntry(47_500, 50_000, "Jadi pembahasan berikutnya"),
        ]

        self.assertEqual(refine_end_boundary(entries, 0, 50_000), 47_500)

    def test_end_boundary_keeps_minimum_duration_safe(self):
        entries = [
            TranscriptEntry(0, 38_000, "Allah membuat hati tenang saat manusia tidak bisa memberi apa apa"),
            TranscriptEntry(43_500, 46_000, "Jadi pembahasan berikutnya"),
        ]

        self.assertEqual(refine_end_boundary(entries, 0, 46_000), 46_000)

    def test_end_boundary_extends_crossing_incomplete_tail(self):
        entries = [
            TranscriptEntry(245_560, 253_920, "adalah Allah sumber dari cinta kita maka"),
            TranscriptEntry(249_920, 257_440, "ikhwah fillah jika cinta-cinta ini"),
            TranscriptEntry(253_920, 260_159, "menghalangi kita kepada Allah leburkan"),
            TranscriptEntry(257_440, 264_639, "cinta itu kepada cinta Allah subhanahu"),
            TranscriptEntry(260_160, 268_320, "wa taala Berarti cinta kita nafsiah"),
            TranscriptEntry(264_639, 270_160, "ego kita leburkan cinta ini dalam cinta"),
            TranscriptEntry(268_320, 273_960, "Allah Subhanahu"),
            TranscriptEntry(270_160, 276_880, "baik suami istri kawan dengan kawan ya"),
        ]

        self.assertEqual(refine_end_boundary(entries, 210_000, 270_000), 273_960)

    def test_start_boundary_skips_weak_opener_when_hook_arrives_early(self):
        entries = [
            TranscriptEntry(0, 5_000, "Nah jadi baik kita lanjutkan dulu"),
            TranscriptEntry(6_000, 18_000, "Kenapa hati manusia tetap kesepian padahal Allah sangat dekat"),
            TranscriptEntry(18_000, 70_000, "Dzikir membuat hati kembali tenang dan tidak mencari validasi manusia"),
        ]

        self.assertLess(opening_strength(entries, 0), opening_strength(entries, 6_000))
        self.assertEqual(refine_start_boundary(entries, 0, 70_000, 45_000), 6_000)

    def test_transcript_cache_can_load_without_network(self):
        cache_path = _transcript_cache_path("cached_video", ["id"])
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text('[{"start_ms": 0, "end_ms": 1000, "text": "Allah dekat"}]', encoding="utf-8")
        try:
            entries = fetch_youtube_transcript("https://youtu.be/cached_video", languages=["id"], use_cache=True)
        finally:
            cache_path.unlink(missing_ok=True)

        self.assertEqual(entries[0].text, "Allah dekat")

    def test_hook_subtitle_is_warmer_than_generic_reason(self):
        subtitle = hook_subtitle_for_span(
            "Bahagia sejati itu dari Allah bukan dari makhluk",
            "Bahagia Hanya dengan Allah",
        )

        self.assertNotEqual(subtitle, "Potongan singkat untuk menenangkan hati dan meluruskan arah.")
        self.assertLessEqual(len(subtitle.split()), 14)

    def test_title_fallback_is_derived_from_transcript_not_static(self):
        span = (
            "itu adalah apa maksudnya mujahadah sebelum kita disiksa oleh keadaan "
            "maka siksa diri sebelum disiksa oleh hawa nafsu"
        )

        title = title_for_span(span)
        subtitle = hook_subtitle_for_span(span, title)

        self.assertNotEqual(title, "Allah Tidak Pernah Jauh")
        self.assertGreaterEqual(len(title.split()), 4)
        self.assertNotEqual(title, "Allah Tidak Pernah Jauh")
        self.assertNotEqual(subtitle, "Potongan singkat untuk menenangkan hati dan meluruskan arah.")
        self.assertIn("ringkasan isi clip:", subtitle.lower())

    def test_unknown_title_fallback_uses_content_phrase(self):
        span = "cerita guru membimbing murid menjaga adab ketika belajar dan menerima nasihat"

        title = title_for_span(span)
        subtitle = hook_subtitle_for_span(span, title)

        self.assertEqual(title, "Cerita Guru Membimbing Murid Menjaga Adab Ketika")
        self.assertIn("cerita guru", subtitle.lower())
        self.assertNotIn("Allah Tidak Pernah Jauh", title)

    def test_candidate_rejects_static_llm_title_and_reason_when_span_mismatches(self):
        texts = [
            "cerita guru membimbing murid menjaga adab ketika belajar",
            "nasihat ini membuat murid lebih siap menerima ilmu",
        ]
        entries = [
            TranscriptEntry(index * 1000, (index + 1) * 1000, texts[index % len(texts)])
            for index in range(70)
        ]

        candidate = choose_nourbit_premium_candidates(
            "nourbit",
            "source",
            entries,
            {"caption": {"max_words_per_caption": 3}, "ai": {"remove_filler_words": False}},
            count=1,
            llm_provider="none",
            duration_preset="standard_short",
        )[0]

        self.assertNotEqual(candidate["title_hook"], "Allah Tidak Pernah Jauh")
        self.assertNotEqual(candidate["viral_reason"], "Potongan singkat untuk menenangkan hati dan meluruskan arah.")
        self.assertIn("murid", candidate["title_hook"].lower())
        self.assertEqual(candidate["curation_metadata"]["title_source"], "heuristic_span")

    def test_build_candidate_rejects_irrelevant_llm_static_fallbacks(self):
        entries = [
            TranscriptEntry(index * 1000, (index + 1) * 1000, "nasihat guru menjaga adab murid ketika belajar")
            for index in range(70)
        ]

        candidate = build_candidate(
            "nourbit",
            "source",
            entries,
            0,
            60_000,
            1,
            {"caption": {"max_words_per_caption": 3}, "ai": {"remove_filler_words": False}},
            llm_provider="deepseek",
            llm_suggestion={
                "title_hook": "Allah Tidak Pernah Jauh",
                "hook_subtitle": "Potongan singkat untuk menenangkan hati dan meluruskan arah.",
                "viral_reason": "Potongan singkat untuk menenangkan hati dan meluruskan arah.",
            },
        )

        self.assertNotEqual(candidate["title_hook"], "Allah Tidak Pernah Jauh")
        self.assertNotEqual(candidate["viral_reason"], "Potongan singkat untuk menenangkan hati dan meluruskan arah.")
        self.assertEqual(candidate["curation_metadata"]["title_source"], "heuristic_span")
        self.assertEqual(candidate["curation_metadata"]["reason_source"], "heuristic_span")

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

    def test_progress_bar_outputs_cli_indicator_to_stderr(self):
        stderr = StringIO()

        with redirect_stderr(stderr):
            bar = ProgressBar(total=2, width=4)
            bar.step("first")
            bar.step("done")

        output = stderr.getvalue()
        self.assertIn("[##--] 1/2 first", output)
        self.assertIn("[####] 2/2 done", output)

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
                "asr_metadata": {"engine": "mock"},
                "render_quality": {"quality_score": 91},
                "cost": {"estimated_total": 0.01},
                "status": "draft",
            },
        )
        row = conn.execute("SELECT * FROM clip_candidates WHERE id = 'clip_meta'").fetchone()

        self.assertEqual(json.loads(row["score_json"])["overall_score"], 88)
        self.assertEqual(json.loads(row["curation_metadata_json"])["llm_provider"], "none")
        self.assertEqual(row["caption_source"], "youtube_glossary")
        self.assertEqual(json.loads(row["asr_metadata_json"])["engine"], "mock")
        self.assertEqual(json.loads(row["render_quality_json"])["quality_score"], 91)
        self.assertEqual(json.loads(row["cost_json"])["estimated_total"], 0.01)
        conn.close()


if __name__ == "__main__":
    unittest.main()
