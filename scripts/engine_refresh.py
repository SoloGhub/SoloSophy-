#!/usr/bin/env python3
"""Refresh the CME research engine with newly ingested IBKR bars, run it, and publish the Engine Lab JSON.
Usage:
  python3 scripts/engine_refresh.py <date> [--gc-hourly f] [--gc-30m f] [--si-hourly f] [--si-30m f] [--gc-daily f] [--si-daily f]
Each file is a raw JSON written by scripts/ingest_ibkr.py. Missing ones keep the previous data in engine/raw/latest.
Writes: engine/raw/latest/*.json (merged), engine/run_<date>/ (outputs, without the large parquet/csv folders),
        docs/data/engine/<date>.json (web app Engine Lab).
"""
import json, subprocess, sys, shutil, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'engine/raw/latest'
MAP = {'--gc-hourly': 'gc_hourly_merged.json', '--gc-30m': 'gc_30m_merged.json', '--si-hourly': 'si_hourly_merged.json',
       '--si-30m': 'si_30m_merged.json', '--gc-daily': 'gc_daily_5y.json', '--si-daily': 'si_daily_5y.json'}


def merge(old_path, new_path, replace=False):
    n = json.load(open(new_path))
    if replace or not old_path.exists():
        return n
    o = json.load(open(old_path))
    rows = {}
    for r in (o['response'], n['response']):
        for i, t in enumerate(r['time']):
            rows[t] = (r['open'][i], r['high'][i], r['low'][i], r['close'][i], r['volume'][i])
    ts = sorted(rows)
    resp = dict(n['response'])
    resp['time'] = ts
    for j, k in enumerate(['open', 'high', 'low', 'close', 'volume']):
        resp[k] = [rows[t][j] for t in ts]
    resp['chart_start'] = ts[0]
    out = dict(n)
    out['response'] = resp
    out['request'] = dict(n['request'], step_count=len(ts))
    return out


def main():
    args = sys.argv[1:]
    date = args.pop(0)
    pairs = dict(zip(args[::2], args[1::2]))
    latest_capture = None
    for flag, name in MAP.items():
        if flag in pairs:
            doc = merge(RAW / name, Path(pairs[flag]), replace=name.endswith('daily_5y.json'))
            json.dump(doc, open(RAW / name, 'w'))
            latest_capture = max(latest_capture or '', doc['captured_at_utc'])
            print('updated', name, len(doc['response']['time']), 'bars →', doc['response']['time'][-1])
    # the engine refuses capture times in the future and wants one consistent capture stamp
    stamp = latest_capture or datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    for f in RAW.glob('*.json'):
        d = json.load(open(f))
        if d.get('captured_at_utc', '') > stamp:
            d['captured_at_utc'] = stamp
            json.dump(d, open(f, 'w'))
    out = ROOT / f'engine/run_{date}'
    if out.exists():
        shutil.rmtree(out)
    subprocess.run([sys.executable, 'scripts/run_pipeline.py', '--raw-dir', str(RAW), '--output-dir', str(out)],
                   cwd=ROOT / 'engine/src', check=True)
    for big in ('curated', 'features', 'market_archive.sqlite3'):
        p = out / big
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()
    (ROOT / 'docs/data/engine').mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, 'scripts/build_engine_lab.py', str(out / 'engine_output.json'), str(out / 'coverage_matrix.json'),
                    str(ROOT / f'docs/data/engine/{date}.json')], cwd=ROOT, check=True)
    print('engine_ref = data/engine/%s.json' % date)


if __name__ == '__main__':
    main()
