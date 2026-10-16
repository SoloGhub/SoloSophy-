from __future__ import annotations

import numpy as np
import pandas as pd


def wilder_average(series: pd.Series, period: int) -> pd.Series:
    """SMA seed followed by Wilder recursion; restart after missing input."""
    output = pd.Series(np.nan, index=series.index, dtype=float)
    seed: list[float] = []
    previous = None
    for index, value in series.items():
        if pd.isna(value):
            seed, previous = [], None
            continue
        if previous is None:
            seed.append(float(value))
            if len(seed) < period:
                continue
            previous = sum(seed) / period
        else:
            previous = (previous * (period - 1) + float(value)) / period
        output.loc[index] = previous
    return output


def true_range(frame: pd.DataFrame) -> pd.Series:
    previous_close = frame["close"].shift(1)
    parts = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous_close).abs(),
            (frame["low"] - previous_close).abs(),
        ],
        axis=1,
    )
    return parts.max(axis=1)


def rsi_wilder(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    average_gain = wilder_average(gain, period)
    average_loss = wilder_average(loss, period)
    relative_strength = average_gain / average_loss.replace(0, np.nan)
    result = 100 - (100 / (1 + relative_strength))
    result = result.mask((average_loss == 0) & (average_gain > 0), 100.0)
    result = result.mask((average_loss == 0) & (average_gain == 0), 50.0)
    return result


def adx_wilder(frame: pd.DataFrame, period: int = 14) -> tuple[pd.Series, pd.Series, pd.Series]:
    upward = frame["high"].diff()
    downward = -frame["low"].diff()
    plus_dm = upward.where((upward > downward) & (upward > 0), 0.0)
    minus_dm = downward.where((downward > upward) & (downward > 0), 0.0)
    atr = wilder_average(true_range(frame), period).replace(0, np.nan)
    plus_di = 100 * wilder_average(plus_dm, period) / atr
    minus_di = 100 * wilder_average(minus_dm, period) / atr
    denominator = (plus_di + minus_di).replace(0, np.nan)
    dx = (100 * (plus_di - minus_di).abs() / denominator).mask((plus_di + minus_di) == 0, 0.0)
    adx = wilder_average(dx, period)
    return adx, plus_di, minus_di


def compute_features(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy().sort_values("bar_start_utc").reset_index(drop=True)
    result["simple_return"] = result["close"].pct_change(fill_method=None)
    result["log_return"] = np.log(result["close"] / result["close"].shift(1))
    result["true_range"] = true_range(result)
    result["atr_14"] = wilder_average(result["true_range"], 14)
    for window in (5, 10, 20, 50, 100, 200):
        result[f"sma_{window}"] = result["close"].rolling(window, min_periods=window).mean()
        result[f'ema_{window}'] = result['close'].ewm(span=window, adjust=False, min_periods=window).mean()
    result["ema_12"] = result["close"].ewm(span=12, adjust=False, min_periods=12).mean()
    result["ema_26"] = result["close"].ewm(span=26, adjust=False, min_periods=26).mean()
    result["rsi_14"] = rsi_wilder(result["close"], 14)
    result["macd"] = result["ema_12"] - result["ema_26"]
    result["macd_signal_9"] = result["macd"].ewm(span=9, adjust=False, min_periods=9).mean()
    result["macd_histogram"] = result["macd"] - result["macd_signal_9"]
    result['macd_histogram_change'] = result['macd_histogram'].diff()
    result['momentum_10'] = result['close'].pct_change(10, fill_method=None)
    result['atr_ratio_50'] = result['atr_14'] / result['atr_14'].shift(1).rolling(50, min_periods=50).mean().replace(0, np.nan)
    result['volatility_high_threshold'] = result['atr_14'].shift(1).rolling(100, min_periods=100).quantile(.9)
    result['volatility_low_threshold'] = result['atr_14'].shift(1).rolling(100, min_periods=100).quantile(.1)
    result["rolling_std_20"] = result["log_return"].rolling(20, min_periods=20).std(ddof=1)
    rolling_mean = result["close"].rolling(20, min_periods=20).mean()
    rolling_std_price = result["close"].rolling(20, min_periods=20).std(ddof=1)
    result["zscore_20"] = (result["close"] - rolling_mean) / rolling_std_price.replace(0, np.nan)
    result["support_20"] = result["low"].shift(1).rolling(20, min_periods=20).min()
    result["resistance_20"] = result["high"].shift(1).rolling(20, min_periods=20).max()
    result["support_distance_atr"] = (result["close"] - result["support_20"]) / result["atr_14"]
    result["resistance_distance_atr"] = (result["resistance_20"] - result["close"]) / result["atr_14"]
    adx, plus_di, minus_di = adx_wilder(result, 14)
    result["adx_14"] = adx
    result["plus_di_14"] = plus_di
    result["minus_di_14"] = minus_di
    result['volume'] = result['volume'].where(np.isfinite(result['volume']) & (result['volume'] >= 0))
    result["volume_sma_20"] = result["volume"].shift(1).rolling(20, min_periods=20).mean()
    result["volume_ratio_20"] = result["volume"] / result["volume_sma_20"].replace(0, np.nan)
    # Per-timeframe previous CLOSED bar, not an exchange-session pivot.
    prev = result[['high', 'low', 'close']].shift(1)
    pivot = prev.mean(axis=1)
    span = prev['high'] - prev['low']
    result['pivot_previous_bar'] = pivot
    result['classic_r1'] = 2 * pivot - prev['low']
    result['classic_s1'] = 2 * pivot - prev['high']
    result['classic_r2'], result['classic_s2'] = pivot + span, pivot - span
    result['classic_r3'] = prev['high'] + 2 * (pivot - prev['low'])
    result['classic_s3'] = prev['low'] - 2 * (prev['high'] - pivot)
    for number, ratio in enumerate((.382, .618, 1.0), start=1):
        result[f'fib_r{number}'] = pivot + ratio * span
        result[f'fib_s{number}'] = pivot - ratio * span
    return result
