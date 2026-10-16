# SoloSophy — Operating Runbook for scheduled runs (v1 · 2026-10-17)

Every scheduled task reads this file first, then its own prompt file in `ops/prompts/`. Arabic summary for the owner: `ops/CONSTITUTION_LITE_AR.md`.

## 0. Non-negotiables (any breach = stop and do not publish)
1. **IBKR is read-only forever.** Use only: `get_price_snapshot`, `get_price_history`, `search_futures`, `search_contracts`, `get_option_parameters`, `get_option_data`. NEVER call `create_order_instruction`, `delete_order_instruction`, `create_alert`, `update_alert`, `delete_alert`, `set_alert_status`, `create_watchlist`, `edit_watchlist`, `delete_watchlist`, or any account tool.
2. **Price = IBKR `last`** (Last price) with its timestamp. Never settlement. If `top_status` is FROZEN the market is closed → the price is the reference close; say so.
3. **No invented numbers.** Every number in a report comes from (a) an IBKR tool result, (b) `scripts/compute_levels.py` / `scripts/report_kit.py`, or (c) a cited source URL. If something is missing, write that it is missing — never estimate silently.
4. **News rule:** a market-moving fact needs two independent sources or one official source; otherwise tag it `مصدر واحد` (set `single: true`) or put it under `unconfirmed`.
5. **Probabilities:** scenario weights are an *analytical weighting* produced by `Kit.ladder()` (base 16/22/24/22/16, tilt ≤ ±8 per rung, sum 100). The CME engine's statistics are shown in full in the Engine Lab but are labelled uncalibrated.
6. **Execution levels** only via `Kit.setup()` (10% ATR offset before the level, valid tick, crowded round price nudged). No-trade zone first. Entries never inside the NTZ.
7. **Language:** client-facing Arabic, formal and confident; never first person (أنا/أرى/أعتقد/نعتقد). Solo Vision is Egyptian Arabic, confident, also without "أنا". Western digits 0–9. Times in Dubai (UTC+4).
8. **Gate:** `python3 scripts/validate_report.py <file>` must print `0 error(s)` before publishing.

## 1. Repository map
- `docs/` — the public web app (GitHub Pages). Data the app reads: `docs/data/index.json` (archive), `docs/data/reports/<date>/<slot>.json`, `docs/data/engine/<date>.json`, `docs/data/alerts.json`, `docs/data/live.json`, `docs/data/config.json`.
- `data/raw/<date>/` — IBKR captures (snapshots.json, daily/*.json, intraday/*.json). `data/derived/<date>/levels.json` — computed indicators.
- `scripts/` — `ingest_ibkr.py`, `compute_levels.py`, `setups.py`, `report_kit.py`, `validate_report.py`, `engine_refresh.py`, `build_engine_lab.py`. Example full report builder: `scripts/build_report_2026_10_17.py` (read it to see the expected depth and style).
- `ops/contracts.json` — active contracts, ticks, roll rule, watch thresholds. `ops/templates/report_template.py` — start every report from this.
- `engine/` — CME research engine v0.3 (`engine/src`, tests: `cd engine/src && python3 -m pytest -q`), merged raw data `engine/raw/latest`, runs `engine/run_<date>`.

## 2. Data capture (all reports)
Let `D` = today's Dubai date (YYYY-MM-DD). `mkdir -p data/raw/$D/daily data/raw/$D/intraday data/derived/$D`.
1. **Snapshots** — for each asset in `ops/contracts.json` call `get_price_snapshot` with `exchange` set (futures: COMEX/NYMEX; SOXL: omit) and fields `["last","change","prior_close","top_status","future_open_interest","implied_vol_underlying","historical_vol","implied_volatility_percentile","misc_statistics","volume","high","low","open"]` (SOXL: drop `future_open_interest`). Write `data/raw/$D/snapshots.json` in the same shape as `data/raw/2026-10-17/snapshots.json` (keys GC, SI, HG, CL, SOXL; `iv` = `annual_iv`, `hv30` = `historical-vol.annual_pct`, `ivp_52w` = `high_52w` percentile, `oi`, `last`, `status`). SOXL uses `last_rth`/`last_ext` only if both exist; otherwise `last`.
2. **Daily history** — `get_price_history` with `step: "ONE_DAY"`, `outside_rth: true` and `step_count: 1300` for futures (exchange set, `security_type: "FUT"`), `step_count: 1000`, `outside_rth: false`, `security_type: "STK"` for SOXL. These outputs are large, so the tool saves them to a file and prints its path. Then:
   `python3 scripts/ingest_ibkr.py <saved file> GC 462941472 COMEX ONE_DAY 1300 data/raw/$D/daily/gc_daily_long.json` (repeat: si, hg, cl; `soxl ... SMART ONE_DAY 1000 ... --stk`). File names must be `<asset lowercase>_daily_long.json`.
   If an output is small and printed inline instead, write it to a temporary `.json` file first and ingest that file.
3. `python3 scripts/compute_levels.py data/raw/$D/daily data/derived/$D/levels.json data/raw/$D/snapshots.json` — prints every indicator; read them before writing.
4. During open sessions the last daily bar is still forming: say "آخر سعر حتى HH:MM دبي" instead of "إغلاق".

## 3. Research (web) — what to collect
Use WebSearch / WebFetch. Prefer Tier A (official: Fed/H.15, BLS, BEA, EIA, IEA, OPEC, CFTC, CME, WGC, LME, company filings on SEC) then Tier B (Reuters-based pages, Bloomberg-based pages, Kitco, FXStreet with byline, Mining Weekly, SMM, Trading Economics, AP). Paywalled/blocked pages: use another source, never guess the content.
- Since the previous report: macro data (actual vs consensus vs prior), Fed speakers/pricing (FedWatch, Polymarket/Kalshi APIs if useful), yields/DXY, geopolitics (Hormuz, Houthis, Iran, Russia/Ukraine, US politics), oil inventories/OPEC/IEA, metals supply (mines, strikes, LME stocks), China data, semiconductors (earnings, guidance, SOX), central-bank gold, ETF flows.
- Analysts (full reports): at least 3 per asset from different countries when available (US, UK/EU, China, Japan, Korea, Gulf, Russia), each with date + link.
- Calendar for the next 24–48h (snapshots) or week (full/weekly) in Dubai time, with consensus and prior.
- CFTC COT (weekly, Friday 23:30 Dubai): `https://www.cftc.gov/dea/newcot/f_disagg.txt` (managed money, swap dealers, producers).

## 4. Writing the report
1. `cp ops/templates/report_template.py scripts/runs/build_${D}_<slot>.py` and fill every `TODO`. Look at `scripts/build_report_2026_10_17.py` and `docs/data/reports/2026-10-17/weekly.json` for depth, tone and structure.
2. Sections by type:
   - **Snapshot** (`pre_europe`, `us_mid`): header, what_changed (3–6 items), sessions (optional), all 5 assets (where, control points, drivers 3–5, ladder with `days=1`, 2–4 setups, stance), today's events, short Solo Vision, sources.
   - **Full** (`pre_us`, `pre_asia`, `weekly`, full on-demand): everything in the snapshot plus analysts per asset, positioning (COT), macro, geopolitics (confirmed / unconfirmed), events table, market makers (COT, ETF, central banks, options IV from IBKR, prediction markets), conflicts with resolution, methodology, voice chapters. Weekly uses `days=5`.
3. Level choices must come from `levels.json` (pivots, week high/low, SMAs, Bollinger, 1σ range, 60-day high/low) or a clearly cited analyst level (state if it is spot, not futures).
4. Run the builder → it writes `docs/data/reports/$D/<slot>.json` and updates `docs/data/index.json`.
5. `python3 scripts/validate_report.py docs/data/reports/$D/<slot>.json` → fix until `0 error(s)`. Warnings are allowed but read them.

## 5. Engine refresh (weekly report; optional in pre_asia)
Pull GC and SI `ONE_HOUR` (`step_count: 800`) and `THIRTY_MINS` (`step_count: 1340`), `outside_rth: true`; ingest each to `data/raw/$D/intraday/{gc,si}_{hourly,30m}.json`; then
`python3 scripts/engine_refresh.py $D --gc-hourly … --gc-30m … --si-hourly … --si-30m … --gc-daily data/raw/$D/daily/gc_daily_long.json --si-daily data/raw/$D/daily/si_daily_long.json`
and set the report's `engine_ref` to `data/engine/$D.json`. Show everything; never convert engine hit-rates into "probabilities".

## 6. Publish
```
git add docs data scripts/runs engine
git commit -m "SoloSophy <slot> report $D"
git pull --rebase origin main
git push origin HEAD:main
git push origin "$(git subtree split --prefix docs HEAD)":refs/heads/gh-pages --force   # mirror for GitHub Pages
```
Push to **main** directly (this repository is the publication channel; do not open a pull request). If the push is rejected because main moved, pull --rebase again and retry (max 3 times).

## 7. Final message of the run
End with a short Arabic summary for the owner: report type, link `https://sologhub.github.io/SoloSophy-/#report/<id>`, the 5 headline prices, any blocker (missing data, failed validation). No first person.
