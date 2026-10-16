from __future__ import annotations

import math
import pandas as pd


def confluence_zones(features: pd.DataFrame) -> dict:
    """Inspectable candidate zones; evidence count is NOT a confidence score."""
    if features.empty:
        return {'status': 'unavailable', 'zones': []}
    row = features.iloc[-1]
    atr = row.get('atr_14')
    if atr is None or not math.isfinite(atr) or atr <= 0:
        return {'status': 'unavailable', 'zones': []}
    tolerance = float(atr) * .25
    names = ['support_20', 'resistance_20', 'sma_20', 'sma_50', 'sma_200', 'ema_26', 'pivot_previous_bar']
    names += [f'{family}_{side}{i}' for family in ('classic', 'fib') for side in ('s', 'r') for i in (1, 2, 3)]
    candidates = sorted((float(row[k]), k) for k in names if pd.notna(row.get(k)))
    groups: list[list[tuple[float, str]]] = []
    for level in candidates:
        if not groups or level[0] - groups[-1][0][0] > 2 * tolerance:
            groups.append([level])
        else:
            groups[-1].append(level)
    return {
        'status': 'descriptive_only', 'tolerance_atr': .25,
        'tolerance_validated': False, 'tick_and_spread_adjusted': False,
        'pivot_basis': 'previous_closed_timeframe_bar_not_session',
        'zones': [
            {'low': min(p for p, _ in group) - tolerance,
             'high': max(p for p, _ in group) + tolerance,
             'centre': sum(p for p, _ in group) / len(group),
             'evidence_count': len(group), 'evidence': [k for _, k in group],
             'probability': None}
            for group in groups
        ],
    }


def temporal_profile(features: pd.DataFrame) -> dict:
    if features.empty:
        return {'status': 'unavailable'}
    data = features[['bar_start_utc', 'open', 'close']].copy()
    # Own-bar return avoids misattributing multi-day gap returns to an hour.
    data['return'] = data['close'] / data['open'] - 1
    data['hour_utc'] = data['bar_start_utc'].dt.hour
    data['weekday_utc'] = data['bar_start_utc'].dt.dayofweek
    def profile(key):
        return data.groupby(key)['return'].agg(sample='count', mean_return='mean', median_return='median').reset_index().to_dict('records')
    return {'status': 'descriptive_not_forecast', 'timezone': 'UTC',
            'exchange_sessions_classified': False, 'by_hour': profile('hour_utc'), 'by_weekday': profile('weekday_utc')}
