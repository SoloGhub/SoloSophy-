from __future__ import annotations

import unittest

import pandas as pd

from solosophy_engine.scenarios import build_conditional_scenarios


class ScenarioTests(unittest.TestCase):
    def test_scenarios_never_claim_probability_or_trade(self) -> None:
        frame = pd.DataFrame([{
            "bar_start_utc": pd.Timestamp("2026-08-28", tz="UTC"),
            "close": 100.0,
            "support_20": 95.0,
            "resistance_20": 105.0,
            "ema_26": 99.0,
            "atr_14": 2.0,
        }])
        scenarios = build_conditional_scenarios(frame, {"state": "range_or_low_trend_strength"})
        self.assertEqual(len(scenarios), 2)
        self.assertTrue(all(item["probability"] is None for item in scenarios))
        self.assertTrue(all(not item["trade_recommendation"] for item in scenarios))


if __name__ == "__main__":
    unittest.main()
