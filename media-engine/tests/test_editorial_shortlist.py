import unittest
from unittest.mock import patch

from media_engine.angle_recommend import recommend_content_angles
from media_engine.decisions import jev_decide
from media_engine.editorial import heuristic_editorial_score, select_editorial_shortlist
from media_engine.generation_jobs import build_generation_command, normalize_generation_payload
from media_engine.metadata_refresh import _local_metadata
from media_engine.post_copy import sanitize_post_caption, strip_unresolved_attribution
from media_engine.youtube_pipeline import _looks_like_transcript_slice


class EditorialShortlistTests(unittest.TestCase):
    def test_generic_sumber_line_is_removed(self):
        caption = strip_unresolved_attribution(
            "Poin utamanya jelas.\n\nSumber: klip kajian YouTube\n\n#Nourbit",
            channel="Ribath Nouraniyyah",
        )
        self.assertNotIn("Sumber", caption)
        self.assertNotIn("kajian", caption)
        self.assertIn("Poin utamanya", caption)

    def test_real_channel_source_line_stays(self):
        caption = strip_unresolved_attribution(
            "Poin utamanya jelas.\n\nSource: Ribath Nouraniyyah",
            channel="Ribath Nouraniyyah",
        )
        self.assertIn("Ribath Nouraniyyah", caption)

    def test_sanitize_shortens_on_a_sentence_without_ellipsis(self):
        text = "Kalimat pertama selesai. Kalimat kedua juga selesai dan terlalu panjang untuk batas ini."
        caption = sanitize_post_caption(text, limit=40)
        self.assertNotIn("...", caption)
        self.assertTrue(caption.endswith("."))

    def test_local_viral_reason_is_not_the_subtitle(self):
        metadata = _local_metadata("Allah membuat hati tenang dengan dzikir setiap malam dan ibadah yang terjaga.")
        self.assertNotEqual(metadata["viral_reason"].casefold(), metadata["hook_subtitle"].casefold())
        self.assertIn("Layak diposting", metadata["viral_reason"])

    def test_transcript_slice_hook_is_rejected(self):
        span = "kenapa inflasi masih bandel meski bunga sudah naik tinggi sekali"
        self.assertTrue(_looks_like_transcript_slice(span, span))
        self.assertFalse(_looks_like_transcript_slice("Inflasi belum kalah", span))

    def test_editorial_floor_drops_weak_heuristic_clips(self):
        weak = {
            "title_hook": "allah membuat hati tenang dengan dzikir",
            "hook_subtitle": "allah membuat hati tenang dengan dzikir",
            "viral_reason": "allah membuat hati tenang dengan dzikir",
            "transcript_span": "allah membuat hati tenang dengan dzikir setiap malam",
            "score": {"hook_score": 48},
        }
        strong = {
            "title_hook": "Bunga naik, harga tidak",
            "hook_subtitle": "Kebijakan moneter belum memadamkan inflasi.",
            "viral_reason": "Layak diposting karena hook menyatakan poinnya.",
            "transcript_span": "suku bunga naik tetapi harga konsumen tetap bandel di pasar",
            "score": {"hook_score": 90},
        }
        self.assertLess(heuristic_editorial_score(weak), 80)
        kept, stats = select_editorial_shortlist([weak, strong], provider="none", min_score=80, limit=5)
        self.assertEqual(stats["considered"], 2)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["title_hook"], "Bunga naik, harga tidak")

    def test_angle_recommendation_uses_catalog_ids(self):
        with patch("media_engine.angle_recommend._jev_angles", return_value=None), patch(
            "media_engine.angle_recommend._available_provider",
            return_value="none",
        ):
            result = recommend_content_angles(
                title="Bagaimana suku bunga mengubah harga",
                excerpt="Artinya kebijakan moneter bekerja lewat biaya pinjaman.",
            )
        self.assertTrue(result["angles"])
        self.assertIn(result["angles"][0]["id"], {"explainer", "opinion", "advice", "story", "tutorial", "history", "social_commentary"})

    def test_jev_failure_returns_none(self):
        with patch.dict("os.environ", {"TYPESAFE_API_KEY": "test"}, clear=False), patch(
            "media_engine.decisions.urllib.request.urlopen",
            side_effect=TimeoutError("slow"),
        ):
            self.assertIsNone(jev_decide("state", {"keep": {"type": "noul", "instructions": "keep?"}}))

    def test_shortlist_command_curates_without_rendering(self):
        payload = normalize_generation_payload(
            {
                "source_url": "https://youtube.com/watch?v=test",
                "stage": "shortlist",
                "count": 3,
            }
        )
        command = build_generation_command(payload)
        self.assertIn("premium-curate", command)
        self.assertNotIn("premium-batch", command)
        self.assertEqual(command[command.index("--min-editorial-score") + 1], "80")


if __name__ == "__main__":
    unittest.main()
