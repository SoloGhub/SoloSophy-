from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import platform
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from solosophy_engine.pipeline import run_pipeline
from solosophy_engine.repository import Repository
from solosophy_engine.journal import verify_journal


def main():
    tests = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                           cwd=ROOT, text=True, capture_output=True)
    print(tests.stdout + tests.stderr)
    if tests.returncode:
        raise SystemExit(tests.returncode)
    out = ROOT / 'reports' / 'audited'
    repository = Repository(out / 'market_archive.sqlite3')
    for source in sorted((ROOT / 'data' / 'raw' / 'ibkr').glob('*.json')):
        repository.ingest(source)
    raw = ROOT / 'data' / 'raw' / 'refresh_2026_09_07'
    first = run_pipeline(raw, out)
    first_count = verify_journal(out / 'signal_journal.jsonl')['record_count']
    second = run_pipeline(raw, out)
    second_count = verify_journal(out / 'signal_journal.jsonl')['record_count']
    if first_count != second_count:
        raise SystemExit('Idempotent replay failed')
    if not second['probabilities_withheld'] or second['shadow_mode']['orders_enabled']:
        raise SystemExit('Publication gates failed')
    subprocess.run([sys.executable, 'scripts/build_validation_notebook.py'], cwd=ROOT, check=True)
    notebook = json.loads((ROOT / 'notebooks' / 'SoloSophy_Audited_Research.ipynb').read_text())
    code_cells = [cell for cell in notebook['cells'] if cell['cell_type'] == 'code']
    if any(cell['execution_count'] is None for cell in code_cells):
        raise SystemExit('Unexecuted notebook cells')
    check = re.search(r'Ran (\d+) tests', tests.stderr)
    receipt = {
        'status': 'passed_local_acceptance_not_live_certification',
        'executed_at_utc': second['generated_at_utc'], 'python': platform.python_version(),
        'unit_tests_passed': int(check.group(1)) if check else None,
        'replay_idempotent': first_count == second_count,
        'journal_integrity': second['signal_journal']['integrity'],
        'archive_responses': len(repository.inventory()),
        'run_status': second['run_status'], 'probabilities_withheld': second['probabilities_withheld'],
        'notebook_code_cells_executed': len(code_cells),
        'notebook_execution_method': notebook['metadata']['execution_method'],
        'frontend_browser_test': 'not_run_no_live_frontend_in_package',
        'external_background_connection': 'not_implemented',
        'ruleset_fingerprint': second['ruleset_fingerprint'],
        'source_dataset_manifest': second['source_dataset_manifest'],
    }
    (out / 'acceptance_receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
