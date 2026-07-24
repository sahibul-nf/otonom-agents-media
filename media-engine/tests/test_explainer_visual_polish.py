import tempfile
import unittest
from pathlib import Path

from media_engine.explainer_stitch import _render_title_png, render_title_card


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
                label="KEY POINT",
                scene_type="text",
            )
            _render_title_png(
                broll_png,
                headline="How supply works",
                narration="Halving cuts new issuance over time.",
                label="B-ROLL",
                scene_type="broll",
            )
            self.assertTrue(text_png.exists())
            self.assertTrue(broll_png.exists())
            self.assertNotEqual(text_png.read_bytes(), broll_png.read_bytes())
            self.assertGreater(text_png.stat().st_size, 20_000)

    def test_title_card_renders_mp4(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "card.mp4"
            render_title_card(
                output_path=out,
                headline="Risk vs reward",
                narration="Do your own research.",
                duration=2.0,
                label="KEY POINT",
                scene_type="text",
            )
            self.assertTrue(out.exists())
            self.assertGreater(out.stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()
