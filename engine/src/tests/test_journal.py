from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from solosophy_engine.journal import append_snapshot, verify_journal


class JournalTests(unittest.TestCase):
    def _payload(self, symbol: str = "GC") -> dict:
        return {
            "input_fingerprint": "abc",
            "symbol": symbol,
            "data_cutoff_utc": "2026-08-28T00:00:00+00:00",
            "ruleset_version": "test",
            "value": 1,
        }

    def test_append_deduplicate_and_verify(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            first = append_snapshot(path, self._payload())
            second = append_snapshot(path, self._payload("SI"))
            duplicate = append_snapshot(path, self._payload())
            self.assertTrue(first["appended"])
            self.assertFalse(duplicate["appended"])
            self.assertTrue(second["appended"])
            self.assertEqual(verify_journal(path)["record_count"], 2)

    def test_tampering_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            append_snapshot(path, self._payload())
            record = json.loads(path.read_text(encoding="utf-8"))
            record["value"] = 2
            path.write_text(json.dumps(record) + "\n", encoding="utf-8")
            self.assertFalse(verify_journal(path)["valid"])


if __name__ == "__main__":
    unittest.main()
