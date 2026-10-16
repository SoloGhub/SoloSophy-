from __future__ import annotations

from math import sqrt
from statistics import NormalDist
from typing import Any

import numpy as np
import pandas as pd


HORIZONS = {
    "daily": (1, 5),
    "hourly": (1, 2, 4, 24),
    "thirty_minute": (1, 2, 4, 8, 16),
}

MINIMUM_ACTIVE_SIGNALS = 100
WALK_FORWARD_FOLDS = 4
SCREEN_Z = NormalDist().inv_cdf(1 - 0.05 / (2 * 88))


def directional_signal(features: pd.DataFrame) -> pd.Series:
    required = ("ema_12", "ema_26", "sma_50", "plus_di_14", "minus_di_14")
    missing = [column for column in required if column not in features]
    if missing:
        raise ValueError(f"Missing signal features: {missing}")
    up = (
        (features["ema_12"] > features["ema_26"])
        & (features["close"] > features["sma_50"])
        & (features["plus_di_14"] > features["minus_di_14"])
    )
    down = (
        (features["ema_12"] < features["ema_26"])
        & (features["close"] < features["sma_50"])
        & (features["minus_di_14"] > features["plus_di_14"])
    )
    return pd.Series(np.select([up, down], [1, -1], default=0), index=features.index, dtype="int8")


def mean_reversion_signal(features: pd.DataFrame) -> pd.Series:
    required = ("zscore_20", "rsi_14")
    missing = [column for column in required if column not in features]
    if missing:
        raise ValueError(f"Missing mean-reversion features: {missing}")
    long_reversion = (features["zscore_20"] <= -2.0) & (features["rsi_14"] < 35.0)
    short_reversion = (features["zscore_20"] >= 2.0) & (features["rsi_14"] > 65.0)
    return pd.Series(
        np.select([long_reversion, short_reversion], [1, -1], default=0),
        index=features.index,
        dtype="int8",
    )


def breakout_signal(features: pd.DataFrame) -> pd.Series:
    required = ("resistance_20", "support_20", "adx_14")
    missing = [column for column in required if column not in features]
    if missing:
        raise ValueError(f"Missing breakout features: {missing}")
    upward_breakout = (features["close"] > features["resistance_20"]) & (features["adx_14"] >= 20.0)
    downward_breakout = (features["close"] < features["support_20"]) & (features["adx_14"] >= 20.0)
    return pd.Series(
        np.select([upward_breakout, downward_breakout], [1, -1], default=0),
        index=features.index,
        dtype="int8",
    )


def regime_conditioned_signal(features: pd.DataFrame) -> pd.Series:
    """Route fixed baseline rules by contemporaneous market state.

    Thresholds are research baselines, frozen before evaluation, and are not
    presented as optimized or validated trading parameters.
    """
    required = ("adx_14",)
    missing = [column for column in required if column not in features]
    if missing:
        raise ValueError(f"Missing regime features: {missing}")
    trend = directional_signal(features)
    reversion = mean_reversion_signal(features)
    breakout = breakout_signal(features)
    strong_trend = features["adx_14"] >= 25.0
    range_state = features["adx_14"] < 20.0
    transition = ~(strong_trend | range_state)
    routed = np.select(
        [strong_trend, range_state, transition],
        [trend, reversion, breakout],
        default=0,
    )
    return pd.Series(routed, index=features.index, dtype="int8")


def _wilson_interval(successes: int, sample: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if sample == 0:
        return None, None
    p = successes / sample
    denominator = 1 + z * z / sample
    centre = (p + z * z / (2 * sample)) / denominator
    margin = z * sqrt((p * (1 - p) + z * z / (4 * sample)) / sample) / denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)


def _segment_metrics(segment: pd.DataFrame, horizon: int = 1) -> dict[str, Any]:
    # Fixed-grid sampling removes overlapping labels within each partition.
    segment = segment.iloc[::horizon]
    usable = segment.dropna(subset=["forward_return"]).copy()
    active = usable.loc[usable["signal"] != 0].copy()
    if active.empty:
        return {
            "eligible_bars": int(len(usable)),
            "active_signals": 0,
            "signal_coverage": 0.0 if len(usable) else None,
            "directional_hit_rate": None,
            "hit_rate_wilson_low": None,
            "hit_rate_wilson_high": None,
            "average_signed_forward_return": None,
            "median_signed_forward_return": None,
            "edge_status": "insufficient_active_signals",
        }
    signed = active["signal"] * active["forward_return"]
    successes = int((signed > 0).sum())
    low, high = _wilson_interval(successes, len(active), z=SCREEN_Z)
    average_signed = float(signed.mean())
    if len(active) < MINIMUM_ACTIVE_SIGNALS:
        edge_status = "insufficient_active_signals"
    elif low is not None and low > 0.50 and average_signed > 0:
        edge_status = "positive_statistical_screen_only"
    elif high is not None and high < 0.50 and average_signed < 0:
        edge_status = "negative_statistical_screen_only"
    else:
        edge_status = "edge_not_established"
    return {
        "eligible_bars": int(len(usable)),
        "active_signals": int(len(active)),
        "signal_coverage": float(len(active) / len(usable)) if len(usable) else None,
        "directional_hit_rate": float(successes / len(active)),
        "hit_rate_wilson_low": low,
        "hit_rate_wilson_high": high,
        "average_signed_forward_return": average_signed,
        "median_signed_forward_return": float(signed.median()),
        "edge_status": edge_status,
        "label_spacing_bars": horizon,
        "interval_caveat": 'approximate_Wilson_Bonferroni_88_serial_dependence_unmodeled',
    }


def _walk_forward_horizon(
    ordered: pd.DataFrame,
    signal: pd.Series,
    horizon: int,
    folds: int = WALK_FORWARD_FOLDS,
) -> dict[str, Any]:
    """Run anchored sequential folds and purge train labels crossing tests."""
    test = ordered[["bar_start_utc", "close"]].copy()
    test["signal"] = signal.reset_index(drop=True)
    test["forward_return"] = test["close"].shift(-horizon) / test["close"] - 1
    n = len(test)
    initial_train = max(200, int(n * 0.40))
    remaining = max(0, n - initial_train)
    fold_size = remaining // folds if folds else 0
    fold_results: list[dict[str, Any]] = []
    pooled: list[pd.DataFrame] = []
    if fold_size <= 0:
        return {
            "horizon_bars": horizon,
            "status": "insufficient_bars_for_walk_forward",
            "purge_bars": horizon,
            "folds": [],
            "pooled_holdout": _segment_metrics(test.iloc[0:0]),
            "stable_positive_fold_share": None,
            "stable_positive_edge": False,
            "stable_positive_screen": False,
        }
    for fold_index in range(folds):
        test_start = initial_train + fold_index * fold_size
        test_end = n if fold_index == folds - 1 else test_start + fold_size
        purged_train_end = max(0, test_start - horizon)
        train = test.iloc[:purged_train_end]
        # No holdout outcome may touch the next fold or exit the dataset.
        holdout = test.iloc[test_start:max(test_start, test_end - horizon)]
        metrics = _segment_metrics(holdout, horizon)
        pooled.append(holdout.iloc[::horizon])
        fold_results.append(
            {
                "fold": fold_index + 1,
                "train_start_utc": train["bar_start_utc"].min().isoformat() if len(train) else None,
                "train_end_utc": train["bar_start_utc"].max().isoformat() if len(train) else None,
                "test_start_utc": holdout["bar_start_utc"].min().isoformat() if len(holdout) else None,
                "test_end_utc": holdout["bar_start_utc"].max().isoformat() if len(holdout) else None,
                "purged_training_rows": min(horizon, test_start),
                "purged_holdout_tail_rows": min(horizon, test_end - test_start),
                "last_outcome_utc": test.iloc[test_end - 1]['bar_start_utc'].isoformat(),
                "holdout": metrics,
            }
        )
    pooled_metrics = _segment_metrics(pd.concat(pooled, ignore_index=True))
    evaluable_folds = [
        row for row in fold_results
        if row["holdout"]["active_signals"] > 0
    ]
    positive_folds = sum(
        row["holdout"].get("edge_status") == "positive_statistical_screen_only"
        for row in evaluable_folds
    )
    stable_share = positive_folds / folds
    stable_edge = (
        pooled_metrics.get("edge_status") == "positive_statistical_screen_only"
        and stable_share is not None
        and stable_share >= 0.75
    )
    return {
        "horizon_bars": horizon,
        "status": "walk_forward_complete",
        "method": "fixed_rule_temporal_folds_no_parameter_refitting",
        "purge_bars": horizon,
        "folds": fold_results,
        "pooled_holdout": pooled_metrics,
        "stable_positive_fold_share": stable_share,
        "stable_positive_screen": stable_edge,
        "stable_positive_edge": False,
    }


def walk_forward_validate(
    features: pd.DataFrame,
    signal: pd.Series,
    timeframe: str,
    rule_name: str,
    folds: int = WALK_FORWARD_FOLDS,
) -> dict[str, Any]:
    if timeframe not in HORIZONS:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    if folds < 2:
        raise ValueError("folds must be at least two")
    if len(signal) != len(features):
        raise ValueError('Signal length mismatch')
    ordered = features.copy()
    ordered['_signal'] = signal.to_numpy()
    ordered = ordered.sort_values('bar_start_utc').reset_index(drop=True)
    aligned_signal = ordered.pop('_signal')
    results = {
        str(horizon): _walk_forward_horizon(ordered, aligned_signal, horizon, folds)
        for horizon in HORIZONS[timeframe]
    }
    stable_horizons = [
        key for key, result in results.items() if result.get("stable_positive_edge")
    ]
    # Probability claims remain blocked until costs and calibration are tested,
    # even when a research edge candidate survives this gate.
    return {
        "status": "walk_forward_validation_complete",
        "rule_name": rule_name,
        "timeframe": timeframe,
        "fold_count": folds,
        "rule_frozen_before_all_holdouts": False,
        "validation_kind": 'retrospective_reused_history_not_untouched_out_of_sample',
        "parameter_training_performed": False,
        "probability_model_fitted": False,
        "label_leakage_control": "purged_by_forward_horizon",
        "transaction_costs_included": False,
        "trade_execution_simulated": False,
        "stable_edge_horizons": stable_horizons,
        "research_edge_candidate": bool(stable_horizons),
        "probability_calibration_permitted": False,
        "calibration_blockers": [
            "transaction_costs_not_included",
            "execution_not_simulated",
            "prospective_shadow_sample_not_accumulated",
            "history_inspected_in_prior_development",
            "source_calendar_and_series_construction_unverified",
        ],
        "horizons": results,
    }


def _validate_signal(
    features: pd.DataFrame,
    signal: pd.Series,
    timeframe: str,
    rule_name: str,
    split_share: float,
) -> dict[str, Any]:
    if timeframe not in HORIZONS:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    if not 0.5 <= split_share < 1:
        raise ValueError("split_share must be between 0.5 and 1")
    ordered = features.copy()
    ordered['signal'] = signal.to_numpy()
    ordered = ordered.sort_values('bar_start_utc').reset_index(drop=True)
    split_index = max(1, min(len(ordered) - 1, int(len(ordered) * split_share)))
    split_time = ordered.iloc[split_index]["bar_start_utc"] if len(ordered) > 1 else None
    results: dict[str, Any] = {}
    for horizon in HORIZONS[timeframe]:
        test = ordered[["bar_start_utc", "close", "signal"]].copy()
        test["forward_return"] = test["close"].shift(-horizon) / test["close"] - 1
        test["segment"] = np.where(test.index < split_index, "development", "holdout")
        results[str(horizon)] = {
            "horizon_bars": horizon,
            "development": _segment_metrics(test.iloc[:max(0, split_index - horizon)], horizon),
            "holdout": _segment_metrics(test.iloc[split_index:], horizon),
            "purged_development_rows": min(split_index, horizon),
        }
    positive_holdout = any(
        result["holdout"].get("edge_status") == "positive_statistical_screen_only"
        for result in results.values()
    )
    negative_holdout = any(
        result["holdout"].get("edge_status") == "negative_statistical_screen_only"
        for result in results.values()
    )
    return {
        "status": "descriptive_validation_only",
        "rule_name": rule_name,
        "timeframe": timeframe,
        "rule_is_frozen_before_holdout": False,
        "validation_kind": 'retrospective_reused_history',
        "split_method": "chronological_with_purged_development_tail",
        "split_share": split_share,
        "split_time_utc": split_time.isoformat() if split_time is not None else None,
        "transaction_costs_included": False,
        "trade_execution_simulated": False,
        "probability_calibration_permitted": False,
        "current_ruleset_decision": (
            "candidate_for_further_validation"
            if positive_holdout
            else "reject_for_probability_calibration"
        ),
        "negative_edge_detected_in_holdout": negative_holdout,
        "horizons": results,
    }


def validate_directional_rules(features: pd.DataFrame, timeframe: str, split_share: float = 0.70) -> dict[str, Any]:
    ordered = features.sort_values("bar_start_utc").reset_index(drop=True).copy()
    return _validate_signal(
        ordered,
        directional_signal(ordered),
        timeframe,
        "trend_following_baseline",
        split_share,
    )


def validate_rule_candidates(features: pd.DataFrame, timeframe: str, split_share: float = 0.70) -> dict[str, Any]:
    ordered = features.sort_values("bar_start_utc").reset_index(drop=True).copy()
    candidates = {
        "trend_following_baseline": directional_signal(ordered),
        "mean_reversion_baseline": mean_reversion_signal(ordered),
        "breakout_baseline": breakout_signal(ordered),
        "regime_conditioned_baseline": regime_conditioned_signal(ordered),
    }
    reports = {
        name: _validate_signal(ordered, signal, timeframe, name, split_share)
        for name, signal in candidates.items()
    }
    survivors = [
        name
        for name, report in reports.items()
        if report["current_ruleset_decision"] == "candidate_for_further_validation"
    ]
    return {
        "status": "candidate_comparison_complete",
        "timeframe": timeframe,
        "survivors": survivors,
        "probability_calibration_permitted": False,
        "candidate_reports": reports,
        "regime_conditioned_walk_forward": walk_forward_validate(
            ordered,
            candidates["regime_conditioned_baseline"],
            timeframe,
            "regime_conditioned_baseline",
        ),
    }
