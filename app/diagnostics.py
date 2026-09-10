# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/diagnostics.py
"""

Application diagnostics and dependency-graph helpers.



This module intentionally contains no import-time application initialization.

The functions are safe to call from the Flask application factory and from

tests using a minimal Flask instance.

"""

from __future__ import annotations


from collections.abc import Iterable

from typing import Any


from flask import Flask


def gather_diagnostics(flask_app: Flask) -> dict[str, Any]:
    """

    Collect lightweight diagnostics for a Flask application.



    The function avoids database, Redis, filesystem, and network access so it

    can safely run during application initialization and in isolated tests.

    """

    return {
        "app": flask_app.import_name,
        "name": flask_app.name,
        "debug": bool(flask_app.debug),
        "testing": bool(flask_app.testing),
        "routes": _route_count(flask_app),
        "blueprints": sorted(flask_app.blueprints),
    }


def build_dependency_graph(flask_app: Flask) -> dict[str, Any]:
    """

    Build a lightweight dependency graph from registered Flask blueprints.



    Blueprint nodes represent the application's registered route groups.

    Endpoint nodes represent routes belonging to those blueprints.



    The returned structure is intentionally JSON-serializable.

    """

    nodes: list[dict[str, str]] = []

    edges: list[dict[str, str]] = []

    app_node_id = "app"

    nodes.append(
        {
            "id": app_node_id,
            "label": flask_app.name,
            "type": "application",
        }
    )

    blueprint_names = sorted(flask_app.blueprints)

    for blueprint_name in blueprint_names:
        blueprint_node_id = f"blueprint:{blueprint_name}"

        nodes.append(
            {
                "id": blueprint_node_id,
                "label": blueprint_name,
                "type": "blueprint",
            }
        )

        edges.append(
            {
                "source": app_node_id,
                "target": blueprint_node_id,
                "type": "registers",
            }
        )

    for rule in flask_app.url_map.iter_rules():
        endpoint = str(rule.endpoint)

        blueprint_name = endpoint.split(".", 1)[0]

        if blueprint_name not in flask_app.blueprints:
            continue

        endpoint_node_id = f"endpoint:{endpoint}"

        nodes.append(
            {
                "id": endpoint_node_id,
                "label": endpoint,
                "type": "endpoint",
            }
        )

        edges.append(
            {
                "source": f"blueprint:{blueprint_name}",
                "target": endpoint_node_id,
                "type": "exposes",
            }
        )

    nodes = _unique_nodes(nodes)

    edges = _unique_edges(edges)

    return {
        "nodes": nodes,
        "edges": edges,
        "dot": _to_dot(nodes, edges),
    }


def _route_count(flask_app: Flask) -> int:
    """Return the number of registered URL rules."""

    return sum(1 for _ in flask_app.url_map.iter_rules())


def _unique_nodes(nodes: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    """Remove duplicate nodes while preserving deterministic ordering."""

    unique: dict[str, dict[str, str]] = {}

    for node in nodes:
        unique[node["id"]] = node

    return [unique[node_id] for node_id in sorted(unique)]


def _unique_edges(edges: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    """Remove duplicate edges while preserving deterministic ordering."""

    unique: dict[tuple[str, str, str], dict[str, str]] = {}

    for edge in edges:
        key = (
            edge["source"],
            edge["target"],
            edge["type"],
        )

        unique[key] = edge

    return [unique[key] for key in sorted(unique)]


def _to_dot(
    nodes: Iterable[dict[str, str]],
    edges: Iterable[dict[str, str]],
) -> str:
    """Render the dependency graph as valid Graphviz DOT."""

    lines = [
        "digraph application {",
        '  rankdir="LR";',
    ]

    for node in nodes:
        node_id = _dot_escape(node["id"])

        label = _dot_escape(node["label"])

        lines.append(f'  "{node_id}" [label="{label}"];')

    for edge in edges:
        source = _dot_escape(edge["source"])

        target = _dot_escape(edge["target"])

        lines.append(f'  "{source}" -> "{target}";')

    lines.append("}")

    return "\n".join(lines)


def _dot_escape(value: str) -> str:
    """Escape a value for use inside a Graphviz quoted string."""

    return (
        str(value)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
    )
