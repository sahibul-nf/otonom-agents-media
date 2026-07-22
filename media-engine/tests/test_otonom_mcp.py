"""Thin MCP protocol smoke tests (no Cursor required)."""

from __future__ import annotations

import unittest

from media_engine.otonom_mcp import TOOLS, call_tool, handle_message


class OtonomMcpTests(unittest.TestCase):
    def test_initialize_and_tools_list(self):
        init = handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(init["result"]["serverInfo"]["name"], "otonom-media")
        listed = handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        names = {tool["name"] for tool in listed["result"]["tools"]}
        self.assertEqual(names, {tool["name"] for tool in TOOLS})
        self.assertIn("create_explainer", names)
        self.assertIn("import_avatar_clip", names)
        self.assertIn("list_review_queue", names)

    def test_unknown_tool(self):
        result = call_tool("nope", {})
        self.assertTrue(result["isError"])


if __name__ == "__main__":
    unittest.main()
