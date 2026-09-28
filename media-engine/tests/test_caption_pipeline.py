import unittest
from unittest.mock import patch

from media_engine.caption_pipeline import (
    _try_youtube_text,
    align_words_to_reconstructed_text,
    apply_youtube_text,
    asr_initial_prompt,
    build_polish_system_prompt,
    build_reconstruct_system_prompt,
    compute_caption_sync_score,
    polish_candidate_captions,
    polish_uncertain_words,
    reconstruct_llm_context,
    reconstruct_timed_captions_llm,
    reconstructed_text_is_grounded,
)
from media_engine.youtube_pipeline import TranscriptEntry


class CaptionPipelineTests(unittest.TestCase):
    def test_asr_prompt_uses_source_title_not_hardcoded_religion_only(self):
        prompt = asr_initial_prompt(
            {"title_hook": "Uang Itu Kotor?", "transcript_span": "uang bukan hal kotor"},
            source_title="5 Kebohongan Tentang Hidup",
            source_channel="Timothy Ronald",
            niche="tech finance",
            profile_id="workspace",
        )

        self.assertIn("Timothy Ronald", prompt)
        self.assertIn("Uang Itu Kotor?", prompt)
        self.assertIn("Bitcoin", prompt)
        self.assertNotEqual(prompt, "Allah, Rasulullah, dzikir, zikir, qalbu, sholawat, istighfar, ma'rifat, taubat, syukur")

    def test_youtube_text_replaces_uncertain_whisper_token_and_keeps_timing(self):
        whisper = [{"text": "wang", "startMs": 0, "endMs": 400, "confidence": 0.4}]
        entries = [TranscriptEntry(1000, 2000, "uang itu")]

        words, meta = apply_youtube_text(whisper, entries, clip_start_ms=1000)

        self.assertEqual(words[0]["text"], "uang")
        self.assertEqual(words[0]["startMs"], 0)
        self.assertEqual(words[0]["endMs"], 400)
        self.assertGreaterEqual(words[0]["confidence"], 0.92)
        self.assertEqual(meta["youtube_replaced"], 1)

    def test_youtube_skips_misaligned_high_confidence_token(self):
        whisper = [
            {"text": "Bitcoin", "startMs": 0, "endMs": 400, "confidence": 0.95},
            {"text": "naik", "startMs": 400, "endMs": 800, "confidence": 0.9},
        ]
        entries = [TranscriptEntry(0, 2000, "the market is rising")]

        words, meta = apply_youtube_text(whisper, entries, clip_start_ms=0)

        self.assertEqual(words[0]["text"], "Bitcoin")
        self.assertGreater(meta.get("youtube_skipped", 0), 0)
        self.assertEqual(meta["youtube_replaced"], 0)

    def test_youtube_skips_unrelated_low_confidence_token(self):
        whisper = [{"text": "Jika", "startMs": 0, "endMs": 400, "confidence": 0.49}]
        entries = [TranscriptEntry(0, 2000, "kenal teritorial")]

        words, meta = apply_youtube_text(whisper, entries, clip_start_ms=0)

        self.assertEqual(words[0]["text"], "Jika")
        self.assertEqual(meta["youtube_replaced"], 0)

    def test_youtube_maps_trimmed_times_through_keep_segments(self):
        whisper = [{"text": "wang", "startMs": 0, "endMs": 400, "confidence": 0.4}]
        entries = [TranscriptEntry(5000, 6000, "uang itu")]

        words, meta = apply_youtube_text(
            whisper,
            entries,
            clip_start_ms=0,
            keep_segments=[(5000, 20_000)],
        )

        self.assertEqual(words[0]["text"], "uang")
        self.assertEqual(words[0]["startMs"], 0)
        self.assertEqual(meta["youtube_replaced"], 1)

    def test_hybrid_skips_youtube_when_trim_timeline_unknown(self):
        words = [{"text": "Jika", "startMs": 6220, "endMs": 7000, "confidence": 0.49}]
        candidate = {"start_ms": 1_536_440, "silence_trim": {"skipped": "already_trimmed"}}
        next_words, meta = _try_youtube_text(words, candidate, "https://youtube.com/watch?v=test", ["id"])
        self.assertEqual(next_words[0]["text"], "Jika")
        self.assertEqual(meta.get("reason"), "silence_trim_timeline_unknown")

    def test_align_keeps_opening_words_llm_dropped(self):
        words = [
            {"text": "Dia", "startMs": 0, "endMs": 200},
            {"text": "memuji", "startMs": 200, "endMs": 400},
            {"text": "dengan", "startMs": 400, "endMs": 600},
            {"text": "sifatnya", "startMs": 600, "endMs": 800},
        ]
        aligned = align_words_to_reconstructed_text(words, "Dengan sifatnya")
        joined = " ".join(item["text"] for item in aligned)
        self.assertIn("Dia", joined)
        self.assertIn("memuji", joined)
        self.assertEqual(aligned[0]["startMs"], 0)

    def test_align_does_not_invent_title_synonyms(self):
        words = [
            {"text": "cari", "startMs": 0, "endMs": 200},
            {"text": "rida", "startMs": 200, "endMs": 400},
        ]
        aligned = align_words_to_reconstructed_text(words, "mencari Ilahi")
        joined = " ".join(item["text"] for item in aligned).lower()
        self.assertIn("rida", joined)
        self.assertNotIn("ilahi", joined)

    def test_caption_sync_score_penalizes_late_first_word(self):
        late = [{"text": "Jika", "startMs": 6220, "endMs": 7000}, {"text": "akhir", "startMs": 78_000, "endMs": 79_500}]
        early = [{"text": "Jika", "startMs": 120, "endMs": 800}, {"text": "akhir", "startMs": 78_000, "endMs": 79_500}]
        self.assertLess(compute_caption_sync_score(late, video_ms=80_000), 70)
        self.assertGreaterEqual(compute_caption_sync_score(early, video_ms=80_000), 95)
        self.assertNotEqual(compute_caption_sync_score(late, video_ms=80_000), 95)

    def test_youtube_absent_leaves_whisper_words(self):
        whisper = [{"text": "wang", "startMs": 0, "endMs": 400, "confidence": 0.4}]

        words, meta = apply_youtube_text(whisper, [], clip_start_ms=0)

        self.assertEqual(words[0]["text"], "wang")
        self.assertEqual(meta["youtube_replaced"], 0)

    def test_llm_polish_replaces_uncertain_token_without_moving_times(self):
        words = [
            {"text": "pilih", "startMs": 0, "endMs": 200, "confidence": 0.9},
            {"text": "bitkon", "startMs": 200, "endMs": 500, "confidence": 0.4},
        ]

        with patch(
            "media_engine.caption_pipeline.call_llm_json",
            return_value={"replacements": [{"index": 1, "text": "Bitcoin"}]},
        ):
            next_words, meta = polish_uncertain_words(words, "deepseek", context="crypto clip")

        self.assertEqual(next_words[1]["text"], "Bitcoin")
        self.assertEqual(next_words[1]["startMs"], 200)
        self.assertEqual(next_words[1]["endMs"], 500)
        self.assertEqual(meta["llm_replacements"], 1)

    def test_llm_polish_skipped_when_provider_none(self):
        words = [{"text": "bitkon", "startMs": 0, "endMs": 200, "confidence": 0.4}]

        next_words, meta = polish_uncertain_words(words, "none")

        self.assertEqual(next_words[0]["text"], "bitkon")
        self.assertTrue(meta["llm_skipped"])

    def test_polish_prompt_uses_tech_domain_for_finance_niche(self):
        prompt = build_polish_system_prompt(detected_language="en", niche="markets", profile_id="workspace")

        self.assertIn("tech, finance", prompt.lower())
        self.assertNotIn("indonesian/arabic asr captions", prompt.lower())

    def test_polish_prompt_uses_devotional_domain_for_nourbit(self):
        prompt = build_polish_system_prompt(detected_language="id", profile_id="nourbit")

        self.assertIn("devotional", prompt.lower())

    def test_reconstruct_prompt_mentions_punctuation(self):
        prompt = build_reconstruct_system_prompt(detected_language="id", profile_id="nourbit")

        self.assertIn("punctuation", prompt.lower())
        self.assertIn("speaker's words", prompt.lower())
        prompt = build_reconstruct_system_prompt(detected_language="id", profile_id="nourbit")

        self.assertIn("punctuation", prompt.lower())

    def test_align_words_removes_stutter_and_keeps_timing(self):
        words = [
            {"text": "memberikan", "startMs": 0, "endMs": 200},
            {"text": "bi", "startMs": 200, "endMs": 300},
            {"text": "memberikan", "startMs": 300, "endMs": 500},
            {"text": "memberikan", "startMs": 500, "endMs": 700},
            {"text": "lah", "startMs": 700, "endMs": 900},
        ]
        aligned = align_words_to_reconstructed_text(words, "Memberikan lah.")

        self.assertEqual(len(aligned), 2)
        self.assertEqual(aligned[0]["text"], "Memberikan")
        self.assertEqual(aligned[0]["startMs"], 0)
        self.assertEqual(aligned[1]["text"], "lah.")
        self.assertEqual(aligned[1]["startMs"], 700)

    def test_reconstruct_timed_captions_llm_uses_llm_output(self):
        words = [
            {"text": "mentakbir", "startMs": 0, "endMs": 200, "confidence": 0.4},
            {"text": "kena", "startMs": 200, "endMs": 400, "confidence": 0.4},
            {"text": "cinta", "startMs": 400, "endMs": 600, "confidence": 0.4},
        ]
        with patch(
            "media_engine.caption_pipeline.call_llm_json",
            return_value={"text": "Mentadbir karena cinta."},
        ):
            next_words, meta = reconstruct_timed_captions_llm(words, "deepseek", profile_id="nourbit")

        self.assertTrue(meta["llm_reconstructed"])
        self.assertEqual(next_words[0]["text"], "Mentadbir")
        self.assertEqual(next_words[-1]["text"], "cinta.")
        self.assertEqual(next_words[0]["startMs"], 0)

    def test_reconstruct_llm_context_omits_domain_vocabulary_dump(self):
        context = reconstruct_llm_context(
            {
                "title_hook": "Saat Allah Menahan",
                "transcript_span": "Baik. Ee saudara-saudariku yang Allah. Semua orang interaksinya",
                "profile_id": "nourbit",
            }
        )
        self.assertIn("Saat Allah Menahan", context)
        self.assertNotIn("Rasulullah", context)
        self.assertNotIn("dzikir", context)

    def test_reconstructed_text_rejects_glossary_injections(self):
        raw = "Baik Ee saudara-saudariku yang Allah"
        injected = "Baik. Saudara-saudari, Rasulullah, yang bukan Allah."
        self.assertFalse(reconstructed_text_is_grounded(raw, injected))
        self.assertTrue(reconstructed_text_is_grounded(raw, "Baik. Saudara-saudariku yang Allah."))

    def test_reconstruct_timed_captions_llm_keeps_asr_when_ungrounded(self):
        words = [
            {"text": "Baik", "startMs": 0, "endMs": 200},
            {"text": "saudara-saudariku", "startMs": 200, "endMs": 600},
            {"text": "yang", "startMs": 600, "endMs": 700},
            {"text": "Allah", "startMs": 700, "endMs": 900},
        ]
        with patch(
            "media_engine.caption_pipeline.call_llm_json",
            return_value={"text": "Baik. Saudara-saudari, Rasulullah, yang bukan Allah."},
        ):
            next_words, meta = reconstruct_timed_captions_llm(words, "deepseek", profile_id="nourbit")

        self.assertFalse(meta["llm_reconstructed"])
        self.assertTrue(meta.get("llm_rejected_ungrounded"))
        self.assertEqual([word["text"] for word in next_words], ["Baik", "saudara-saudariku", "yang", "Allah"])

    def test_polish_candidate_captions_updates_caption_corrections(self):
        candidate = {
            "title_hook": "Saksi Cinta",
            "transcript_span": "mentakbir kena cinta",
            "profile_id": "nourbit",
            "caption_corrections": {},
            "asr_metadata": {"detected_language": "id"},
        }
        captions = [
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
        with patch(
            "media_engine.caption_pipeline.call_llm_json",
            return_value={"text": "Mentadbir karena cinta."},
        ):
            result = polish_candidate_captions(candidate, captions, llm_provider="deepseek", profile_id="nourbit")

        self.assertTrue(result["caption_corrections"]["ai_polish"])
        self.assertGreater(len(result["captions"]), 0)
        joined = " ".join(caption["text"] for caption in result["captions"])
        self.assertIn("Mentadbir", joined)
        self.assertIn("karena", joined)


if __name__ == "__main__":
    unittest.main()
