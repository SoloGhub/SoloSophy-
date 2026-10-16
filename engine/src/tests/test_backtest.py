from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from solosophy_engine.backtest import (
    directional_signal,
    regime_conditioned_signal,
    validate_directional_rules,
    validate_rule_candidates,
    walk_forward_validate,
)
from solosophy_engine.indicators import compute_features


class BacktestTests(unittest.TestCase):
    def _features(self, length: int = 500) -> pd.DataFrame:
        close = np.linspace(100.0, 250.0, length)
        frame = pd.DataFrame(
            {
                "bar_start_utc": pd.date_range("2025-01-01", periods=length, freq="h", tz="UTC"),
                "open": close - 0.1,
                "high": close + 0.5,
                "low": close - 0.5,
                "close": close,
                "volume": np.full(length, 100.0),
            }
        )
        return compute_features(frame)

    def test_directional_signal_has_no_future_dependency(self) -> None:
        first = self._features()
        changed = first.copy()
        changed.loc[400:, ["close", "ema_12", "ema_26", "sma_50"]] *= 2
        self.assertTrue(directional_signal(first).loc[:399].equals(directional_signal(changed).loc[:399]))

    def test_holdout_metrics_are_emitted(self) -> None:
        report = validate_directional_rules(self._features(), "hourly")
        self.assertEqual(report["status"], "descriptive_validation_only")
        self.assertIn("holdout", report["horizons"]["4"])
        self.assertFalse(report["probability_calibration_permitted"])

    def test_three_candidate_families_are_compared(self) -> None:
        report = validate_rule_candidates(self._features(), "hourly")
        self.assertEqual(
            set(report["candidate_reports"]),
            {
                "trend_following_baseline",
                "mean_reversion_baseline",
                "breakout_baseline",
                "regime_conditioned_baseline",
            },
        )
        self.assertFalse(report["probability_calibration_permitted"])

    def test_walk_forward_is_purged_and_keeps_probabilities_blocked(self) -> None:
        features = self._features(800)
        report = walk_forward_validate(
            features,
            regime_conditioned_signal(features),
            "hourly",
            "regime_conditioned_baseline",
        )
        self.assertEqual(report["label_leakage_control"], "purged_by_forward_horizon")
        self.assertFalse(report["probability_calibration_permitted"])
        for fold in report["horizons"]["24"]["folds"]:
            self.assertEqual(fold["purged_training_rows"], 24)


if __name__ == "__main__":
    unittest.main()
