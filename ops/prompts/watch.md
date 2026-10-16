# Hourly price watch (Mon–Fri 10:07–23:07, Tue–Sat 00:07–01:07 Dubai)
Goal: cheap and fast. Detect abnormal moves, keep `docs/data/live.json` fresh, and serve on-demand requests queued on GitHub.
1. Read `ops/contracts.json` (thresholds) — do NOT read the full RUNBOOK unless a breach or a queued request needs a report.
2. For each asset call `get_price_snapshot` with `["last","prior_close","change","top_status"]` (+ exchange for futures). `chg_pct` = `change.change_pct` (vs previous session close).
3. Write `docs/data/live.json` with the same structure as the current file: `checked_utc`, `checked_label` (Dubai time in Arabic), and for each asset `code, last, ref_close, chg_pct, threshold, breach (|chg_pct| ≥ threshold), status_ar, ts_label`.
4. If any breach is NEW (not already flagged in the previous live.json for the same session): run a quick web search for the cause (2 sources), add `note` text in live.json, and build a short `alert_t1`-style report for that asset only (template, SLOT `alert_watch_<HHMM>`, one asset, ladder days=1) — validate and publish. Keep it under 10 minutes.
5. Queue: list open GitHub issues in SoloGhub/SoloSophy- with label `report-request` (GitHub connector). For each: parse the `SOLOSOPHY_REQUEST type=… assets=… note=…` line, produce that report following `ops/prompts/on_demand.md`, comment the report link on the issue and close it. If several are open, serve the oldest first; max 1 per run.
6. Commit and push only if live.json or a report changed (RUNBOOK §6). If markets are closed (all FROZEN and no change) just exit with one line.
