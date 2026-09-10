# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/cli_commands/route_graph.py

from __future__ import annotations

from collections import defaultdict
from typing import List

import click
from flask import current_app
from flask.cli import with_appcontext


@click.command("route-graph")
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=False, writable=True),
    default="-",
    help="Output file (default stdout). Use .dot extension to save DOT text.",
)
@with_appcontext
def route_graph(output: str) -> None:
    """
    Emit a Graphviz DOT graph of the application's routing surface.
    - Nodes: blueprints and endpoints
    - Edges: blueprint -> endpoint (label includes rule + methods)
    """
    rules = sorted(
        current_app.url_map.iter_rules(), key=lambda r: (r.endpoint or "")
    )
    groups = defaultdict(list)
    for r in rules:
        bp = (
            r.endpoint.split(".")[0]
            if r.endpoint and "." in r.endpoint
            else "root"
        )
        groups[bp].append(r)

    lines: List[str] = []
    lines.append("digraph routes {")
    lines.append('  rankdir="LR";')
    lines.append("  node [shape=box, fontsize=10];")

    # blueprint nodes
    for bp in sorted(groups.keys()):
        lines.append(
            f'  "bp::{bp}" [label="{bp}", shape=folder, style=filled, fillcolor="#f6f8fa"];'
        )

    # endpoint nodes & edges
    for bp, bp_rules in sorted(groups.items()):
        for r in bp_rules:
            ep = r.endpoint or "unknown"
            node_id = f"ep::{ep}"
            label = ep.replace('"', '\\"')
            rule = str(r).replace('"', '\\"')
            methods = (
                ",".join(sorted(r.methods))
                if getattr(r, "methods", None)
                else ""
            )
            lines.append(
                f'  "{node_id}" [label="{label}\\n{rule}\\n{methods}", shape=note];'
            )
            lines.append(f'  "bp::{bp}" -> "{node_id}";')

    lines.append("}")
    dot = "\n".join(lines)

    if output == "-":
        click.echo(dot)
    else:
        with open(output, "w", encoding="utf-8") as fh:
            fh.write(dot)
        click.echo(f"Wrote DOT to {output}")
