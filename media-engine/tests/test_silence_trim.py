"""Unit tests for silence trim planning and caption remapping."""

from __future__ import annotations

import unittest

from media_engine.silence_trim import (
    SilenceTrimConfig,
    build_keep_segments,
    clamp_keep_segments,
    plan_remove_pause,
    remap_caption_groups,
    remap_time_ms,
    remove_pause_from_captions,
    remove_pauses_batch_from_captions,
)


class SilenceTrimPlanningTests(unittest.TestCase):
    def test_leading_and_trailing_silence_removed(self):
        config = SilenceTrimConfig(keep_silence_ms=140, edge_pad_ms=60, min_silence_ms=450)
        keep = build_keep_segments(
            10_000,
            [(0, 800), (9_000, 10_000)],
            config,
        )
        self.assertEqual(keep[0][0], 740)  # 800 - edge_pad
        self.assertEqual(keep[-1][1], 9_000)
        kept = sum(end - start for start, end in keep)
        self.assertLess(kept, 10_000 - 500)

    def test_internal_dead_air_is_compressed_not_deleted_entirely(self):
        config = SilenceTrimConfig(keep_silence_ms=140, edge_pad_ms=60, min_silence_ms=450)
        keep = build_keep_segments(
            10_000,
            [(4_000, 5_200)],
            config,
        )
        # Speech + short breath merge into one keep, then jump past compressed silence.
        self.assertEqual(keep[0], (0, 4_140))
        self.assertEqual(keep[1], (5_200, 10_000))
        kept = sum(end - start for start, end in keep)
        self.assertEqual(kept, 4_140 + (10_000 - 5_200))

    def test_no_silence_keeps_full_timeline(self):
        keep = build_keep_segments(8_000, [], SilenceTrimConfig())
        self.assertEqual(keep, [(0, 8_000)])

    def test_remap_time_and_captions_follow_keep_segments(self):
        keep = [(0, 1000), (1000, 1140), (2000, 3000)]
        self.assertEqual(remap_time_ms(500, keep), 500)
        self.assertEqual(remap_time_ms(1000, keep), 1000)
        self.assertEqual(remap_time_ms(2100, keep), 1000 + 140 + 100)

        captions = [
            {
                "text": "hello there",
                "startMs": 0,
                "endMs": 900,
                "words": [
                    {"text": "hello", "startMs": 0, "endMs": 400},
                    {"text": "there", "startMs": 400, "endMs": 900},
                ],
            },
            {
                "text": "after pause",
                "startMs": 2100,
                "endMs": 2800,
                "words": [
                    {"text": "after", "startMs": 2100, "endMs": 2400},
                    {"text": "pause", "startMs": 2400, "endMs": 2800},
                ],
            },
        ]
        remapped = remap_caption_groups(captions, keep)
        self.assertEqual(len(remapped), 2)
        self.assertEqual(remapped[0]["words"][0]["startMs"], 0)
        self.assertEqual(remapped[1]["words"][0]["startMs"], 1000 + 140 + 100)
        # burn-in bridge restored
        self.assertEqual(remapped[0]["endMs"], remapped[1]["startMs"])

    def test_plan_remove_pause_compresses_selected_window(self):
        config = SilenceTrimConfig(keep_silence_ms=140, edge_pad_ms=60, min_silence_ms=450)
        keep = plan_remove_pause(10_000, 4_000, 1_200, config)
        self.assertEqual(keep[0], (0, 4_140))
        self.assertEqual(keep[1], (5_200, 10_000))
        kept = sum(end - start for start, end in keep)
        self.assertEqual(kept, 4_140 + (10_000 - 5_200))

    def test_remove_pause_remaps_captions_and_keeps_bridge(self):
        captions = [
            {
                "text": "before silence",
                "startMs": 0,
                "endMs": 4_000,
                "words": [
                    {"text": "before", "startMs": 0, "endMs": 800},
                    {"text": "silence", "startMs": 800, "endMs": 1_600},
                ],
            },
            {
                "text": "after silence",
                "startMs": 5_200,
                "endMs": 6_000,
                "words": [
                    {"text": "after", "startMs": 5_200, "endMs": 5_500},
                    {"text": "silence", "startMs": 5_500, "endMs": 6_000},
                ],
            },
        ]
        keep, remapped = remove_pause_from_captions(captions, 10_000, 4_000, 1_200)
        self.assertEqual(keep[0], (0, 4_140))
        self.assertEqual(keep[1], (5_200, 10_000))
        self.assertEqual(len(remapped), 2)
        self.assertEqual(remapped[0]["endMs"], remapped[1]["startMs"])
        self.assertLess(remapped[1]["words"][0]["startMs"], 5_200)
        self.assertEqual(remapped[1]["words"][0]["startMs"], 4_140)


    def test_forced_keep_clamps_to_source_duration(self):
        # Keep plan from a longer caption/YouTube span must still cut a shorter source.
        keep = clamp_keep_segments(97_664, [(0, 62_400), (68_790, 106_480)])
        self.assertEqual(keep, [(0, 62_400), (68_790, 97_664)])
        kept = sum(end - start for start, end in keep)
        self.assertLess(kept, 97_664 - 80)

    def test_batch_remove_pauses_compresses_all_matching_gaps(self):
        captions = [
            {
                "text": "one two",
                "startMs": 0,
                "endMs": 1_000,
                "words": [
                    {"text": "one", "startMs": 0, "endMs": 400},
                    {"text": "two", "startMs": 400, "endMs": 800},
                ],
            },
            {
                "text": "three",
                "startMs": 2_000,
                "endMs": 2_500,
                "words": [{"text": "three", "startMs": 2_000, "endMs": 2_500}],
            },
            {
                "text": "four",
                "startMs": 4_000,
                "endMs": 4_500,
                "words": [{"text": "four", "startMs": 4_000, "endMs": 4_500}],
            },
        ]
        keep, remapped, gaps = remove_pauses_batch_from_captions(captions, 5_000, min_gap_ms=500)
        self.assertEqual(len(gaps), 2)
        self.assertEqual(keep[0], (0, 940))  # 800 + keep_silence 140
        self.assertEqual(keep[1][0], 2_000)
        self.assertEqual(remapped[0]["endMs"], remapped[1]["startMs"])
        self.assertLess(remapped[-1]["endMs"], 4_500)


if __name__ == "__main__":
    unittest.main()
