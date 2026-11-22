# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/cli_commands/route_graph.py

from __future__ import annotations
from pathlib import Path

from collections import defaultdict

from typing import List

import click

from flask import current_app

from flask.cli import with_appcontext

from app.diagnostics import audit_route_collisions





def _safe_ident(value: str) -> str:

    return "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in value)





@click.command("route-graph")

@click.option("--output", "-o", type=click.Path(dir_okay=False, writable=True), default="-")

@click.option("--audit/--no-audit", default=False)

@with_appcontext

def route_graph(output: str, audit: bool) -> None:

    """Emit a clustered top-down Graphviz DOT graph of the application's routing surface."""

    report = audit_route_collisions(current_app)

    collisions = set(report["cross_blueprint_collisions"].keys())

    multi_eps = set(report["multi_rule_endpoints"].keys())



    if audit:

        click.echo(

            f"[AUDIT] Total rules: {report['total_rules']} | "

            f"Multi-rule endpoints: {len(multi_eps)} | "

            f"Cross-blueprint collisions: {len(collisions)}",

            err=True,

        )

        for ep, rlist in report["multi_rule_endpoints"].items():

            click.echo(f"  [MULTI-RULE] {ep}: {rlist}", err=True)

        for path, entries in report["cross_blueprint_collisions"].items():

            click.echo(f"  [COLLISION]  {path}: {entries}", err=True)



    rules = sorted(current_app.url_map.iter_rules(), key=lambda r: (r.endpoint or "", r.rule))

    groups = defaultdict(list)

    for r in rules:
        if getattr(r, "build_only", False):
            continue

        bp = r.endpoint.split(".")[0] if r.endpoint and "." in r.endpoint else "root"

        groups[bp].append(r)



    lines: List[str] = [

        "digraph routes {",

        '  rankdir="TB";',

        '  splines="ortho";',

        "  nodesep=0.30;",

        "  ranksep=0.55;",

        '  node [shape=box, style="rounded,filled", fontname="Consolas,monospace", fontsize=10];',

        '  edge [color="#64748b", arrowsize=0.7];',

        '  "app_root" [label="PlaidBridgeOpenBankingApi\nRouting Surface", fillcolor="#1e293b", color="#38bdf8", fontcolor="#f8fafc", penwidth=2];',

    ]



    for idx, (bp, bp_rules) in enumerate(sorted(groups.items())):

        lines.extend([

            f"  subgraph cluster_{idx}_{_safe_ident(bp)} {{",

            f'    label="Blueprint: {bp} ({len(bp_rules)} rules)";',

            '    style="rounded,filled"; fillcolor="#f8fafc"; color="#cbd5e1";',

            f'    "bp::{bp}" [label="bp::{bp}", shape=folder, style=filled, fillcolor="#0284c7", color="#0369a1", fontcolor="#ffffff"];',

        ])

        by_ep = defaultdict(list)

        for r in bp_rules:

            by_ep[r.endpoint or "unknown"].append(r)



        for ep, ep_rules in sorted(by_ep.items()):

            node_id = f"ep::{ep}"

            label_ep = ep.replace('"', '\\"')

            rule_lines = []

            has_col = False

            for r in ep_rules:

                if r.rule in collisions:

                    has_col = True

                methods = ",".join(sorted(m for m in (r.methods or ()) if m not in {"HEAD", "OPTIONS"}))

                rule_lines.append(f"{str(r).replace('"', '\\"')} [{methods}]")



            if has_col:

                fill, border, font, tag = "#fee2e2", "#ef4444", "#7f1d1d", " [COLLISION]"

            elif ep in multi_eps:

                fill, border, font, tag = "#fef3c7", "#f59e0b", "#78350f", " [MULTI-RULE]"

            else:

                fill, border, font, tag = "#ffffff", "#94a3b8", "#0f172a", ""



            lines.append(f'    "{node_id}" [label="{label_ep}{tag}\n{"\n".join(rule_lines)}", fillcolor="{fill}", color="{border}", fontcolor="{font}"];')

            lines.append(f'    "bp::{bp}" -> "{node_id}";')



        lines.append("  }")

        lines.append(f'  "app_root" -> "bp::{bp}";')



    lines.append("}")

    dot = "\n".join(lines)

    if output == "-":

        click.echo(dot)

    else:

        Path(output).write_text(dot, encoding="utf-8")

        click.echo(f"Wrote DOT to {output}")

