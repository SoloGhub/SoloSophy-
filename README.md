# SoloSophy Insights — Private-Banking Market Reports

**Web app:** https://sologhub.github.io/SoloSophy-/ (GitHub Pages, served from the `gh-pages` branch which mirrors `docs/`).

| Folder | Content |
|---|---|
| `docs/` | The public web app (no login): report, alerts & agenda, Engine Lab, archive, listen, request-a-report-now. Data in `docs/data/`. |
| `data/` | Raw IBKR captures (`data/raw/<date>`) and computed levels (`data/derived/<date>`). |
| `scripts/` | Ingest, indicators, execution levels, report kit, validator (publication gate), engine refresh. |
| `engine/` | CME research engine v0.3 (source, merged raw data, runs). |
| `ops/` | Runbook for scheduled tasks, prompts per task, contracts, short constitution (Arabic). |
| `legacy/` | Earlier prototype, kept for reference. |

Rules: IBKR read-only · Last price never settlement · no number without a source or a computation · 5-rung scenario ladder summing to 100 · no-trade zone first · validator must pass before publishing.
