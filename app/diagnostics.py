# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/diagnostics.py

"""Application diagnostics and dependency-graph helpers."""

from __future__ import annotations

from collections import defaultdict

from collections.abc import Iterable

from typing import Any

from flask import Flask





def gather_diagnostics(flask_app: Flask) -> dict[str, Any]:

    return {

        "app": flask_app.import_name,

        "name": flask_app.name,

        "debug": bool(flask_app.debug),

        "testing": bool(flask_app.testing),

        "routes": _route_count(flask_app),

        "blueprints": sorted(flask_app.blueprints),

    }





def audit_route_collisions(flask_app: Flask) -> dict[str, Any]:

    path_to_blueprints: dict[str, list[dict[str, Any]]] = defaultdict(list)

    endpoint_rules: dict[str, list[str]] = defaultdict(list)



    for rule in flask_app.url_map.iter_rules():

        endpoint = str(rule.endpoint)

        if endpoint == "static" or getattr(rule, "build_only", False):

            continue

        bp_name = endpoint.split(".", 1)[0] if "." in endpoint else "app"

        methods = sorted(m for m in (rule.methods or ()) if m not in {"HEAD", "OPTIONS"})

        endpoint_rules[endpoint].append(rule.rule)

        path_to_blueprints[rule.rule].append({

            "blueprint": bp_name,

            "endpoint": endpoint,

            "methods": methods,

        })



    multi_rule_endpoints = {

        ep: sorted(rules) for ep, rules in sorted(endpoint_rules.items()) if len(rules) > 1

    }

    cross_blueprint_collisions = {

        path: entries

        for path, entries in sorted(path_to_blueprints.items())

        if len({e["blueprint"] for e in entries}) > 1

    }

    return {

        "total_rules": _route_count(flask_app),

        "multi_rule_endpoints": multi_rule_endpoints,

        "cross_blueprint_collisions": cross_blueprint_collisions,

    }





def build_dependency_graph(flask_app: Flask) -> dict[str, Any]:

    nodes: list[dict[str, str]] = [{"id": "app", "label": flask_app.name, "type": "application"}]

    edges: list[dict[str, str]] = []



    for blueprint_name in sorted(flask_app.blueprints):

        bp_id = f"blueprint:{blueprint_name}"

        nodes.append({"id": bp_id, "label": blueprint_name, "type": "blueprint"})

        edges.append({"source": "app", "target": bp_id, "type": "registers"})



    for rule in flask_app.url_map.iter_rules():

        endpoint = str(rule.endpoint)

        bp_name = endpoint.split(".", 1)[0]

        if bp_name not in flask_app.blueprints:

            continue

        ep_id = f"endpoint:{endpoint}"

        nodes.append({"id": ep_id, "label": endpoint, "type": "endpoint"})

        edges.append({"source": f"blueprint:{bp_name}", "target": ep_id, "type": "exposes"})



    nodes = _unique_nodes(nodes)

    edges = _unique_edges(edges)

    return {"nodes": nodes, "edges": edges, "dot": _to_dot(nodes, edges)}





def _route_count(flask_app: Flask) -> int:

    return sum(1 for _ in flask_app.url_map.iter_rules())





def _unique_nodes(nodes: Iterable[dict[str, str]]) -> list[dict[str, str]]:

    unique = {n["id"]: n for n in nodes}

    return [unique[k] for k in sorted(unique)]





def _unique_edges(edges: Iterable[dict[str, str]]) -> list[dict[str, str]]:

    unique = {(e["source"], e["target"], e["type"]): e for e in edges}

    return [unique[k] for k in sorted(unique)]





def _safe_ident(value: str) -> str:

    return "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in value)





def _dot_escape(value: str) -> str:

    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")





def _to_dot(nodes: Iterable[dict[str, str]], edges: Iterable[dict[str, str]]) -> str:

    node_list, edge_list = list(nodes), list(edges)

    app_nodes = [n for n in node_list if n.get("type") == "application"]

    bp_nodes = [n for n in node_list if n.get("type") == "blueprint"]

    ep_nodes = [n for n in node_list if n.get("type") == "endpoint"]



    eps_by_bp: dict[str, list[dict[str, str]]] = defaultdict(list)

    for ep in ep_nodes:

        lbl = ep.get("label", "")

        eps_by_bp[lbl.split(".", 1)[0] if "." in lbl else "root"].append(ep)



    lines = [

        "digraph application {",

        '  rankdir="TB";',

        '  splines="ortho";',

        "  nodesep=0.30;",

        "  ranksep=0.55;",

        '  node [shape=box, style="rounded,filled", fontname="Consolas,monospace", fontsize=10];',

        '  edge [color="#64748b", arrowsize=0.7];',

    ]

    for n in app_nodes:

        lines.append(f'  "{_dot_escape(n["id"])}" [label="{_dot_escape(n["label"])}", fillcolor="#1e293b", color="#38bdf8", fontcolor="#f8fafc", penwidth=2];')



    for idx, bp in enumerate(bp_nodes):

        bp_name = bp["label"]

        bp_id = _dot_escape(bp["id"])

        bp_lbl = _dot_escape(bp_name)

        cluster_eps = eps_by_bp.get(bp_name, [])

        lines.extend([

            f"  subgraph cluster_{idx}_{_safe_ident(bp_name)} {{",

            f'    label="Blueprint: {bp_lbl} ({len(cluster_eps)})";',

            '    style="rounded,filled"; fillcolor="#f8fafc"; color="#cbd5e1";',

            f'    "{bp_id}" [label="bp::{bp_lbl}", fillcolor="#0284c7", color="#0369a1", fontcolor="#ffffff"];',

        ])

        for ep in cluster_eps:

            lines.append(f'    "{_dot_escape(ep["id"])}" [label="{_dot_escape(ep["label"])}", fillcolor="#ffffff", color="#94a3b8", fontcolor="#0f172a"];')

        lines.append("  }")



    for e in edge_list:

        lines.append(f'  "{_dot_escape(e["source"])}" -> "{_dot_escape(e["target"])}";')

    lines.append("}")

    return "\n".join(lines)

