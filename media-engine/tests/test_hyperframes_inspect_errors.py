import json
import unittest

from media_engine.generation_jobs import _failure_summary, _partial_batch_message
from media_engine.hyperframes_renderer import summarize_hyperframes_inspect_failure


INSPECT_SAMPLE = {
    "ok": False,
    "errorCount": 1,
    "issues": [
        {
            "code": "text_box_overflow",
            "severity": "error",
            "message": "Text extends outside its nearest visual/container box.",
            "text": "Jika Tidak Ada Yang Ingkar, Benarkah Cintamu?",
        }
    ],
}


class HyperframesInspectErrorTests(unittest.TestCase):
    def test_summarize_inspect_failure_is_human_readable(self):
        message = summarize_hyperframes_inspect_failure(json.dumps(INSPECT_SAMPLE))
        self.assertIn("text_box_overflow", message)
        self.assertIn("Jika Tidak Ada", message)
        self.assertNotEqual(message.strip(), "{")

    def test_failure_summary_parses_inspect_json_from_traceback(self):
        output = (
            "Traceback...\n"
            'RuntimeError: hyperframes inspect failed: {\n'
            + json.dumps(INSPECT_SAMPLE)
            + "\n}"
        )
        summary = _failure_summary(output, 1)
        self.assertIn("text_box_overflow", summary)

    def test_partial_batch_message(self):
        message = _partial_batch_message(
            {
                "renders": [{"candidate_id": "a"}],
                "failures": [{"error": "HyperFrames layout check failed. text_box_overflow"}],
            }
        )
        self.assertIn("1 clip(s) rendered", message)
        self.assertIn("1 failed", message)


if __name__ == "__main__":
    unittest.main()
