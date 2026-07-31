# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/cli_commands/route_drift.py

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Set

import click
from flask import current_app
from flask.cli import with_appcontext


def _load_expected(path: Path) -> Set[str]:
    text = path.read_text(encoding="utf-8").strip()
    # support either JSON array or newline-separated list
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return {str(x) for x in data}
    except Exception:
        pass
    return {line.strip() for line in text.splitlines() if line.strip()}


@click.command("route-drift")
@click.option("--expected-file", "-e", required=True, type=click.Path(exists=True, readable=True), help="Path to JSON array or newline list of expected endpoints (e.g. expected_endpoints.json)")
@click.option("--fail-on-missing/--no-fail-on-missing", default=True, help="Exit non-zero if any expected endpoints are missing")
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON summary")
@with_appcontext
def route_drift(expected_file: str, fail_on_missing: bool, as_json: bool) -> None:
    """
    Compare an expected endpoint list to the endpoints actually registered in Flask.
    Exits with non-zero status when missing endpoints are found (if --fail-on-missing).
    """
    expected_path = Path(expected_file)
    expected = _load_expected(expected_path)

    rules = list(current_app.url_map.iter_rules())
    actual = {r.endpoint for r in rules if r.endpoint}

    missing = sorted(list(expected - actual))
    unexpected = sorted(list(actual - expected))

    summary = {
        "expected_count": len(expected),
        "actual_count": len(actual),
        "missing": missing,
        "unexpected": unexpected,
    }

    if as_json:
        click.echo(json.dumps(summary, indent=2))
    else:
        click.echo(f"Expected endpoints: {len(expected)}")
        click.echo(f"Actual endpoints:   {len(actual)}")
        click.echo("")
        if missing:
            click.echo("Missing endpoints:")
            for e in missing:
                click.echo(f"  - {e}")
        else:
            click.echo("No expected endpoints missing.")
        click.echo("")
        if unexpected:
            click.echo("Unexpected (extra) endpoints:")
            for e in unexpected:
                click.echo(f"  - {e}")
        else:
            click.echo("No unexpected endpoints detected.")

    if missing and fail_on_missing:
        # Non-zero exit for CI
        sys.exit(2)