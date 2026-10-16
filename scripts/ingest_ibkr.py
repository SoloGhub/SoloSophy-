#!/usr/bin/env python3
"""Wrap an IBKR get_price_history result into the SoloSophy raw format.
Large tool outputs are auto-saved by Claude Code to a tool-results .txt file (path shown in the tool error);
small ones can be pasted into a .json file first. Either way:
    python3 scripts/ingest_ibkr.py <tool_output_file> <asset> <contract_id> <exchange> <STEP> <step_count> <out.json> [--stk]
Validates array lengths and OHLC sanity, stamps capture time (UTC now).
"""
import json, sys, datetime


def main():
    a = sys.argv[1:]
    stk = '--stk' in a
    a = [x for x in a if x != '--stk']
    src, asset, cid, exch, step, cnt, out = a
    raw = open(src).read().strip()
    try:
        r = json.loads(raw)
    except json.JSONDecodeError:
        r = json.loads(json.loads(raw)[0]['text'])
    if isinstance(r, list):
        r = json.loads(r[0]['text'])
    if r.get('error'):
        sys.exit('IBKR error: ' + str(r['error']))
    n = len(r['time'])
    assert all(len(r[k]) == n for k in ('open', 'high', 'low', 'close', 'volume')), 'array length mismatch'
    bad = [i for i in range(n) if not (r['low'][i] <= min(r['open'][i], r['close'][i]) + 1e-9 and r['high'][i] >= max(r['open'][i], r['close'][i]) - 1e-9)]
    now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    doc = dict(captured_at_utc=now, source='IBKR MCP get_price_history (Last)',
               request=dict(asset=asset, contract_id=int(cid), exchange=exch, contract_month=None if stk else '202612',
                            security_type='STK' if stk else 'FUT', outside_rth=not stk, step=step, step_count=int(cnt)),
               response=r)
    json.dump(doc, open(out, 'w'))
    print(f'{asset} {step}: {n} bars {r["time"][0]} → {r["time"][-1]} last close {r["close"][-1]} · bad OHLC bars: {len(bad)} → {out}')


if __name__ == '__main__':
    main()
