"""Self-checks for peer-chat.py addressing and message framing: python3 -m unittest test_peer_chat.py"""

import importlib.util
import os
import unittest

spec = importlib.util.spec_from_file_location("pc", os.path.join(os.path.dirname(__file__), "peer-chat.py"))
pc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pc)

TREE = {"result": {"tree": {"workspaces": [
    {"id": "W1", "sessions": [
        {"id": "S1", "name": "main", "surfaces": [{"paneID": "P1"}, {"paneID": "P2"}]},
        {"id": "S2", "name": "side", "parent": "S1", "surfaces": [{"paneID": "P3"}]},
    ]},
    {"id": "W2", "sessions": [{"id": "S9", "name": "other", "surfaces": [{"paneID": "P9"}]}]},
]}}}


class Resolve(unittest.TestCase):
    def setUp(self):
        self.orig = pc.registered_agent

    def tearDown(self):
        pc.registered_agent = self.orig

    def agents(self, table):
        pc.registered_agent = lambda sid, pane: table.get(pane)

    def test_other_session_same_workspace(self):
        self.agents({"P1": "claude", "P3": "agy", "P9": "agy"})
        self.assertEqual(pc.resolve_peer("agy", "S1", "P1", TREE), ("S2", "P3"))

    def test_other_workspace_ignored(self):
        self.agents({"P1": "claude", "P9": "codex"})
        with self.assertRaisesRegex(pc.ChatError, "no running codex"):
            pc.resolve_peer("codex", "S1", "P1", TREE)

    def test_self_excluded_and_ambiguous(self):
        self.agents({"P1": "claude", "P2": "claude", "P3": "claude"})
        with self.assertRaisesRegex(pc.ChatError, "several claude"):
            pc.resolve_peer("claude", "S1", "P1", TREE)

    def test_explicit_address(self):
        self.assertEqual(pc.resolve_peer("S9:P9", "S1", "P1", TREE), ("S9", "P9"))
        with self.assertRaises(pc.ChatError):
            pc.resolve_peer("S9:", "S1", "P1", TREE)


class Compose(unittest.TestCase):
    def test_header_and_reply_line(self):
        m = pc.compose("hello", "claude", "S1:P1")
        self.assertTrue(m.startswith("[peer chat] from claude at S1:P1\nhello"))
        self.assertIn("peer-chat.py say --to S1:P1", m)

    def test_forwarded_frame_not_doubled(self):
        m = pc.compose(pc.compose("hello", "agy", "S2:P3"), "claude", "S1:P1")
        self.assertEqual(m.count("[peer chat]"), 1)
        self.assertEqual(m.count("If you answer"), 1)

    def test_empty(self):
        with self.assertRaises(pc.ChatError):
            pc.compose("  ", "claude", "S1:P1")


if __name__ == "__main__":
    unittest.main()
