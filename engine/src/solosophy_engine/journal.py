from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any


GENESIS_HASH = "0" * 64


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def verify_journal(path: str | Path) -> dict[str, Any]:
    journal = Path(path)
    previous = GENESIS_HASH
    count = 0
    if not journal.exists():
        return {"valid": True, "record_count": 0, "last_hash": previous}
    for line_number, line in enumerate(journal.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError('Expected object')
        except (ValueError, TypeError):
            return {'valid': False, 'record_count': count, 'failure_line': line_number, 'reason': 'malformed_record'}
        claimed = record.pop("record_hash", None)
        if record.get("previous_hash") != previous:
            return {"valid": False, "record_count": count, "failure_line": line_number, "reason": "previous_hash_mismatch"}
        calculated = sha256(_canonical(record)).hexdigest()
        if claimed != calculated:
            return {"valid": False, "record_count": count, "failure_line": line_number, "reason": "record_hash_mismatch"}
        previous = calculated
        count += 1
    return {"valid": True, "record_count": count, "last_hash": previous}


def append_snapshot(path: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Tamper-evident, not encrypted/immutable; exclusive lock fails closed."""
    journal = Path(path)
    journal.parent.mkdir(parents=True, exist_ok=True)
    if {'previous_hash', 'record_hash'} & payload.keys():
        raise ValueError('Reserved hash fields cannot be supplied')
    lock = journal.with_suffix(journal.suffix + '.lock')
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ValueError('Journal locked; do not remove a lock without checking the writer') from exc
    try:
        return _append_locked(journal, payload)
    finally:
        os.close(descriptor)
        lock.unlink()


def _append_locked(journal: Path, payload: dict[str, Any]) -> dict[str, Any]:
    audit = verify_journal(journal)
    if not audit["valid"]:
        raise ValueError(f"Journal integrity failure: {audit}")
    lines = journal.read_text(encoding="utf-8").splitlines() if journal.exists() else []
    duplicate_key = ('event_id',) if payload.get('event_id') else ("input_fingerprint", "symbol", "data_cutoff_utc", "ruleset_version", 'ruleset_fingerprint')
    for line in lines:
        existing = json.loads(line)
        if all(existing.get(key) == payload.get(key) for key in duplicate_key):
            return {"appended": False, "reason": "duplicate_snapshot", **audit}
    record = dict(payload)
    record["previous_hash"] = audit["last_hash"]
    record_hash = sha256(_canonical(record)).hexdigest()
    record["record_hash"] = record_hash
    with journal.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return {"appended": True, "record_count": audit["record_count"] + 1, "last_hash": record_hash, "valid": True}
