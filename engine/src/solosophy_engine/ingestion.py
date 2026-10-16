from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


STEP_SECONDS = {
    "ONE_DAY": 86_400,
    "ONE_HOUR": 3_600,
    "THIRTY_MINS": 1_800,
}

TIMEFRAME_BY_STEP = {
    "ONE_DAY": "daily",
    "ONE_HOUR": "hourly",
    "THIRTY_MINS": "thirty_minute",
}

MINIMUM_RESEARCH_BARS = {
    "daily": 200,
    "hourly": 500,
    "thirty_minute": 500,
}


class DataContractError(ValueError):
    """Raised when the source response cannot be mapped without guessing."""


@dataclass
class LoadedDataset:
    dataset_id: str
    context: dict[str, Any]
    bars: pd.DataFrame
    analysis_bars: pd.DataFrame
    quarantine: pd.DataFrame
    report: dict[str, Any]


def _as_utc(value: str) -> pd.Timestamp:
    parsed = pd.Timestamp(value)
    if parsed.tzinfo is None:
        raise DataContractError(f"Timezone missing from timestamp: {value}")
    return parsed.tz_convert("UTC")


def _metadata_warning(response: dict[str, Any], times: pd.Series, step_seconds: int) -> list[str]:
    warnings: list[str] = []
    if times.empty:
        return warnings
    tolerance = pd.Timedelta(seconds=step_seconds)
    for field, observed in (("chart_start", times.min()), ("chart_end", times.max())):
        raw_value = response.get(field)
        if not raw_value:
            continue
        try:
            declared = _as_utc(raw_value)
        except (TypeError, ValueError):
            warnings.append(f"invalid_{field}_metadata")
            continue
        if abs(declared - observed) > tolerance:
            warnings.append(f"{field}_does_not_match_bar_timestamps")
    return warnings


def load_ibkr_history(path: str | Path, *, as_of: str | pd.Timestamp | None = None) -> LoadedDataset:
    source_path = Path(path)
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    request = payload.get("request", {})
    response = payload.get("response", {})

    if response.get("error"):
        raise DataContractError(f"Source error: {response['error']}")

    required_context = ("asset", "contract_id", "exchange", "contract_month", "step")
    missing_context = [key for key in required_context if request.get(key) in (None, "")]
    if missing_context:
        raise DataContractError(f"Missing request context: {missing_context}")
    if request['asset'] not in {'GC', 'SI'} or request['exchange'] != 'COMEX':
        raise DataContractError('Asset or exchange outside approved scope')
    if not isinstance(request['contract_id'], int) or isinstance(request['contract_id'], bool) or request['contract_id'] <= 0:
        raise DataContractError('Contract id must be a positive integer')
    if response.get('chart_step') is not None and response['chart_step'] != STEP_SECONDS.get(request['step']):
        raise DataContractError('Response chart_step does not match request')

    step_name = request["step"]
    if step_name not in STEP_SECONDS:
        raise DataContractError(f"Unsupported step: {step_name}")
    step_seconds = STEP_SECONDS[step_name]
    timeframe = TIMEFRAME_BY_STEP[step_name]

    arrays = {key: response.get(key) for key in ("time", "open", "high", "low", "close")}
    if any(not isinstance(value, list) for value in arrays.values()):
        raise DataContractError("Missing one or more required OHLC arrays")
    lengths = {key: len(value) for key, value in arrays.items()}
    if len(set(lengths.values())) != 1:
        raise DataContractError(f"OHLC array length mismatch: {lengths}")
    if not arrays["time"]:
        raise DataContractError("Source returned no bars")

    volume = response.get("volume")
    warnings: list[str] = []
    if volume is None:
        volume = [np.nan] * lengths["time"]
        warnings.append("volume_missing")
    elif not isinstance(volume, list) or len(volume) != lengths["time"]:
        raise DataContractError("Volume array length mismatch")

    if any(not isinstance(value, str) or pd.Timestamp(value).tzinfo is None for value in arrays['time']):
        raise DataContractError('Every bar timestamp must explicitly include a timezone')
    times = pd.to_datetime(arrays["time"], utc=True, errors="coerce")
    if times.isna().any():
        raise DataContractError("One or more bar timestamps are invalid")

    captured_at = _as_utc(payload.get('captured_at_utc'))
    checked_at = _as_utc(as_of) if as_of is not None else pd.Timestamp.now(tz='UTC')
    if captured_at > checked_at + pd.Timedelta(minutes=5):
        raise DataContractError('Capture timestamp is in the future')
    frame = pd.DataFrame(
        {
            "bar_start_utc": times,
            "open": pd.to_numeric(arrays["open"], errors="coerce"),
            "high": pd.to_numeric(arrays["high"], errors="coerce"),
            "low": pd.to_numeric(arrays["low"], errors="coerce"),
            "close": pd.to_numeric(arrays["close"], errors="coerce"),
            "volume": pd.to_numeric(volume, errors="coerce"),
        }
    )
    frame["bar_end_utc"] = frame["bar_start_utc"] + pd.to_timedelta(step_seconds, unit="s")
    frame["is_closed"] = frame["bar_end_utc"] <= captured_at

    duplicate_count = int(frame.duplicated(subset=["bar_start_utc"], keep="last").sum())
    duplicate_rows = frame.loc[frame.duplicated('bar_start_utc', keep=False)]
    if not duplicate_rows.empty and (duplicate_rows.groupby('bar_start_utc')[["open", "high", "low", "close", "volume"]].nunique(dropna=False) > 1).any().any():
        raise DataContractError('Conflicting duplicate bars must not be silently resolved')
    frame = frame.sort_values("bar_start_utc").drop_duplicates("bar_start_utc", keep="last")

    numeric = frame[["open", "high", "low", "close"]]
    finite = np.isfinite(numeric).all(axis=1) & (numeric > 0).all(axis=1)
    coherent = (
        (frame["high"] >= frame[["open", "close", "low"]].max(axis=1))
        & (frame["low"] <= frame[["open", "close", "high"]].min(axis=1))
    )
    valid = finite & coherent & frame["is_closed"]
    quarantine_reason = pd.Series(
        np.select(
            [~finite, ~coherent, ~frame["is_closed"]],
            ["non_finite_ohlc", "impossible_ohlc", "incomplete_bar"],
            default="unknown",
        ),
        index=frame.index,
    )
    quarantine = frame.loc[~valid].copy()
    quarantine["quarantine_reason"] = quarantine_reason.loc[~valid]
    curated = frame.loc[valid].copy().reset_index(drop=True)
    invalid_volume = ~np.isfinite(curated['volume']) | (curated['volume'] < 0)
    if invalid_volume.any():
        curated.loc[invalid_volume, 'volume'] = np.nan
        warnings.append('invalid_or_missing_volume_excluded')
    structural_invalid = finite & ~coherent | ~finite
    structural_invalid_times = frame.loc[structural_invalid, "bar_start_utc"]
    if structural_invalid_times.empty:
        reliable_segment_start = curated["bar_start_utc"].min() if len(curated) else None
        analysis_bars = curated.copy()
    else:
        last_structural_invalid = structural_invalid_times.max()
        analysis_bars = curated.loc[curated["bar_start_utc"] > last_structural_invalid].copy()
        reliable_segment_start = analysis_bars["bar_start_utc"].min() if len(analysis_bars) else None

    incomplete_count = int((~frame["is_closed"]).sum())
    impossible_count = int((finite & ~coherent).sum())
    non_finite_count = int((~finite).sum())
    closed_bar_count = int(frame["is_closed"].sum())
    structural_anomaly_share = (
        float((impossible_count + non_finite_count) / closed_bar_count) if closed_bar_count else None
    )
    if duplicate_count:
        warnings.append("duplicate_bars_resolved_keep_last")
    if incomplete_count:
        warnings.append("incomplete_bars_quarantined")
    if impossible_count:
        warnings.append("impossible_ohlc_quarantined")
    if non_finite_count:
        warnings.append("non_finite_ohlc_quarantined")
    warnings.extend(_metadata_warning(response, frame["bar_start_utc"], step_seconds))

    gap_count = 0
    if len(curated) > 1:
        diffs = curated["bar_start_utc"].diff().dropna().dt.total_seconds()
        gap_count = int((diffs > step_seconds * 1.5).sum())
        if gap_count:
            warnings.append("raw_gaps_require_exchange_calendar_classification")

    volume_share = float((curated["volume"].fillna(0) > 0).mean()) if len(curated) else None
    recent_cutoff = captured_at - pd.Timedelta(days=30)
    recent = curated.loc[curated["bar_start_utc"] >= recent_cutoff]
    recent_volume_share = float((recent["volume"].fillna(0) > 0).mean()) if len(recent) else None
    volume_quality = "unverified"
    if recent_volume_share is None:
        volume_quality = "missing"
    elif recent_volume_share >= 0.90:
        volume_quality = "recent_positive_values_not_independently_verified"
    if volume_share is not None and volume_share < 0.90:
        warnings.append("full_history_volume_not_reliable")

    blocking_reasons: list[str] = []
    if len(analysis_bars) < MINIMUM_RESEARCH_BARS[timeframe]:
        blocking_reasons.append("insufficient_reliable_analysis_bars")
    decision = "reject" if not len(curated) else "quarantine" if blocking_reasons else "accept_with_limits" if warnings else "accept"

    dataset_id = source_path.stem
    latest_end = curated['bar_end_utc'].max() if len(curated) else None
    age_seconds = max(0.0, (checked_at - latest_end).total_seconds()) if latest_end is not None else None
    live_blockers = list(blocking_reasons)
    if age_seconds is None or age_seconds > 2 * step_seconds:
        live_blockers.append('last_closed_bar_is_stale')
    if gap_count:
        live_blockers.append('gaps_not_classified_against_exchange_calendar')
    # The source schema does not certify native/continuous/back-adjusted prices.
    live_blockers.extend(['price_series_construction_unverified', 'exchange_calendar_not_loaded'])
    report = {
        "dataset_id": dataset_id,
        "symbol": request["asset"],
        "local_symbol": request.get("local_symbol"),
        "contract_id": request["contract_id"],
        "contract_expiry": request["contract_month"],
        "timeframe": timeframe,
        "coverage_start_utc": curated["bar_start_utc"].min().isoformat() if len(curated) else None,
        "coverage_end_utc": curated["bar_start_utc"].max().isoformat() if len(curated) else None,
        "bar_count": int(len(curated)),
        "analysis_bar_count": int(len(analysis_bars)),
        "reliable_segment_start_utc": reliable_segment_start.isoformat() if reliable_segment_start is not None else None,
        "duplicate_count": duplicate_count,
        "gap_count": gap_count,
        "incomplete_bar_count": incomplete_count,
        "impossible_ohlc_count": impossible_count,
        "non_finite_ohlc_count": non_finite_count,
        "structural_anomaly_share": structural_anomaly_share,
        "long_history_price_quality": (
            "not_backtest_ready" if impossible_count or non_finite_count else "passed_internal_checks"
        ),
        "quarantine_count": int(len(quarantine)),
        "valid_volume_share": volume_share,
        "recent_valid_volume_share": recent_volume_share,
        "volume_quality": volume_quality,
        "delay_state": "historical",
        "blocking_reasons": blocking_reasons,
        "warnings": sorted(set(warnings)),
        "decision": decision,
        "research_eligible": decision in {'accept', 'accept_with_limits'},
        "live_eligible": not live_blockers,
        "live_blocking_reasons": sorted(set(live_blockers)),
        "last_closed_bar_age_seconds": age_seconds,
        "raw_bar_count": len(arrays['time']),
        "captured_at_utc": captured_at.isoformat(),
        "timestamp_end_basis": 'nominal_bar_duration_conservative_not_exchange_settlement',
        "series_construction": 'unverified_contract_request_not_proof_of_unadjusted_series',
        "checked_at_utc": checked_at.isoformat(),
    }

    curated.insert(0, "symbol", request["asset"])
    curated.insert(1, "contract_id", request["contract_id"])
    curated.insert(2, "contract_expiry", request["contract_month"])
    curated.insert(3, "exchange", request["exchange"])
    curated.insert(4, "timeframe", timeframe)
    curated["source"] = payload.get("source", "existing_ibkr_connection")
    curated["received_at_utc"] = captured_at
    curated["data_delay_state"] = "historical"
    curated["volume_quality"] = volume_quality

    context = {
        "asset": request["asset"],
        "contract_id": request["contract_id"],
        "contract_month": request["contract_month"],
        "exchange": request["exchange"],
        "timeframe": timeframe,
        "step_seconds": step_seconds,
        "captured_at_utc": captured_at.isoformat(),
        "source_file": str(source_path),
    }
    analysis_bars = analysis_bars.reset_index(drop=True)
    return LoadedDataset(dataset_id, context, curated, analysis_bars, quarantine, report)
