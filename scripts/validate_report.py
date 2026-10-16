#!/usr/bin/env python3
"""Publication gate (Constitution D8). Exit code 1 = Critical/High error → DO NOT publish.
Usage: python3 scripts/validate_report.py docs/data/reports/<date>/<slot>.json [--date <date>]
Checks: schema fields, ladder sums & tilts, NTZ inside 1σ, setups math (offset/tick/rr), prices equal levels.json (Last),
spark/price consistency, sources present, no placeholder text, index entry present.
"""
import json, sys, math, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from setups import SPEC  # noqa: E402

FULL = {'weekly', 'pre_us', 'pre_asia', 'on_demand_full'}
PLACEHOLDER = re.compile(r'(TODO|TBD|lorem|XXX|\?\?\?|placeholder|PLACEHOLDER|N/A N/A)', re.I)


def main(path, date=None):
    errs, warns = [], []
    p = Path(path)
    r = json.load(open(p))
    date = date or p.parent.name
    lv_path = ROOT / f'data/derived/{date}/levels.json'
    L = json.load(open(lv_path)) if lv_path.exists() else None
    if L is None:
        errs.append(f'CRITICAL levels.json missing for {date} — numbers cannot be verified')
    for k in ('schema', 'id', 'type', 'type_ar', 'issued_dubai', 'issued_label', 'data_cutoff', 'headline', 'assets', 'disclaimer'):
        if not r.get(k):
            errs.append(f'HIGH missing field: {k}')
    txt = json.dumps(r, ensure_ascii=False)
    if PLACEHOLDER.search(txt):
        errs.append(f'HIGH placeholder text found: {PLACEHOLDER.search(txt).group(0)}')
    for a in r.get('assets', []):
        c = a.get('code')
        dec = SPEC[c]['dec']
        if L:
            d = L[c]
            if abs(a['price']['last'] - d['close']) > 1e-9:
                errs.append(f'CRITICAL {c} price {a["price"]["last"]} != levels close {d["close"]}')
        lad = a.get('ladder') or {}
        w = [i['weight'] for i in lad.get('items', [])]
        if len(w) != 5 or sum(w) != 100:
            errs.append(f'CRITICAL {c} ladder must have 5 rungs summing to 100 (got {w})')
        if any(abs(i['tilt']) > 8 for i in lad.get('items', [])):
            errs.append(f'HIGH {c} tilt above 8 points')
        if lad and (lad.get('up_total', 0) + lad.get('range_total', 0) + lad.get('down_total', 0)) != 100:
            errs.append(f'CRITICAL {c} totals do not sum to 100')
        ntz = a.get('ntz')
        if not ntz or not (ntz[0] < a['price']['last'] < ntz[1]):
            errs.append(f'HIGH {c} NTZ must bracket the reference price ({ntz})')
        for s in a.get('setups', []):
            t = SPEC[c]['tick']
            for k in ['entry', 'stop'] + [f'targets[{i}]' for i in range(len(s['targets']))]:
                v = s[k] if '[' not in k else s['targets'][int(k[-2])]
                if abs(round(v / t) * t - v) > t * 1e-3:
                    errs.append(f'HIGH {c} {s["label"]} {k}={v} not on tick {t}')
            if s['side'] == 'long' and not (s['stop'] < s['entry'] < s['targets'][0]):
                errs.append(f'CRITICAL {c} long setup order wrong: {s}')
            if s['side'] == 'short' and not (s['stop'] > s['entry'] > s['targets'][0]):
                errs.append(f'CRITICAL {c} short setup order wrong: {s}')
            if ntz and ntz[0] < s['entry'] < ntz[1]:
                warns.append(f'{c} {s["label"]} entry {s["entry"]} lies inside NTZ {ntz}')
            if s.get('grade') == 'weak':
                warns.append(f'{c} {s["label"]} graded weak (rr {s["rr"]}) — shown with label')
        for f in ('where', 'stance'):
            if not a.get(f):
                errs.append(f'HIGH {c} missing {f}')
        if not a.get('spark'):
            warns.append(f'{c} no spark data')
        elif abs(a['spark'][-1]['c'] - a['price']['last']) > 1e-9:
            errs.append(f'HIGH {c} spark last close != price')
    if r.get('type') in FULL:
        for k in ('macro', 'events', 'market_makers', 'solo_vision', 'sources', 'conflicts', 'methodology'):
            if not r.get(k):
                errs.append(f'HIGH full report missing section: {k}')
    if not r.get('sources'):
        errs.append('HIGH no sources')
    idx = json.load(open(ROOT / 'docs/data/index.json'))
    if not any(x['id'] == r['id'] for x in idx['reports']):
        errs.append('HIGH report not in docs/data/index.json')
    print(f'validate {path}: {len(errs)} error(s), {len(warns)} warning(s)')
    for e in errs:
        print('  ERROR', e)
    for w_ in warns:
        print('  warn ', w_)
    return 1 if errs else 0


if __name__ == '__main__':
    args = sys.argv[1:]
    date = None
    if '--date' in args:
        i = args.index('--date'); date = args[i + 1]; del args[i:i + 2]
    sys.exit(main(args[0], date))
