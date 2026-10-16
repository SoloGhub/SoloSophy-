from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

import numpy as np
import pandas as pd

from solosophy_engine.backtest import _segment_metrics, directional_signal, validate_directional_rules, walk_forward_validate
from solosophy_engine.events import event_reaction
from solosophy_engine.execution import CostModel, separate_roll_returns, simulate_next_open
from solosophy_engine.indicators import compute_features, wilder_average
from solosophy_engine.ingestion import DataContractError, load_ibkr_history
from solosophy_engine.journal import append_snapshot, verify_journal
from solosophy_engine.levels import confluence_zones, temporal_profile
from solosophy_engine.outcomes import score_outcomes
from solosophy_engine.pipeline import run_pipeline
from solosophy_engine.repository import Repository


def bars(n=800):
    prices = np.arange(n, dtype=float) + 100
    times = pd.date_range('2025-01-01', periods=n, freq='h', tz='UTC')
    return pd.DataFrame({'bar_start_utc': times, 'bar_end_utc': times + pd.Timedelta(hours=1),
                         'open': prices, 'close': prices + .5, 'high': prices + 1, 'low': prices - 1,
                         'volume': np.ones(n) * 100, 'contract_id': 1})


def payload(n=220, step='ONE_DAY'):
    frame = bars(n)
    if step == 'ONE_DAY':
        frame['bar_start_utc'] = pd.date_range('2025-01-01', periods=n, freq='D', tz='UTC')
    return {'captured_at_utc': '2025-12-01T00:00:00Z', 'source': 'synthetic_unit_test_only',
            'request': {'asset': 'GC', 'exchange': 'COMEX', 'contract_id': 1, 'contract_month': '202612', 'step': step},
            'response': {'time': [x.isoformat() for x in frame.bar_start_utc],
                         **{name: frame[name].tolist() for name in ['open', 'high', 'low', 'close', 'volume']}}}


class QualityAuditTests(unittest.TestCase):
    def load(self, data):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'data.json'
            path.write_text(json.dumps(data))
            return load_ibkr_history(path, as_of='2026-09-07T10:00:00Z')

    def test_short_reliable_tail_blocks_daily(self):
        data = payload()
        data['response']['high'][205] = 0
        loaded = self.load(data)
        self.assertEqual(loaded.report['decision'], 'quarantine')
        self.assertIn('insufficient_reliable_analysis_bars', loaded.report['blocking_reasons'])

    def test_timezone_is_not_guessed(self):
        data = payload()
        data['response']['time'][0] = '2025-01-01T00:00:00'
        with self.assertRaises(DataContractError):
            self.load(data)

    def test_contract_scope_is_enforced(self):
        data = payload()
        data['request']['asset'] = 'CL'
        with self.assertRaises(DataContractError):
            self.load(data)

    def test_conflicting_duplicates_fail_closed(self):
        data = payload()
        data['response']['time'][1] = data['response']['time'][0]
        with self.assertRaises(DataContractError):
            self.load(data)

    def test_stale_data_never_live(self):
        report = self.load(payload()).report
        self.assertFalse(report['live_eligible'])
        self.assertIn('last_closed_bar_is_stale', report['live_blocking_reasons'])

    def test_negative_price_is_quarantined(self):
        data = payload()
        for field in ['open', 'high', 'low', 'close']:
            data['response'][field][0] = -1
        self.assertEqual(self.load(data).report['non_finite_ohlc_count'], 1)


class StatisticalAuditTests(unittest.TestCase):
    def test_wilder_uses_sma_seed(self):
        output = wilder_average(pd.Series([1., 2., 3., 4.]), 3)
        self.assertTrue(np.isnan(output[1]))
        self.assertEqual(output[2], 2)
        self.assertAlmostEqual(output[3], 8 / 3)

    def test_previous_bar_pivot_has_no_current_price_dependency(self):
        frame = bars(250)
        first = compute_features(frame)
        frame.loc[249, ['high', 'low', 'close']] *= 2
        second = compute_features(frame)
        self.assertEqual(first.iloc[-1].pivot_previous_bar, second.iloc[-1].pivot_previous_bar)
        self.assertAlmostEqual(first.iloc[-1].classic_r2 - first.iloc[-1].pivot_previous_bar, 2)

    def test_nonoverlapping_sample_count(self):
        segment = pd.DataFrame({'forward_return': [.01] * 120, 'signal': [1] * 120})
        self.assertEqual(_segment_metrics(segment, horizon=4)['active_signals'], 30)

    def test_temporal_tests_do_not_claim_unseen_holdout(self):
        feature = compute_features(bars())
        result = validate_directional_rules(feature, 'hourly', .6)
        self.assertFalse(result['rule_is_frozen_before_holdout'])
        self.assertEqual(result['split_share'], .6)
        self.assertEqual(result['horizons']['24']['purged_development_rows'], 24)

    def test_fold_labels_stay_inside_fold(self):
        feature = compute_features(bars())
        result = walk_forward_validate(feature, directional_signal(feature), 'hourly', 'test')
        folds = result['horizons']['24']['folds']
        for left, right in zip(folds, folds[1:]):
            self.assertLess(pd.Timestamp(left['last_outcome_utc']), pd.Timestamp(right['test_start_utc']))
        self.assertFalse(result['rule_frozen_before_all_holdouts'])

    def test_signal_alignment_survives_shuffled_input(self):
        feature = compute_features(bars())
        shuffled = feature.sample(frac=1, random_state=7)
        result = walk_forward_validate(feature, directional_signal(feature), 'hourly', 'test')
        reordered = walk_forward_validate(shuffled, directional_signal(shuffled), 'hourly', 'test')
        self.assertEqual(result['horizons'], reordered['horizons'])

    def test_levels_and_profile_remain_descriptive(self):
        features = compute_features(bars())
        self.assertFalse(confluence_zones(features)['tolerance_validated'])
        self.assertFalse(temporal_profile(features)['exchange_sessions_classified'])


class OperationalAuditTests(unittest.TestCase):
    def test_repository_is_idempotent_and_update_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            raw = path / 'raw.json'
            raw.write_text(json.dumps(payload()))
            repository = Repository(path / 'data.sqlite3')
            self.assertTrue(repository.ingest(raw)['inserted'])
            self.assertFalse(repository.ingest(raw)['inserted'])
            self.assertEqual(len(repository.inventory()), 1)
            with sqlite3.connect(repository.path) as db, self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE raw_responses SET asset='SI'")

    def test_journal_corruption_and_lock_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'journal.jsonl'
            path.write_text('{bad json}\n')
            self.assertFalse(verify_journal(path)['valid'])
            with self.assertRaises(ValueError):
                append_snapshot(path, {'event_id': 'one'})
            lock = path.with_suffix('.jsonl.lock')
            lock.touch()
            with self.assertRaises(ValueError):
                append_snapshot(path, {'event_id': 'one'})

    def test_outcomes_pending_then_append_once(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            data = bars(10)
            forecast = {'timeframe': 'hourly', 'contract_id': 1,
                        'reference_bar_start_utc': data.iloc[0].bar_start_utc.isoformat(),
                        'reference_bar_end_utc': data.iloc[0].bar_end_utc.isoformat(),
                        'reference_close': 100.5, 'direction': 1, 'horizons_bars': [4], 'step_seconds': 3600}
            append_snapshot(path / 'signals.jsonl', {'signal_id': 'test-only', 'symbol': 'GC',
                            'created_at_utc': data.iloc[0].bar_end_utc.isoformat(), 'forecasts': [forecast]})
            result = score_outcomes(path / 'signals.jsonl', {('GC', 'hourly'): data.iloc[:3]}, path / 'outcomes.jsonl', as_of='2025-01-01T03:00:00Z')
            self.assertEqual(result['pending'], 1)
            result = score_outcomes(path / 'signals.jsonl', {('GC', 'hourly'): data}, path / 'outcomes.jsonl', as_of='2025-01-01T11:00:00Z')
            self.assertEqual(result['appended'], 1)
            repeat = score_outcomes(path / 'signals.jsonl', {('GC', 'hourly'): data}, path / 'outcomes.jsonl', as_of='2025-01-01T11:00:00Z')
            self.assertEqual(repeat['appended'], 0)

    def test_simulation_requires_cost_evidence(self):
        frame = bars(10)
        self.assertEqual(simulate_next_open(frame, pd.Series([1] * 10), 2, None)['status'], 'blocked')
        costs = CostModel(.1, 10, 1, 1, 'unit-test-fixture-not-market-specification', True)
        result = simulate_next_open(frame, pd.Series([1] * 10), 2, costs)
        trade = result['trades'][0]
        self.assertAlmostEqual(trade['net_cash_pnl_one_contract'], trade['gross_cash_pnl_one_contract'] - 4)
        with self.assertRaises(ValueError):
            simulate_next_open(frame, pd.Series([1] * 10), 2, replace(costs, verified=False))

    def test_roll_change_is_not_market_return(self):
        frame = bars(3)
        frame.loc[2, 'contract_id'] = 2
        result = separate_roll_returns(frame)
        self.assertTrue(pd.isna(result.iloc[2].market_return))
        self.assertTrue(result.iloc[2].contract_switch)

    def test_unverified_events_are_blocked(self):
        self.assertEqual(event_reaction(bars(), {})['status'], 'blocked')

    def test_empty_pipeline_reports_blocker(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            result = run_pipeline(path / 'missing', path / 'output')
            self.assertEqual(result['run_status'], 'blocked_no_accepted_data')
            self.assertTrue(result['probabilities_withheld'])


if __name__ == '__main__':
    unittest.main()
