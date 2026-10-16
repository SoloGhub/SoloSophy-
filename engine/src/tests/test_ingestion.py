from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from solosophy_engine.ingestion import load_ibkr_history


def _write_payload(path: Path, high: list[float], captured: str = "2026-01-01T03:30:00Z") -> None:
    payload = {
        "captured_at_utc": captured,
        "source": "test",
        "request": {
            "asset": "GC",
            "contract_id": 1,
            "exchange": "COMEX",
            "contract_month": "202612",
            "step": "ONE_HOUR",
        },
        "response": {
            "time": ["2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z", "2026-01-01T03:00:00Z"],
            "open": [10.0, 11.0, 12.0],
            "high": high,
            "low": [9.0, 10.0, 11.0],
            "close": [10.5, 11.5, 12.5],
            "volume": [1.0, 2.0, 3.0],
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


class IngestionTests(unittest.TestCase):
    def test_incomplete_bar_is_quarantined(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.json"
            _write_payload(path, [11.0, 12.0, 13.0])
            loaded = load_ibkr_history(path)
            self.assertEqual(loaded.report["incomplete_bar_count"], 1)
            self.assertEqual(len(loaded.bars), 2)
            self.assertIn("incomplete_bar", set(loaded.quarantine["quarantine_reason"]))

    def test_impossible_ohlc_is_quarantined(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.json"
            _write_payload(path, [11.0, 11.0, 13.0], captured="2026-01-01T05:00:00Z")
            loaded = load_ibkr_history(path)
            self.assertEqual(loaded.report["impossible_ohlc_count"], 1)
            self.assertEqual(len(loaded.bars), 2)


if __name__ == "__main__":
    unittest.main()
