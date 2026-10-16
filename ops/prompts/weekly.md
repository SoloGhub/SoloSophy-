# Weekly report (slot `weekly`, Saturday ~10:12 Dubai)
Goal: weekly wrap of Mon–Fri + the coming week, exactly like `docs/data/reports/2026-10-17/weekly.json` (the reference edition).
1. Read `ops/RUNBOOK.md`, `ops/contracts.json`, and the reference builder `scripts/build_report_2026_10_17.py`.
2. Data: RUNBOOK §2 (prices are Friday's Last close, status FROZEN). CFTC COT released Friday 23:30 Dubai.
3. Research the whole week + next week's calendar (Dubai times, consensus, prior, importance). Analysts: Kitco weekly survey, banks, Asia (China/Japan/Korea), Europe, Gulf.
4. Engine refresh: RUNBOOK §5 (mandatory weekly) and link `engine_ref`.
5. Ladder `days=5`, horizon = next week. Historical analogs via `Kit.analog()`.
6. Validate → publish → final Arabic summary. Also update `docs/data/alerts.json` "events" with next week's alert plan if the Sunday scan has not run yet.
