import tempfile
import unittest
from pathlib import Path

from media_engine.explainer_stitch import (
    _render_card_layers,
    _render_title_png,
    extract_audio_track,
    probe_duration_seconds,
    render_title_card,
)


class ExplainerVisualPolishTests(unittest.TestCase):
    def test_title_png_text_vs_broll_differ(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            text_png = root / "text.png"
            broll_png = root / "broll.png"
            _render_title_png(
                text_png,
                headline="Bitcoin is scarce",
                narration="Only 21 million will ever exist.",
                label="KEY TAKEAWAY",
                scene_type="text",
            )
            _render_title_png(
                broll_png,
                headline="How supply works",
                narration="Halving cuts new issuance over time.",
                label="SIGNAL SNAPSHOT",
                scene_type="broll",
            )
            self.assertTrue(text_png.exists())
            self.assertTrue(broll_png.exists())
            self.assertNotEqual(text_png.read_bytes(), broll_png.read_bytes())
            self.assertGreater(text_png.stat().st_size, 20_000)

    def test_card_layers_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            base, content, accent = _render_card_layers(
                Path(tmp),
                headline="Risk vs reward",
                narration="Do your own research.",
                label="KEY TAKEAWAY",
                scene_type="text",
            )
            self.assertTrue(base.exists())
            self.assertTrue(content.exists())
            self.assertTrue(accent.exists())

    def test_title_card_renders_mp4(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "card.mp4"
            render_title_card(
                output_path=out,
                headline="Risk vs reward",
                narration="Do your own research.",
                duration=2.0,
                label="KEY TAKEAWAY",
                scene_type="text",
            )
            self.assertTrue(out.exists())
            self.assertGreater(out.stat().st_size, 1000)

    def test_title_card_muxes_narration_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Build a short card, extract its (silent) AAC, then remux as VO fixture.
            silent_card = root / "silent.mp4"
            render_title_card(
                output_path=silent_card,
                headline="Tone bed",
                narration="placeholder",
                duration=2.0,
                scene_type="text",
            )
            audio = root / "vo.m4a"
            extract_audio_track(silent_card, audio)
            out = root / "vo_card.mp4"
            render_title_card(
                output_path=out,
                headline="With voice",
                narration="Muxed narration path.",
                duration=2.0,
                scene_type="text",
                audio_path=audio,
            )
            self.assertTrue(out.exists())
            self.assertGreater(probe_duration_seconds(out), 1.5)
            # Ensure we did not leave a zero-size audio track file.
            self.assertGreater(audio.stat().st_size, 100)


if __name__ == "__main__":
    unittest.main()
