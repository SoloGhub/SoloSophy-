#!/usr/bin/env python3
"""SoloSophy execution-level helper.
Rules (Constitution D3):
  * every entry / stop / target is offset ~10% of ATR14 *before* the chart level
    (buy entries above support, sell entries below resistance, stops beyond the level,
     targets just before the opposing level);
  * every price is rounded to the contract's valid tick;
  * crowded round prices (multiples of round_unit) are nudged by one tick away from the crowd.
"""
import math

SPEC = {
    'GC':   dict(tick=0.10,   round_unit=0.5,   dec=1),
    'SI':   dict(tick=0.005,  round_unit=0.05,  dec=3),
    'HG':   dict(tick=0.0005, round_unit=0.005, dec=4),
    'CL':   dict(tick=0.01,   round_unit=0.05,  dec=2),
    'SOXL': dict(tick=0.01,   round_unit=0.05,  dec=2),
}


def to_tick(asset, price, nudge):
    """Round to tick; if on a crowded round price, move one tick in `nudge` direction (+1/-1)."""
    s = SPEC[asset]
    t = s['tick']
    v = round(round(price / t) * t, s['dec'])
    q = v / s['round_unit']
    if abs(q - round(q)) < 1e-6:
        v = round(v + nudge * t, s['dec'])
    return v


def build(asset, atr, side, kind, entry_level, stop_level, targets, label, condition, note=''):
    """side: 'long' | 'short'. Levels are raw chart levels; offsets are applied here."""
    off = 0.10 * atr
    if side == 'long':
        entry = to_tick(asset, entry_level + off, +1)            # above support / above breakout level
        stop = to_tick(asset, stop_level - off, -1)              # below the invalidation level
        tps = [to_tick(asset, x - off, -1) for x in targets]     # just before resistance
        risk = entry - stop
        rr = [round((tp - entry) / risk, 2) for tp in tps]
    else:
        entry = to_tick(asset, entry_level - off, -1)            # below resistance / below breakdown level
        stop = to_tick(asset, stop_level + off, +1)              # above the invalidation level
        tps = [to_tick(asset, x + off, +1) for x in targets]     # just before support
        risk = stop - entry
        rr = [round((entry - tp) / risk, 2) for tp in tps]
    d = SPEC[asset]['dec']
    grade = 'preferred' if rr[0] >= 1 and rr[-1] >= 2 else 'acceptable' if rr[-1] >= 1.5 else 'weak'
    grade_ar = {'preferred': 'مفضّل', 'acceptable': 'مقبول', 'weak': 'عائد ضعيف — غير مفضّل'}[grade]
    return dict(side=side, grade=grade, grade_ar=grade_ar, kind=kind, label=label, condition=condition, note=note,
                entry=entry, stop=stop, targets=tps, risk=round(risk, d), rr=rr,
                raw=dict(entry_level=entry_level, stop_level=stop_level, targets=targets,
                         offset=round(off, d + 1)))
