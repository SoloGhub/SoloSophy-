from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pandas as pd

from .journal import append_snapshot, verify_journal


def score_outcomes(journal_path: str | Path, features: dict, output_path: str | Path, *, as_of: str) -> dict:
    """Append realized close-to-close outcomes; never modify the prediction."""
    source = Path(journal_path)
    integrity = verify_journal(source)
    if not integrity['valid']:
        raise ValueError('Prediction journal failed verification')
    status = {'appended': 0, 'pending': 0, 'legacy_unscorable': 0, 'blocked': 0}
    if not source.exists():
        return status
    cutoff = pd.Timestamp(as_of)
    if cutoff.tzinfo is None:
        raise ValueError('as_of requires timezone')
    for line in source.read_text(encoding='utf-8').splitlines():
        record = json.loads(line)
        forecasts = record.get('forecasts')
        if forecasts is None:
            status['legacy_unscorable'] += 1
            continue
        for forecast in forecasts:
            frame = features.get((record['symbol'], forecast['timeframe']))
            if frame is None:
                status['pending'] += 1
                continue
            frame = frame.sort_values('bar_start_utc').reset_index(drop=True)
            if 'contract_id' not in frame or not frame['contract_id'].eq(forecast['contract_id']).all():
                status['blocked'] += 1
                continue
            matches = frame.index[frame.bar_start_utc == pd.Timestamp(forecast['reference_bar_start_utc'])]
            if len(matches) != 1:
                status['blocked'] += 1
                continue
            start = int(matches[0])
            if abs(float(frame.iloc[start]['close']) - forecast['reference_close']) > 1e-9:
                status['blocked'] += 1  # revision of entry data needs explicit reconciliation
                continue
            for horizon in forecast['horizons_bars']:
                end = start + horizon
                if end >= len(frame) or frame.iloc[end]['bar_end_utc'] > cutoff:
                    status['pending'] += 1
                    continue
                # Require labels entirely after decision time and no unclassified gap.
                section = frame.iloc[start:end + 1]
                step = pd.Timedelta(seconds=forecast['step_seconds'])
                if not section.bar_start_utc.diff().dropna().eq(step).all() or frame.iloc[end]['bar_end_utc'] <= pd.Timestamp(record['created_at_utc']):
                    status['blocked'] += 1
                    continue
                exit_close = float(frame.iloc[end]['close'])
                direction = forecast['direction']
                event_id = sha256(f"{record['signal_id']}|{forecast['timeframe']}|{horizon}".encode()).hexdigest()
                gross = exit_close / forecast['reference_close'] - 1
                outcome = {
                    'event_id': event_id, 'prediction_id': record['signal_id'],
                    'symbol': record['symbol'], 'timeframe': forecast['timeframe'],
                    'horizon_bars': horizon, 'created_at_utc': as_of,
                    'outcome_bar_end_utc': frame.iloc[end]['bar_end_utc'].isoformat(),
                    'gross_forward_return': gross, 'signed_forward_return': direction * gross,
                    'direction': direction, 'hit': None if direction == 0 else direction * gross > 0,
                    'costs_included': False, 'execution_simulated': False,
                    'eligible_for_probability_calibration': False,
                    'usage': 'realized_descriptive_observation_not_executable_profit',
                    'reference_before_creation': pd.Timestamp(forecast['reference_bar_end_utc']) < pd.Timestamp(record['created_at_utc']),
                }
                status['appended'] += int(append_snapshot(output_path, outcome)['appended'])
    status['integrity'] = verify_journal(output_path)
    return status
