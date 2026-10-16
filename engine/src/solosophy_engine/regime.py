from __future__ import annotations

from typing import Any

import pandas as pd


RULESET_VERSION = "v0.3-audited-research"


def classify_latest(features: pd.DataFrame) -> dict[str, Any]:
    if features.empty:
        return {"state": "NO_ANALYSIS", "reason": "empty_feature_set"}
    row = features.iloc[-1]
    required = ("close", "ema_12", "ema_26", "sma_50", "adx_14", "plus_di_14", "minus_di_14")
    if any(pd.isna(row.get(key)) for key in required):
        return {"state": "NO_ANALYSIS", "reason": "indicator_warmup_incomplete"}

    close = float(row["close"])
    ema_fast = float(row["ema_12"])
    ema_slow = float(row["ema_26"])
    sma_50 = float(row["sma_50"])
    adx = float(row["adx_14"])
    plus_di = float(row["plus_di_14"])
    minus_di = float(row["minus_di_14"])

    upward = ema_fast > ema_slow and close > sma_50 and plus_di > minus_di
    downward = ema_fast < ema_slow and close < sma_50 and minus_di > plus_di
    if adx >= 25 and upward:
        state = "trend_up_strong"
    elif adx >= 25 and downward:
        state = "trend_down_strong"
    elif adx < 20:
        state = "range_or_low_trend_strength"
    elif upward:
        state = "trend_up_weak"
    elif downward:
        state = "trend_down_weak"
    else:
        state = "unclear_transition"

    volatility_state = 'insufficient_history'
    atr = row.get('atr_14')
    if pd.notna(row.get('volatility_high_threshold')) and pd.notna(atr):
        if atr > row['volatility_high_threshold']:
            volatility_state = 'high_volatility'
        elif atr < row['volatility_low_threshold']:
            volatility_state = 'compression'
        else:
            volatility_state = 'normal_relative_to_sample'

    return {
        "state": state,
        "volatility_state": volatility_state,
        "thresholds_validated": False,
        "directional_state_is_descriptive": True,
        "ruleset_version": RULESET_VERSION,
        "validated": False,
        "probability_withheld": True,
        "data_cutoff_utc": row["bar_start_utc"].isoformat(),
        "observations": {
            "close": close,
            "ema_12": ema_fast,
            "ema_26": ema_slow,
            "sma_50": sma_50,
            "sma_200": None if pd.isna(row.get("sma_200")) else float(row["sma_200"]),
            "rsi_14": None if pd.isna(row.get("rsi_14")) else float(row["rsi_14"]),
            "adx_14": adx,
            "plus_di_14": plus_di,
            "minus_di_14": minus_di,
            "atr_14": None if pd.isna(row.get("atr_14")) else float(row["atr_14"]),
            "support_20": None if pd.isna(row.get("support_20")) else float(row["support_20"]),
            "resistance_20": None if pd.isna(row.get("resistance_20")) else float(row["resistance_20"]),
            "zscore_20": None if pd.isna(row.get("zscore_20")) else float(row["zscore_20"]),
        },
    }
