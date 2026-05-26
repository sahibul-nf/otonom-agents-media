import unittest

from media_engine.rendering import (
    PREMIUM_PRESET,
    build_premium_filter_script,
    build_caption_segments,
    build_premium_render_contract,
    validate_premium_duration,
)
from media_engine.hyperframes_renderer import build_hyperframes_index_html
from media_engine.hyperframes_templates import list_hyperframes_templates
from media_engine.captions import group_word_captions, normalize_word_timeline
from media_engine.youtube_pipeline import TranscriptEntry, choose_nourbit_premium_candidate


class PremiumRenderingTests(unittest.TestCase):
    def test_premium_contract_contains_publish_gated_fields(self):
        candidate = {
            "id": "clip_test",
            "start_ms": 335000,
            "end_ms": 455000,
            "title_hook": "Kenapa Hati Masih Kesepian?",
            "viral_reason": "Momen reflektif yang kuat.",
            "transcript_span": "Allah selalu bersama kita maka hati tidak perlu merasa kesepian.",
            "timed_captions": [
                {
                    "text": "Allah selalu bersama kita",
                    "startMs": 0,
                    "endMs": 2200,
                    "words": [
                        {"text": "Allah", "startMs": 0, "endMs": 500},
                        {"text": "selalu", "startMs": 500, "endMs": 1100},
                        {"text": "bersama", "startMs": 1100, "endMs": 1700},
                        {"text": "kita", "startMs": 1700, "endMs": 2200},
                    ],
                }
            ],
        }
        profile = {
            "id": "nourbit",
            "watermark_text": "Nourbit Clips",
            "cta_text": "Follow Nourbit untuk nasihat singkat lainnya",
        }

        contract = build_premium_render_contract(
            candidate,
            profile,
            "runtime/render_test/source.mp4",
            "https://www.youtube.com/live/WSg7MGv4_Fs",
            "Source: Ribath Nouraniyyah Hasyimiyyah",
        )

        self.assertEqual(contract["composition"], "HyperFramesPremiumClip")
        self.assertEqual(contract["stylePreset"], PREMIUM_PRESET)
        self.assertEqual(contract["width"], 1080)
        self.assertEqual(contract["height"], 1920)
        self.assertTrue(contract["publishSafety"]["reviewRequired"])
        self.assertTrue(contract["publishSafety"]["autoPublishAllowed"])
        self.assertGreater(len(contract["captions"]), 0)
        self.assertEqual(contract["captionDiagnostics"]["maxConcurrentEvents"], 1)

    def test_hyperframes_html_contains_required_runtime_contract(self):
        candidate = {
            "id": "clip_hyper",
            "start_ms": 0,
            "end_ms": 60_000,
            "title_hook": "Allah Tidak Pernah Jauh",
            "viral_reason": "Momen reflektif yang kuat.",
            "transcript_span": "Allah selalu bersama kita.",
            "timed_captions": [
                {
                    "text": "Allah selalu bersama",
                    "startMs": 0,
                    "endMs": 1200,
                    "words": [
                        {"text": "Allah", "startMs": 0, "endMs": 400},
                        {"text": "selalu", "startMs": 400, "endMs": 800},
                        {"text": "bersama", "startMs": 800, "endMs": 1200},
                    ],
                }
            ],
        }
        profile = {
            "id": "nourbit",
            "watermark_text": "Nourbit Clips",
            "cta_text": "Follow Nourbit untuk nasihat singkat lainnya",
        }
        contract = build_premium_render_contract(candidate, profile, "source.mp4", "https://youtu.be/test", "Source")

        html = build_hyperframes_index_html(contract)

        self.assertIn('data-composition-id="premium-hyperframes"', html)
        self.assertIn('data-width="1080"', html)
        self.assertIn('data-height="1920"', html)
        self.assertIn("<video", html)
        self.assertIn("muted playsinline", html)
        self.assertIn("<audio", html)
        self.assertIn('window.__timelines["premium-hyperframes"]', html)
        self.assertIn('data-track-index="2"', html)

    def test_hyperframes_all_templates_emit_required_contract(self):
        candidate = {
            "id": "clip_hyper_templates",
            "start_ms": 0,
            "end_ms": 60_000,
            "title_hook": "Template Siap Pakai",
            "viral_reason": "Momen reflektif yang kuat.",
            "transcript_span": "Allah selalu bersama kita.",
            "timed_captions": [
                {
                    "text": "Allah selalu bersama",
                    "startMs": 0,
                    "endMs": 1500,
                    "words": [
                        {"text": "Allah", "startMs": 0, "endMs": 500},
                        {"text": "selalu", "startMs": 500, "endMs": 1000},
                        {"text": "bersama", "startMs": 1000, "endMs": 1500},
                    ],
                }
            ],
        }
        profile = {"id": "nourbit", "watermark_text": "Nourbit Clips", "cta_text": "Follow Nourbit"}
        contract = build_premium_render_contract(candidate, profile, "source.mp4", "https://youtu.be/test", "Source")

        for template in list_hyperframes_templates():
            with self.subTest(template=template["id"]):
                html = build_hyperframes_index_html(contract, hyperframes_template=template["id"])
                self.assertIn(f'"hyperframesTemplate": "{template["id"]}"', html)
                self.assertIn('"templateVersion": "1.1.0"', html)
                self.assertIn("<video", html)
                self.assertIn("muted playsinline", html)
                self.assertIn("<audio", html)
                self.assertIn('data-track-index="0"', html)
                self.assertIn('data-track-index="4"', html)
                self.assertIn('window.__timelines["premium-hyperframes"]', html)

    def test_hyperframes_caption_clips_leave_micro_gap_for_linter(self):
        candidate = {
            "id": "clip_hyper_adjacent",
            "start_ms": 0,
            "end_ms": 60_000,
            "title_hook": "Caption Rapat",
            "viral_reason": "Momen reflektif yang kuat.",
            "transcript_span": "satu dua tiga empat",
            "timed_captions": [
                {"text": "satu dua", "startMs": 0, "endMs": 1000, "words": [{"text": "satu", "startMs": 0, "endMs": 500}, {"text": "dua", "startMs": 500, "endMs": 1000}]},
                {"text": "tiga empat", "startMs": 1000, "endMs": 2000, "words": [{"text": "tiga", "startMs": 1000, "endMs": 1500}, {"text": "empat", "startMs": 1500, "endMs": 2000}]},
            ],
        }
        profile = {"id": "nourbit", "watermark_text": "Nourbit Clips", "cta_text": "Follow Nourbit"}
        contract = build_premium_render_contract(candidate, profile, "source.mp4", "https://youtu.be/test", "Source")

        html = build_hyperframes_index_html(contract)

        self.assertIn('data-start="0.000" data-duration="1.498"', html)
        self.assertIn('data-start="1.500" data-duration="0.498"', html)

    def test_premium_duration_bounds(self):
        validate_premium_duration(20_000)
        validate_premium_duration(180_000)
        with self.assertRaises(ValueError):
            validate_premium_duration(19_999)
        with self.assertRaises(ValueError):
            validate_premium_duration(180_001)

    def test_caption_segments_fit_duration(self):
        captions = build_caption_segments("satu dua tiga empat lima enam tujuh delapan sembilan", 10_000)
        self.assertEqual(captions[0]["startMs"], 0)
        self.assertLessEqual(captions[-1]["endMs"], 10_000)

    def test_candidate_uses_word_timed_captions_from_transcript_entries(self):
        entries = [
            TranscriptEntry(index * 1000, (index + 1) * 1000, "Allah selalu bersama")
            for index in range(100)
        ]
        candidate = choose_nourbit_premium_candidate(
            "nourbit",
            "source",
            entries,
            {"caption": {"max_words_per_caption": 3}, "ai": {"remove_filler_words": False}},
        )

        self.assertIn("timed_captions", candidate)
        self.assertIn("words", candidate["timed_captions"][0])
        self.assertEqual(candidate["timed_captions"][0]["words"][0]["startMs"], 0)
        self.assertLess(
            candidate["timed_captions"][0]["words"][0]["endMs"],
            candidate["timed_captions"][0]["endMs"],
        )

    def test_caption_groups_bridge_gaps_until_next_caption(self):
        groups = group_word_captions(
            [
                {"text": "Allah", "startMs": 0, "endMs": 120},
                {"text": "selalu", "startMs": 300, "endMs": 420},
                {"text": "bersama", "startMs": 900, "endMs": 1040},
                {"text": "kita", "startMs": 1500, "endMs": 1640},
            ],
            max_words_per_caption=2,
        )

        self.assertEqual(groups[0]["endMs"], groups[1]["startMs"])

    def test_out_of_order_words_are_sorted_and_normalized(self):
        words = normalize_word_timeline(
            [
                {"text": "yang", "startMs": 3165, "endMs": 4220},
                {"text": "dibaca", "startMs": 4220, "endMs": 5279},
                {"text": "allahuziri", "startMs": 3000, "endMs": 3704},
                {"text": "depannya", "startMs": 5816, "endMs": 6520},
                {"text": "Allahu", "startMs": 5280, "endMs": 12400},
                {"text": "Mai", "startMs": 6520, "endMs": 8000},
            ]
        )

        self.assertEqual([word["text"] for word in words[:3]], ["allahuziri", "yang", "dibaca"])
        self.assertEqual([word["startMs"] for word in words], sorted(word["startMs"] for word in words))
        for previous, current in zip(words, words[1:]):
            self.assertLessEqual(previous["endMs"], current["startMs"])

    def test_caption_events_are_exclusive_for_overlapping_transcript_words(self):
        candidate = {
            "id": "clip_overlap",
            "start_ms": 0,
            "end_ms": 95_000,
            "title_hook": "Kenapa Hati Masih Kesepian?",
            "viral_reason": "Momen reflektif yang kuat.",
            "transcript_span": "allahuziri yang dibaca Allahu depannya Mai",
            "timed_captions": [
                {
                    "text": "yang dibaca allahuziri",
                    "startMs": 3165,
                    "endMs": 5279,
                    "words": [
                        {"text": "yang", "startMs": 3165, "endMs": 4220},
                        {"text": "dibaca", "startMs": 4220, "endMs": 5279},
                        {"text": "allahuziri", "startMs": 3000, "endMs": 3704},
                    ],
                },
                {
                    "text": "depannya Allahu Mai",
                    "startMs": 5280,
                    "endMs": 8000,
                    "words": [
                        {"text": "depannya", "startMs": 5816, "endMs": 6520},
                        {"text": "Allahu", "startMs": 5280, "endMs": 12400},
                        {"text": "Mai", "startMs": 6520, "endMs": 8000},
                    ],
                },
            ],
        }
        profile = {
            "id": "nourbit",
            "watermark_text": "Nourbit Clips",
            "cta_text": "Follow Nourbit untuk nasihat singkat lainnya",
        }

        contract = build_premium_render_contract(
            candidate,
            profile,
            "source.mp4",
            "https://www.youtube.com/live/WSg7MGv4_Fs",
            "Source: Ribath Nouraniyyah Hasyimiyyah",
        )

        self.assertEqual(contract["captionDiagnostics"]["maxConcurrentEvents"], 1)
        self.assertEqual(contract["captionDiagnostics"]["overlapCount"], 0)
        for previous, current in zip(contract["captionEvents"], contract["captionEvents"][1:]):
            self.assertLessEqual(previous["endMs"], current["startMs"])

    def test_ffmpeg_filter_no_longer_collapses_early_caption_events_to_five_seconds(self):
        candidate = {
            "id": "clip_early",
            "start_ms": 0,
            "end_ms": 95_000,
            "title_hook": "Allah Tidak Pernah Jauh",
            "viral_reason": "Momen reflektif yang kuat.",
            "transcript_span": "Allah selalu bersama",
            "timed_captions": [
                {
                    "text": "Allah selalu bersama",
                    "startMs": 0,
                    "endMs": 1200,
                    "words": [
                        {"text": "Allah", "startMs": 0, "endMs": 400},
                        {"text": "selalu", "startMs": 400, "endMs": 800},
                        {"text": "bersama", "startMs": 800, "endMs": 1200},
                    ],
                }
            ],
        }
        profile = {
            "id": "nourbit",
            "watermark_text": "Nourbit Clips",
            "cta_text": "Follow Nourbit untuk nasihat singkat lainnya",
        }

        contract = build_premium_render_contract(candidate, profile, "source.mp4", "https://youtu.be/test", "Source")
        script = build_premium_filter_script(contract, len(contract["captionEvents"]))

        self.assertEqual(contract["captionEvents"][0]["startMs"], 0)
        self.assertIn("gte(t,0.000)*lt(t,0.400)", script)
        self.assertNotIn("between(t", script)
        self.assertNotIn("gte(t,5.000)*lt", script)

    def test_hook_title_remains_title_only(self):
        candidate = {
            "id": "clip_hook",
            "start_ms": 0,
            "end_ms": 95_000,
            "title_hook": "Kenapa Hati Masih Kesepian?",
            "viral_reason": "Momen reflektif yang kuat.",
            "transcript_span": "Allah selalu bersama kita.",
            "timed_captions": [
                {
                    "text": "Allah selalu bersama kita",
                    "startMs": 0,
                    "endMs": 2200,
                    "words": [
                        {"text": "Allah", "startMs": 0, "endMs": 500},
                        {"text": "selalu", "startMs": 500, "endMs": 1100},
                        {"text": "bersama", "startMs": 1100, "endMs": 1700},
                        {"text": "kita", "startMs": 1700, "endMs": 2200},
                    ],
                }
            ],
        }
        profile = {
            "id": "nourbit",
            "watermark_text": "Nourbit Clips",
            "cta_text": "Follow Nourbit untuk nasihat singkat lainnya",
        }

        contract = build_premium_render_contract(candidate, profile, "source.mp4", "https://youtu.be/test", "Source")

        self.assertEqual(contract["titleHook"], "Kenapa Hati Masih Kesepian?")
        self.assertNotIn("Nourbit Clips", contract["titleHook"])

    def test_hook_subtitle_uses_candidate_specific_copy(self):
        candidate = {
            "id": "clip_hook_subtitle",
            "start_ms": 0,
            "end_ms": 95_000,
            "title_hook": "Bahagia Hanya dengan Allah",
            "hook_subtitle": "Bahagia yang tidak sibuk mencari validasi dari makhluk.",
            "viral_reason": "Momen reflektif yang kuat.",
            "transcript_span": "Allah selalu bersama kita.",
            "timed_captions": [
                {
                    "text": "Allah selalu bersama kita",
                    "startMs": 0,
                    "endMs": 2200,
                    "words": [
                        {"text": "Allah", "startMs": 0, "endMs": 500},
                        {"text": "selalu", "startMs": 500, "endMs": 1100},
                        {"text": "bersama", "startMs": 1100, "endMs": 1700},
                        {"text": "kita", "startMs": 1700, "endMs": 2200},
                    ],
                }
            ],
        }
        profile = {
            "id": "nourbit",
            "watermark_text": "Nourbit Clips",
            "cta_text": "Follow Nourbit untuk nasihat singkat lainnya",
        }

        contract = build_premium_render_contract(candidate, profile, "source.mp4", "https://youtu.be/test", "Source")

        self.assertEqual(contract["subtitle"], "Bahagia yang tidak sibuk mencari validasi dari makhluk.")


if __name__ == "__main__":
    unittest.main()
