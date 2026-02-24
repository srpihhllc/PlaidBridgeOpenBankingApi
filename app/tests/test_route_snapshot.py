# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_route_snapshot.py

import json
from pathlib import Path

import pytest

SNAPSHOT_FILE = Path(__file__).parent / "route_snapshot.json"


def test_route_snapshot(app):
    """Ensure the API route map matches the stored snapshot."""
    current = sorted(
        {
            "rule": rule.rule,
            "methods": sorted(m for m in rule.methods if m not in {"HEAD", "OPTIONS"}),
            "endpoint": rule.endpoint,
        }
        for rule in app.url_map.iter_rules()
    )

    if not SNAPSHOT_FILE.exists():
        # First run: create snapshot
        SNAPSHOT_FILE.write_text(json.dumps(current, indent=2))
        pytest.fail(
            "Route snapshot created. Re-run tests to validate. "
            "Commit route_snapshot.json to lock the API surface."
        )

    saved = json.loads(SNAPSHOT_FILE.read_text())

    assert current == saved, (
        "Route map has changed.\n"
        "If this change is intentional, update route_snapshot.json.\n"
        "Otherwise, investigate unexpected route drift."
    )
