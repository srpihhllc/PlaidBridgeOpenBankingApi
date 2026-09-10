# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/cli_commands/sweep_endpoints.py

# =============================================================================
# FILE: app/cli_commands/sweep_endpoints.py
# DESCRIPTION: CLI command to list all registered Flask endpoints and routes.
# =============================================================================

from __future__ import annotations

import json
from collections import defaultdict
from typing import List

import click
from flask import current_app
from flask.cli import with_appcontext


@click.command("sweep-endpoints")
@click.option(
    "--filter", "-f", "filter_str", help="Filter endpoints by substring"
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Output as JSON (list of {endpoint, rule, methods, blueprint})",
)
@click.option(
    "--no-group",
    is_flag=True,
    default=False,
    help="Disable grouping by blueprint (print a flat list)",
)
@click.option(
    "--methods-only",
    is_flag=True,
    default=False,
    help="Print only endpoint -> methods mapping (one-per-line)",
)
@click.option(
    "--blueprints-only",
    is_flag=True,
    default=False,
    help="Print only blueprint names and counts",
)
@with_appcontext
def sweep_endpoints(
    filter_str: str | None,
    as_json: bool,
    no_group: bool,
    methods_only: bool,
    blueprints_only: bool,
) -> None:
    """
    List all registered Flask endpoints and their URL rules.

    - By default the output is grouped by blueprint and includes a small header with counts.
    - Use --filter / -f to show only endpoints whose name contains the substring.
    - Use --json to emit machine-readable JSON suitable for dashboards/CI.
    - Use --no-group to print a flat list (no blueprint grouping).
    - Use --methods-only to print endpoint -> methods pairs (compact).
    - Use --blueprints-only to list registered blueprints and their rule counts.
    """
    rules = sorted(
        current_app.url_map.iter_rules(), key=lambda r: r.endpoint or ""
    )
    if filter_str:
        rules = [r for r in rules if filter_str in (r.endpoint or "")]

    total_rules = len(rules)
    unique_endpoints = len({r.endpoint for r in rules})

    # JSON mode
    if as_json:
        data = []
        for r in rules:
            bp = (
                r.endpoint.split(".")[0]
                if r.endpoint and "." in r.endpoint
                else "root"
            )
            data.append(
                {
                    "endpoint": r.endpoint,
                    "rule": str(r),
                    "methods": (
                        sorted(list(r.methods))
                        if getattr(r, "methods", None)
                        else []
                    ),
                    "blueprint": bp,
                }
            )
        click.echo(
            json.dumps(
                {
                    "total_rules": total_rules,
                    "unique_endpoints": unique_endpoints,
                    "rules": data,
                },
                indent=2,
            )
        )
        return

    # Methods-only output (compact mapping)
    if methods_only:
        for r in rules:
            methods = (
                ",".join(sorted(r.methods))
                if getattr(r, "methods", None)
                else ""
            )
            click.echo(f"{(r.endpoint or 'unknown'):60} : {methods}")
        return

    # Blueprints-only output (name + count)
    if blueprints_only:
        groups: dict[str, List] = defaultdict(list)
        for r in rules:
            bp = (
                r.endpoint.split(".")[0]
                if r.endpoint and "." in r.endpoint
                else "root"
            )
            groups[bp].append(r)
        for bp in sorted(groups.keys()):
            click.echo(f"{bp}: {len(groups[bp])}")
        return

    # Human-friendly header with counts
    click.echo(f"Registered rules:   {total_rules}")
    click.echo(f"Unique endpoints:   {unique_endpoints}")
    click.echo("-" * 80)

    # Flat list (no grouping)
    if no_group:
        for r in rules:
            methods = (
                ",".join(sorted(r.methods))
                if getattr(r, "methods", None)
                else ""
            )
            click.echo(
                f"{(r.endpoint or 'unknown'):40} → {str(r):40}  methods: {methods}"
            )
        click.echo("-" * 80)
        return

    # Group by blueprint for readability
    groups: dict[str, List] = defaultdict(list)
    for r in rules:
        bp = (
            r.endpoint.split(".")[0]
            if r.endpoint and "." in r.endpoint
            else "root"
        )
        groups[bp].append(r)

    for bp in sorted(groups.keys()):
        bp_rules = groups[bp]
        click.echo(f"[{bp}] ({len(bp_rules)} rules)")
        for r in bp_rules:
            methods = (
                ",".join(sorted(r.methods))
                if getattr(r, "methods", None)
                else ""
            )
            click.echo(
                f"  {(r.endpoint or 'unknown'):36} → {str(r):40}  methods: {methods}"
            )
        click.echo("")

    click.echo("-" * 80)
