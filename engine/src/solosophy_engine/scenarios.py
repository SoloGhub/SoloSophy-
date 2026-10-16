from __future__ import annotations

from typing import Any

import pandas as pd


def _level(value: Any) -> float | None:
    return None if value is None or pd.isna(value) else float(value)


def build_conditional_scenarios(features: pd.DataFrame, state: dict[str, Any]) -> list[dict[str, Any]]:
    """Describe conditional paths from measured levels without probabilities."""
    if features.empty or state.get("state") == "NO_ANALYSIS":
        return []
    row = features.iloc[-1]
    close = _level(row.get("close"))
    support = _level(row.get("support_20"))
    resistance = _level(row.get("resistance_20"))
    ema_slow = _level(row.get("ema_26"))
    atr = _level(row.get("atr_14"))
    if None in (close, support, resistance, ema_slow, atr) or atr == 0:
        return []
    regime = state["state"]
    common = {
        "regime": regime,
        "data_cutoff_utc": row["bar_start_utc"].isoformat(),
        "probability": None,
        "probability_status": "withheld_unvalidated",
        "trade_recommendation": False,
        "level_basis": "prior_twenty_bar_extremes_and_current_indicators",
    }
    if regime == "trend_up_strong":
        return [{
            **common,
            "scenario": "uptrend_continuation_condition",
            "trigger": {"condition": "close_above_resistance", "level": resistance},
            "invalidation": {"condition": "close_below_slow_ema", "level": ema_slow},
            "reference_zone": {"support": support, "resistance": resistance},
        }]
    if regime == "trend_down_strong":
        return [{
            **common,
            "scenario": "downtrend_continuation_condition",
            "trigger": {"condition": "close_below_support", "level": support},
            "invalidation": {"condition": "close_above_slow_ema", "level": ema_slow},
            "reference_zone": {"support": support, "resistance": resistance},
        }]
    if regime == "range_or_low_trend_strength":
        return [
            {
                **common,
                "scenario": "range_support_reversion_condition",
                "trigger": {"condition": "close_near_support_within_one_atr", "level": support},
                "invalidation": {"condition": "close_below_support_by_one_atr", "level": support - atr},
                "reference_zone": {"support": support, "resistance": resistance},
            },
            {
                **common,
                "scenario": "range_resistance_reversion_condition",
                "trigger": {"condition": "close_near_resistance_within_one_atr", "level": resistance},
                "invalidation": {"condition": "close_above_resistance_by_one_atr", "level": resistance + atr},
                "reference_zone": {"support": support, "resistance": resistance},
            },
        ]
    return [
        {
            **common,
            "scenario": "transition_upward_breakout_condition",
            "trigger": {"condition": "close_above_resistance", "level": resistance},
            "invalidation": {"condition": "close_back_inside_range", "level": resistance},
            "reference_zone": {"support": support, "resistance": resistance},
        },
        {
            **common,
            "scenario": "transition_downward_breakout_condition",
            "trigger": {"condition": "close_below_support", "level": support},
            "invalidation": {"condition": "close_back_inside_range", "level": support},
            "reference_zone": {"support": support, "resistance": resistance},
        },
    ]
