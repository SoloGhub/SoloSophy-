from __future__ import annotations

from urllib.parse import urlparse
import pandas as pd


def event_reaction(bars: pd.DataFrame, event: dict, window_minutes: int = 60) -> dict:
    """Observed price change around a verified release; not causal attribution."""
    required = {'event_id', 'release_at_utc', 'actual', 'prior', 'consensus', 'sources', 'verified'}
    if not required.issubset(event) or not event.get('verified'):
        return {'status': 'blocked', 'reason': 'verified_event_record_missing'}
    sources = event['sources']
    domains = {urlparse(s.get('url', '')).hostname for s in sources if s.get('verified') and s.get('published_at_utc')}
    domains.discard(None)
    if len(domains) < 2:
        return {'status': 'blocked', 'reason': 'two_independent_confirmed_sources_required'}
    release = pd.Timestamp(event['release_at_utc'])
    if release.tzinfo is None or window_minutes <= 0:
        raise ValueError('Timezone-aware release and positive window required')
    frame = bars.sort_values('bar_end_utc')
    before = frame.loc[frame.bar_end_utc <= release]
    # Only use bars whose endpoints are known, not an intrabar fabricated price.
    after = frame.loc[(frame.bar_start_utc >= release) & (frame.bar_end_utc <= release + pd.Timedelta(minutes=window_minutes))]
    if before.empty or after.empty:
        return {'status': 'blocked', 'reason': 'event_window_not_covered_at_bar_resolution'}
    start, end = before.iloc[-1], after.iloc[-1]
    if start['contract_id'] != end['contract_id']:
        return {'status': 'blocked', 'reason': 'contract_roll_crosses_event_window'}
    section = frame.loc[(frame.bar_end_utc > start['bar_end_utc']) & (frame.bar_end_utc <= end['bar_end_utc'])]
    if (section.contract_id != start['contract_id']).any():
        return {'status': 'blocked', 'reason': 'contract_roll_crosses_event_window'}
    price_return = float(end['close']) / float(start['close']) - 1
    return {'status': 'descriptive_observed_reaction', 'event_id': event['event_id'],
            'release_at_utc': release.isoformat(), 'before_bar_end_utc': start['bar_end_utc'].isoformat(),
            'after_bar_end_utc': end['bar_end_utc'].isoformat(), 'observed_return': price_return,
            'actual': event['actual'], 'prior': event['prior'], 'consensus': event['consensus'],
            'surprise': None if event['consensus'] is None else event['actual'] - event['consensus'],
            'causality_established': False, 'calendar_verified': False, 'probability': None}
