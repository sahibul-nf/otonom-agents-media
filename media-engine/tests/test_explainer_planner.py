import unittest

from media_engine.explainer_planner import default_plan, normalize_plan, plan_explainer


class ExplainerPlannerTests(unittest.TestCase):
    def test_default_plan_has_alternating_types(self):
        plan = default_plan("Apa itu Bitcoin?")
        self.assertEqual(plan["title"], "Apa itu Bitcoin?")
        types = [scene["type"] for scene in plan["scenes"]]
        self.assertIn("avatar", types)
        self.assertIn("text", types)
        self.assertTrue(any(scene.get("clip_file") for scene in plan["scenes"] if scene["type"] == "avatar"))

    def test_normalize_rejects_bad_type(self):
        with self.assertRaises(ValueError):
            normalize_plan({"title": "x", "scenes": [{"id": "s1", "type": "slide", "headline": "h"}]})

    def test_plan_explainer_none_provider(self):
        plan = plan_explainer("DeFi", llm_provider="none")
        self.assertGreaterEqual(len(plan["scenes"]), 4)


if __name__ == "__main__":
    unittest.main()
