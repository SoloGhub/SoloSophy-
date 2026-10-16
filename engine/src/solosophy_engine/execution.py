from __future__ import annotations

from dataclasses import asdict, dataclass
import math

import pandas as pd


@dataclass(frozen=True)
class CostModel:
    tick_size: float
    value_per_price_point: float
    commission_per_side: float
    slippage_ticks_per_side: float
    source_reference: str
    verified: bool

    def validate(self):
        values = (self.tick_size, self.value_per_price_point, self.commission_per_side, self.slippage_ticks_per_side)
        if not all(math.isfinite(x) for x in values) or min(values[:2]) <= 0 or min(values[2:]) < 0:
            raise ValueError('Invalid cost model')
        if not self.verified or not self.source_reference.strip():
            raise ValueError('Cost model requires verified source evidence')


def simulate_next_open(features: pd.DataFrame, signal: pd.Series, horizon: int, costs: CostModel | None) -> dict:
    """Fixed-horizon, single-contract simulation. No real orders are possible."""
    if costs is None:
        return {'status': 'blocked', 'reason': 'verified_contract_specs_and_costs_missing', 'trades': []}
    costs.validate()
    if horizon < 1 or len(features) != len(signal):
        raise ValueError('Invalid horizon or signal length')
    required = {'open', 'close', 'bar_start_utc', 'bar_end_utc', 'contract_id'}
    if not required.issubset(features.columns):
        raise ValueError('Missing execution input fields')
    frame = features.copy()
    frame['direction'] = signal.to_numpy()
    frame = frame.sort_values('bar_start_utc').reset_index(drop=True)
    trades, i, blocked_windows = [], 0, 0
    while i + horizon < len(frame):
        direction = int(frame.iloc[i]['direction'])
        if direction not in (-1, 0, 1):
            raise ValueError('Direction must be minus one, zero, or one')
        if direction == 0:
            i += 1
            continue
        entry, end = i + 1, i + horizon
        window = frame.iloc[i:end + 1]
        uninterrupted = (window.bar_start_utc.iloc[1:].to_numpy() == window.bar_end_utc.iloc[:-1].to_numpy()).all()
        if window.contract_id.nunique() != 1 or not uninterrupted:
            blocked_windows += 1
            i += 1
            continue
        slip = costs.slippage_ticks_per_side * costs.tick_size
        entry_price = float(frame.iloc[entry]['open']) + direction * slip
        exit_price = float(frame.iloc[end]['close']) - direction * slip
        if not all(math.isfinite(x) and x > 0 for x in (entry_price, exit_price)):
            raise ValueError('Invalid execution prices')
        gross = direction * (float(frame.iloc[end]['close']) - float(frame.iloc[entry]['open'])) * costs.value_per_price_point
        net = direction * (exit_price - entry_price) * costs.value_per_price_point - 2 * costs.commission_per_side
        trades.append({'signal_bar': i, 'entry_bar': entry, 'exit_bar': end,
                       'direction': direction, 'entry_price': entry_price, 'exit_price': exit_price,
                       'gross_cash_pnl_one_contract': gross, 'net_cash_pnl_one_contract': net})
        i = end + 1
    return {'status': 'simulation_only', 'cost_model': asdict(costs), 'trades': trades,
            'unclassified_or_roll_windows_blocked': blocked_windows,
            'net_cash_pnl_one_contract': sum(t['net_cash_pnl_one_contract'] for t in trades),
            'probability_calibration_permitted': False}


def separate_roll_returns(bars: pd.DataFrame) -> pd.DataFrame:
    """Mask contract-boundary returns; never treat roll basis as market return."""
    if not {'contract_id', 'bar_start_utc', 'close'}.issubset(bars.columns):
        raise ValueError('Roll separation requires contract identity')
    result = bars.sort_values('bar_start_utc').reset_index(drop=True).copy()
    if result.bar_start_utc.duplicated().any():
        raise ValueError('Choose an explicit contract per timestamp before roll separation')
    result['contract_switch'] = result.contract_id.ne(result.contract_id.shift()) & result.index.to_series().gt(0)
    result['unadjusted_return'] = result.close.pct_change(fill_method=None)
    result['market_return'] = result.unadjusted_return.mask(result.contract_switch)
    result['contract_switch_price_gap'] = result.close.diff().where(result.contract_switch)
    result['roll_basis_verified'] = False
    return result
