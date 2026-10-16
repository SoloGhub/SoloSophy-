# Snapshot report (slots: `pre_europe` ~10:20 Dubai, `us_mid` ~20:20 Dubai)
Goal: a fast, precise update — where each market is now, what changed since the previous report, the levels that matter for the next hours, the 5-rung ladder (days=1) and execution levels.
1. Read `ops/RUNBOOK.md` (rules 0–8 are mandatory) and `ops/contracts.json`.
2. Data: RUNBOOK §2 (snapshots + daily history + compute_levels). Note the IBKR timestamp of each `last`.
3. Research (RUNBOOK §3), limited to what happened since the last report in `docs/data/index.json` and the next 12 hours of events (Dubai time). `pre_europe`: Asia session moves, China/Japan data, overnight geopolitics, today's EU/US calendar. `us_mid`: US data released today (actual vs consensus), market reaction since 17:30, Fed/oil/geopolitics headlines, EIA if Wednesday.
4. Build from `ops/templates/report_template.py` with SLOT = the slot named in the task. `what_changed` must compare with the previous report's prices (read its JSON).
5. Validate → publish (RUNBOOK §6) → final Arabic summary (RUNBOOK §7).
Time budget: aim to publish within 20 minutes of start.
