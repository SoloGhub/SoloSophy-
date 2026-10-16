from __future__ import annotations

from typing import Any


def _direction(state: str) -> str:
    if "_up_" in state:
        return "up"
    if "_down_" in state:
        return "down"
    if state == "NO_ANALYSIS":
        return "unavailable"
    return "neutral"


def merge_current_states(states: dict[str, dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    order = ("daily", "hourly", "thirty_minute")
    for asset, timeframe_states in states.items():
        directions = {
            timeframe: _direction(timeframe_states.get(timeframe, {}).get("state", "NO_ANALYSIS"))
            for timeframe in order
        }
        available = [value for value in directions.values() if value not in {"unavailable", "neutral"}]
        if len(available) == 3 and len(set(available)) == 1:
            consensus = f"aligned_{available[0]}"
        elif not available:
            consensus = "no_directional_consensus"
        elif len(set(available)) == 1:
            consensus = f"partial_{available[0]}_alignment"
        else:
            daily = directions["daily"]
            consensus = f"mixed_with_daily_{daily}_bias" if daily in {"up", "down"} else "mixed_without_daily_bias"
        result[asset] = {
            "timeframe_directions": directions,
            "consensus": consensus,
            "probability_withheld": True,
            "note": "deterministic_state_merge_not_a_trade_recommendation",
        }
    return result

