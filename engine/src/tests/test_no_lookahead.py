from __future__ import annotations

import numpy as np
import pandas as pd
from pandas.testing import assert_series_equal
import unittest

from solosophy_engine.indicators import compute_features


def _frame(length: int = 300) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    close = 100 + np.cumsum(rng.normal(0, 1, length))
    return pd.DataFrame(
        {
            "bar_start_utc": pd.date_range("2025-01-01", periods=length, freq="h", tz="UTC"),
            "open": close - 0.1,
            "high": close + 0.8,
            "low": close - 0.8,
            "close": close,
            "volume": rng.integers(10, 100, length).astype(float),
        }
    )


class NoLookaheadTests(unittest.TestCase):
    def test_future_mutation_does_not_change_past_features(self) -> None:
        original = _frame()
        changed = original.copy()
        changed.loc[250:, ["open", "high", "low", "close"]] *= 3
        first = compute_features(original)
        second = compute_features(changed)
        for column in ("atr_14", "rsi_14", "macd", "adx_14", "support_20", "resistance_20"):
            assert_series_equal(first.loc[:249, column], second.loc[:249, column], check_names=False)


if __name__ == "__main__":
    unittest.main()
