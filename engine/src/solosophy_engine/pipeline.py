from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .indicators import compute_features
from .ingestion import DataContractError, load_ibkr_history
from .backtest import HORIZONS, regime_conditioned_signal, validate_rule_candidates
from .journal import append_snapshot, verify_journal
from .multitimeframe import merge_current_states
from .regime import RULESET_VERSION, classify_latest
from .scenarios import build_conditional_scenarios
from .levels import confluence_zones, temporal_profile
from .repository import Repository
from .outcomes import score_outcomes


def _json_default(value: Any) -> Any:
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if np.isnan(value) else float(value)
    raise TypeError(f"Unsupported JSON value: {type(value)!r}")


def _fingerprint(paths: list[Path]) -> str:
    digest = sha256()
    for path in sorted(paths):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _cross_asset_daily(feature_sets: dict[tuple[str, str], pd.DataFrame]) -> dict[str, Any]:
    gc = feature_sets.get(("GC", "daily"))
    si = feature_sets.get(("SI", "daily"))
    if gc is None or si is None:
        return {"state": "not_available", "reason": "daily_pair_missing"}
    left = gc[["bar_start_utc", "close", "log_return"]].rename(columns={"close": "gc_close", "log_return": "gc_return"})
    right = si[["bar_start_utc", "close", "log_return"]].rename(columns={"close": "si_close", "log_return": "si_return"})
    joined = left.merge(right, on="bar_start_utc", how="inner").sort_values("bar_start_utc")
    if len(joined) < 60:
        return {"state": "not_available", "reason": "insufficient_aligned_daily_bars", "aligned_bars": len(joined)}
    # Recompute both returns AFTER joining so their endpoints always agree.
    joined['gc_return'] = np.log(joined.gc_close / joined.gc_close.shift())
    joined['si_return'] = np.log(joined.si_close / joined.si_close.shift())
    joined["correlation_60"] = joined["gc_return"].rolling(60, min_periods=60).corr(joined["si_return"])
    joined["gold_silver_price_ratio"] = joined["gc_close"] / joined["si_close"].replace(0, np.nan)
    last = joined.iloc[-1]
    return {
        "state": "calculated",
        "aligned_bars": int(len(joined)),
        "data_cutoff_utc": last["bar_start_utc"].isoformat(),
        "rolling_return_correlation_60": None if pd.isna(last["correlation_60"]) else float(last["correlation_60"]),
        "gold_silver_price_ratio": None if pd.isna(last["gold_silver_price_ratio"]) else float(last["gold_silver_price_ratio"]),
        "note": "descriptive_only_not_a_signal",
    }


def run_pipeline(raw_dir: str | Path, output_dir: str | Path, *, as_of: str | None = None) -> dict[str, Any]:
    raw_path = Path(raw_dir)
    out = Path(output_dir)
    curated_dir = out / "curated"
    feature_dir = out / "features"
    quarantine_dir = out / "quarantine"
    for directory in (out, curated_dir, feature_dir, quarantine_dir):
        directory.mkdir(parents=True, exist_ok=True)

    source_files = sorted(raw_path.glob("*.json"))
    repository = Repository(out / 'market_archive.sqlite3')
    observed_at = pd.Timestamp(as_of) if as_of else pd.Timestamp.now(tz='UTC')
    if observed_at.tzinfo is None:
        raise ValueError('as_of must have a timezone')
    reports: list[dict[str, Any]] = []
    feature_sets: dict[tuple[str, str], pd.DataFrame] = {}
    states: dict[str, dict[str, Any]] = {}
    validation: dict[str, dict[str, Any]] = {}
    scenarios: dict[str, dict[str, list[dict[str, Any]]]] = {}
    asset_context: dict[str, dict[str, Any]] = {}
    accepted_paths: list[Path] = []
    forecasts: dict[str, list[dict]] = {}
    levels: dict[str, dict] = {}
    profiles: dict[str, dict] = {}
    seen_keys = set()

    for path in source_files:
        try:
            loaded = load_ibkr_history(path, as_of=observed_at)
            key = (loaded.context['asset'], loaded.context['timeframe'])
            if key in seen_keys:
                raise RuntimeError('Multiple snapshots for one asset/timeframe require explicit selection')
            seen_keys.add(key)
            repository.ingest(path)
        except (DataContractError, KeyError, TypeError, ValueError) as exc:
            reports.append(
                {
                    "dataset_id": path.stem,
                    "decision": "reject",
                    "blocking_reasons": [str(exc)],
                    "warnings": [],
                }
            )
            continue

        reports.append(loaded.report)
        loaded.bars.to_csv(curated_dir / f"{loaded.dataset_id}.csv", index=False)
        loaded.quarantine.to_csv(quarantine_dir / f"{loaded.dataset_id}.csv", index=False)
        state_key = (loaded.context['asset'], loaded.context['timeframe'])
        asset_context.setdefault(state_key[0], {'contract_expiry': loaded.context['contract_month'], 'quality_decision': 'no_analysis'})
        if loaded.report['decision'] not in {'accept', 'accept_with_limits'}:
            states.setdefault(state_key[0], {})[state_key[1]] = {
                'state': 'NO_ANALYSIS', 'quality_decision': loaded.report['decision'],
                'reason': loaded.report['blocking_reasons'], 'live_eligible': False,
            }
            # Explicit empty current output prevents stale features surviving rejection.
            pd.DataFrame(columns=loaded.analysis_bars.columns).to_csv(feature_dir / f'{loaded.dataset_id}.csv', index=False)
        if loaded.report["decision"] in {"accept", "accept_with_limits"}:
            features = compute_features(loaded.analysis_bars)
            features['contract_id'] = loaded.context['contract_id']
            features.to_csv(feature_dir / f"{loaded.dataset_id}.csv", index=False)
            key = (loaded.context["asset"], loaded.context["timeframe"])
            feature_sets[key] = features
            state = classify_latest(features)
            state["quality_decision"] = loaded.report["decision"]
            state["volume_quality"] = loaded.report["volume_quality"]
            state['live_eligible'] = loaded.report['live_eligible']
            state['live_blocking_reasons'] = loaded.report['live_blocking_reasons']
            state['data_age_seconds'] = loaded.report['last_closed_bar_age_seconds']
            levels.setdefault(key[0], {})[key[1]] = confluence_zones(features)
            profiles.setdefault(key[0], {})[key[1]] = temporal_profile(features)
            states.setdefault(loaded.context["asset"], {})[loaded.context["timeframe"]] = state
            validation.setdefault(loaded.context["asset"], {})[loaded.context["timeframe"]] = (
                validate_rule_candidates(features, loaded.context["timeframe"])
            )
            scenarios.setdefault(loaded.context["asset"], {})[loaded.context["timeframe"]] = (
                build_conditional_scenarios(features, state)
            )
            asset_context[loaded.context["asset"]] = {
                "contract_expiry": loaded.context["contract_month"],
                "quality_decision": loaded.report["decision"],
            }
            accepted_paths.append(path)
            last = features.iloc[-1]
            forecasts.setdefault(key[0], []).append({
                'timeframe': key[1], 'contract_id': loaded.context['contract_id'],
                'reference_bar_start_utc': last['bar_start_utc'].isoformat(),
                'reference_bar_end_utc': last['bar_end_utc'].isoformat(),
                'reference_close': float(last['close']),
                'direction': int(regime_conditioned_signal(features).iloc[-1]),
                'horizons_bars': list(HORIZONS[key[1]]), 'step_seconds': loaded.context['step_seconds'],
                'use': 'research_observation_not_live_signal',
                'live_eligible': loaded.report['live_eligible'],
            })

    coverage = pd.DataFrame(reports)
    coverage.to_csv(out / "coverage_matrix.csv", index=False)
    (out / "coverage_matrix.json").write_text(
        json.dumps(reports, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8"
    )

    fingerprint = _fingerprint(source_files) if source_files else None
    code_fingerprint = _fingerprint(list(Path(__file__).parent.glob('*.py')))
    generated_at = observed_at.isoformat()
    walk_forward_survivors = {
        asset: {
            timeframe: report["regime_conditioned_walk_forward"]["stable_edge_horizons"]
            for timeframe, report in timeframes.items()
        }
        for asset, timeframes in validation.items()
    }
    engine_output = {
        "generated_at_utc": generated_at,
        "ruleset_version": RULESET_VERSION,
        "ruleset_fingerprint": code_fingerprint,
        "ruleset_validated": False,
        "probabilities_withheld": True,
        "input_fingerprint": fingerprint,
        "run_status": 'research_only_live_blocked' if feature_sets else 'blocked_no_accepted_data',
        "research_sample_is_untouched_holdout": False,
        "source_dataset_manifest": [dict(path=path.name, sha256=sha256(path.read_bytes()).hexdigest()) for path in source_files],
        "timeframe_states": states,
        "multitimeframe_consensus": merge_current_states(states),
        "candidate_rule_validation": validation,
        "walk_forward_survivors": walk_forward_survivors,
        "cross_asset_daily": _cross_asset_daily(feature_sets),
        "level_zones": levels,
        "time_profiles": profiles,
        "operational_actions": {asset: {'action': 'NO_LIVE_SIGNAL', 'probability': None,
                                        'reason': 'source_quality_and_calibration_not_approved'} for asset in ('GC', 'SI')},
        "event_layer": {'status': 'blocked_verified_event_dataset_missing'},
        "execution_layer": {'status': 'blocked_verified_cost_model_missing'},
        "collection_mode": 'on_demand_connector_snapshot_no_background_schedule',
        "scenario_set": scenarios,
        "scenario_status": "conditional_descriptions_only_probabilities_withheld",
        "shadow_mode": {
            "status": "research_journaling_only_not_validated_prospective_signal",
            "orders_enabled": False,
            "probability_publication_enabled": False,
            "next_requirement": "accumulate_forward_unmodified_journal_observations",
        },
    }

    journal_path = out / "signal_journal.jsonl"
    journal_writes: dict[str, Any] = {}
    for asset, timeframe_states in states.items():
        cutoffs = [state.get("data_cutoff_utc") for state in timeframe_states.values() if state.get("data_cutoff_utc")]
        cutoff = max(cutoffs) if cutoffs else generated_at
        journal_scenarios = [
            {**scenario, "timeframe": timeframe}
            for timeframe, items in scenarios.get(asset, {}).items()
            for scenario in items
        ]
        journal_payload = {
            "signal_id": sha256(f"{asset}|{cutoff}|{fingerprint}|{code_fingerprint}".encode("utf-8")).hexdigest()[:24],
            "created_at_utc": generated_at,
            "data_cutoff_utc": cutoff,
            "symbol": asset,
            "contract_expiry": asset_context.get(asset, {}).get("contract_expiry"),
            "quality_decision": 'no_analysis' if all(s['state'] == 'NO_ANALYSIS' for s in timeframe_states.values()) else (
                'accept_with_limits' if any(s.get('quality_decision') != 'accept' for s in timeframe_states.values()) else 'accept'),
            "regime": merge_current_states({asset: timeframe_states})[asset]["consensus"],
            "timeframe_states": timeframe_states,
            "scenario_set": journal_scenarios,
            "ruleset_version": RULESET_VERSION,
            "ruleset_fingerprint": code_fingerprint,
            "input_fingerprint": fingerprint,
            "forecasts": forecasts.get(asset, []),
            "entry_type": 'research_snapshot_not_trading_instruction',
            "probabilities_withheld": True,
            "orders_enabled": False,
        }
        journal_writes[asset] = append_snapshot(journal_path, journal_payload)
    engine_output["signal_journal"] = {
        "path": "signal_journal.jsonl",
        "writes": journal_writes,
        "integrity": verify_journal(journal_path),
        "protection": 'tamper_evident_hash_chain_not_encryption_or_absolute_immutability',
    }
    engine_output['outcome_scoring'] = score_outcomes(journal_path, feature_sets, out / 'outcome_journal.jsonl', as_of=generated_at)
    engine_output['raw_archive'] = {'path': 'market_archive.sqlite3', 'responses': len(repository.inventory())}
    (out / "engine_output.json").write_text(
        json.dumps(engine_output, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8"
    )
    return engine_output
