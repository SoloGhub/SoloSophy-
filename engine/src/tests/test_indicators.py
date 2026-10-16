from __future__ import annotations

import numpy as np
import pandas as pd
import unittest

from solosophy_engine.indicators import compute_features, true_range


def _frame(length: int = 260) -> pd.DataFrame:
    close = np.linspace(100.0, 150.0, length)
    return pd.DataFrame(
        {
            "bar_start_utc": pd.date_range("2025-01-01", periods=length, freq="D", tz="UTC"),
            "open": close - 0.2,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": np.full(length, 100.0),
        }
    )


class IndicatorTests(unittest.TestCase):
    def test_true_range_known_values(self) -> None:
        frame = pd.DataFrame({"high": [10.0, 13.0], "low": [8.0, 11.0], "close": [9.0, 12.0]})
        result = true_range(frame)
        self.assertEqual(result.tolist(), [2.0, 4.0])

    def test_features_warm_up_and_finish(self) -> None:
        result = compute_features(_frame())
        self.assertTrue(pd.isna(result.loc[198, "sma_200"]))
        self.assertFalse(pd.isna(result.loc[199, "sma_200"]))
        self.assertEqual(result.iloc[-1]["rsi_14"], 100.0)


if __name__ == "__main__":
    unittest.main()
