from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sqlite3


class Repository:
    """Versioned response archive. No credentials, trading, or network access."""
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS raw_responses (
                    content_hash TEXT PRIMARY KEY, source_name TEXT NOT NULL,
                    captured_at_utc TEXT NOT NULL, asset TEXT NOT NULL,
                    contract_id INTEGER NOT NULL, step TEXT NOT NULL, payload_json TEXT NOT NULL
                );
                CREATE TRIGGER IF NOT EXISTS raw_no_update BEFORE UPDATE ON raw_responses
                    BEGIN SELECT RAISE(ABORT, 'raw responses are append only'); END;
                CREATE TRIGGER IF NOT EXISTS raw_no_delete BEFORE DELETE ON raw_responses
                    BEGIN SELECT RAISE(ABORT, 'raw responses are append only'); END;
            ''')

    def ingest(self, path: str | Path) -> dict:
        raw = Path(path).read_bytes()
        payload = json.loads(raw)
        request = payload['request']
        fingerprint = sha256(raw).hexdigest()
        with sqlite3.connect(self.path) as db:
            cursor = db.execute('INSERT OR IGNORE INTO raw_responses VALUES (?, ?, ?, ?, ?, ?, ?)', (
                fingerprint, Path(path).name, payload['captured_at_utc'], request['asset'],
                request['contract_id'], request['step'], raw.decode('utf-8')))
        return {'content_hash': fingerprint, 'inserted': cursor.rowcount == 1}

    def inventory(self) -> list[dict]:
        with sqlite3.connect(self.path) as db:
            db.row_factory = sqlite3.Row
            return [dict(row) for row in db.execute(
                'SELECT content_hash, source_name, captured_at_utc, asset, contract_id, step '
                'FROM raw_responses ORDER BY captured_at_utc, asset, step')]
