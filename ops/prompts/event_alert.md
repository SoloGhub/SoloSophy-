# Event alert (T-30 before, T+1 after) — the scheduled task names the event, time and assets
## T-30 (30 minutes before)
Order: event · time (Dubai) · official source → prior and consensus (2 sources) → why it matters now → context (recent trend, positioning) → impact grid per asset: ABOVE / IN LINE / BELOW consensus, each with direction and an analytical % move range derived from IV (σ_hour ≈ price × IV × √(1/(252×6.5)), state the method) → invalidation levels and no-trade zone from `levels.json` → sources.
## T+1 (right after release)
Order: actual vs consensus vs prior (+ revisions) from the official release or two sources → surprise size → IBKR reaction (snapshot `last` and change for the affected assets, timestamp) → interpretation → scenario repricing (new ladder weights, days=1) → action (NTZ first, levels via Kit.setup) → next trigger to watch. Never invent the actual number: if it is not yet published anywhere, wait up to 10 minutes re-checking, then publish "لم يصدر الرقم بعد" with the time checked.
## Build
Data per RUNBOOK §2 (snapshots are enough if levels.json for today exists; otherwise run the daily history step). Template with SLOT `alert_t30` or `alert_t1`; include only the affected assets; add `event` block in `what_changed`. Validate → publish → final Arabic summary.
