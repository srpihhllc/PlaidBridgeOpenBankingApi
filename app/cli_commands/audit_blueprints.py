# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/cli_commands/audit_blueprints.py

import json
import sys
from datetime import UTC, datetime
from typing import Any

import click
import requests
from flask import current_app

from app.telemetry.ttl_emit import ttl_emit
from app.utils.redis_utils import get_redis_client


def _fetch_blueprints_via_http(url: str) -> dict[str, Any]:
    resp = requests.get(url, timeout=6)
    resp.raise_for_status()
    return resp.json()


def _introspect_blueprints_local(app) -> dict[str, Any]:
    # Mirror the /debug/blueprints payload structure
    return {
        name: {
            "url_prefix": bp.url_prefix,
            "import_name": bp.import_name,
        }
        for name, bp in app.blueprints.items()
    }


def _normalize_prefix(prefix: str) -> str:
    """Ensure leading slash, strip trailing slash (except for root)."""
    if not prefix:
        return ""
    if prefix == "/":
        return "/"
    p = prefix if prefix.startswith("/") else f"/{prefix}"
    if p.endswith("/"):
        p = p[:-1]
    return p


def _normalize_expected_map(raw_expected: dict[str, Any]) -> tuple[dict[str, str], dict[str, bool]]:
    """
    Accepts either:
      - { name: "/prefix" }
      - { name: { "prefix": "/prefix", "required": true } }
    Returns (expected_prefixes, required_flags)
    """
    prefixes = {}
    required = {}
    for name, val in raw_expected.items():
        if isinstance(val, str):
            prefixes[name] = _normalize_prefix(val)
            required[name] = True
        elif isinstance(val, dict):
            p = _normalize_prefix(val.get("prefix", ""))
            if not p:
                raise ValueError(f"Expected map for '{name}' missing 'prefix'.")
            prefixes[name] = p
            required[name] = bool(val.get("required", True))
        else:
            raise ValueError(f"Invalid expected entry for '{name}': {val}")
    return prefixes, required


def _compare(
    expected_prefixes: dict[str, str],
    required_flags: dict[str, bool],
    actual: dict[str, Any],
) -> dict[str, Any]:
    drift = []
    missing = []
    extras = []

    # Normalize actual prefixes
    actual_norm = {
        name: {
            **meta,
            "url_prefix": _normalize_prefix(meta.get("url_prefix")),
        }
        for name, meta in actual.items()
    }

    # Missing + drift
    for name, exp_prefix in expected_prefixes.items():
        if name not in actual_norm:
            if required_flags.get(name, True):
                missing.append(name)
            continue
        act_prefix = actual_norm[name].get("url_prefix")
        if act_prefix != exp_prefix:
            drift.append({"name": name, "expected": exp_prefix, "actual": act_prefix})

    # Extras
    for name in actual_norm.keys():
        if name not in expected_prefixes:
            extras.append(name)

    return {
        "drift": drift,
        "missing": missing,
        "extras": extras,
        "actual_norm": actual_norm,
    }


def init_app(app):
    @app.cli.command("cockpit.audit-blueprints")
    @click.option(
        "--use-http",
        is_flag=True,
        default=False,
        help=(
            "Fetch via HTTP from /admin/cockpit/debug/blueprints instead of local " "introspection."
        ),
    )
    @click.option(
        "--expect",
        type=str,
        default=None,
        help=(
            "JSON mapping of expected blueprints. Accepts {name: prefix} or "
            "{name: {prefix, required}}. Overrides app.config['EXPECTED_BLUEPRINTS'] "
            "if provided."
        ),
    )
    @click.option(
        "--fail-on-extras/--no-fail-on-extras",
        default=False,
        help="Treat unexpected blueprints as failures.",
    )
    @click.option(
        "--json",
        "print_json",
        is_flag=True,
        default=False,
        help="Print the full audit payload as JSON to stdout.",
    )
    @click.option(
        "--tile-key",
        type=str,
        default="tile:cockpit:blueprints:summary",
        help="Redis hash key for dashboard tile summary.",
    )
    @click.option(
        "--last-key",
        type=str,
        default="audit:blueprints:last",
        help="Redis key for storing last audit JSON.",
    )
    @click.option(
        "--ttl-key",
        type=str,
        default="ttl:cockpit:blueprints:audit",
        help="Redis TTL pulse key.",
    )
    @click.option(
        "--tile-ttl",
        type=int,
        default=900,
        help="TTL (seconds) for dashboard tile summary and last audit snapshot.",
    )
    def audit_blueprints(
        use_http,
        expect,
        fail_on_extras,
        print_json,
        tile_key,
        last_key,
        ttl_key,
        tile_ttl,
    ):
        """
        Audit registered blueprints for prefix drift and presence.
        Emits TTL-backed status, stores the last audit to Redis, and updates a cockpit tile summary.

        Exit codes:
          0 = OK
          1 = Drift or missing (or extras when --fail-on-extras)
          2 = Transport or unexpected error
        """
        r = get_redis_client()

        # Load expected map
        try:
            if expect:
                raw_expected = json.loads(expect)
            else:
                raw_expected = current_app.config.get("EXPECTED_BLUEPRINTS", {})
            if not isinstance(raw_expected, dict):
                raise ValueError(
                    "EXPECTED_BLUEPRINTS must be a dict of {name: prefix} or "
                    "{name: {prefix, required}}."
                )
            expected_prefixes, required_flags = _normalize_expected_map(raw_expected)
        except Exception as e:
            click.echo(f"[ERROR] Could not load expected mapping: {e}", err=True)
            ttl_emit(key=ttl_key, status="error", client=r, ttl=300)
            sys.exit(2)

        # Fetch actual registry
        try:
            if use_http:
                base = current_app.config.get("COCKPIT_BASE_URL")
                if not base:
                    raise RuntimeError("COCKPIT_BASE_URL not set; cannot use --use-http.")
                url = base.rstrip("/") + "/admin/cockpit/debug/blueprints"
                actual = _fetch_blueprints_via_http(url)
            else:
                actual = _introspect_blueprints_local(current_app)
        except Exception as e:
            click.echo(f"[ERROR] Failed to fetch blueprints: {e}", err=True)
            ttl_emit(key=ttl_key, status="error", client=r, ttl=300)
            sys.exit(2)

        # Compare
        result = _compare(expected_prefixes, required_flags, actual)

        # Prepare summary
        ok = (
            not result["drift"]
            and not result["missing"]
            and (not fail_on_extras or not result["extras"])
        )
        status = "success" if ok else "drift"

        now = datetime.now(UTC)
        now_iso = now.isoformat()
        now_epoch = int(now.timestamp())

        summary = {
            "status": status,
            "counts": {
                "expected": len(expected_prefixes),
                "actual": len(result["actual_norm"]),
                "missing": len(result["missing"]),
                "drift": len(result["drift"]),
                "extras": len(result["extras"]),
            },
            "expected": expected_prefixes,
            "actual": result["actual_norm"],
            "result": {
                "missing": result["missing"],
                "drift": result["drift"],
                "extras": result["extras"],
            },
            "timestamps": {
                "last_audit_iso": now_iso,
                "last_audit_epoch": now_epoch,
                "tile_ttl_seconds": tile_ttl,
            },
        }

        # Emit TTL + store last audit + update cockpit tile
        try:
            ttl_emit(key=ttl_key, status=status, client=r, ttl=300)

            # Store the full JSON (for deep dive panel)
            key = last_key
            value = json.dumps(summary, ensure_ascii=False)

            client = getattr(current_app, "redis_client", None) or get_redis_client()
            if client:
                try:
                    client.setex(key, tile_ttl, value)
                except Exception as e:
                    current_app.logger.error(
                        f"[cli_commands.audit_blueprints] Redis setex failed for " f"{key} — {e}"
                    )
            else:
                current_app.logger.error(
                    f"[cli_commands.audit_blueprints] Redis unavailable — skipping "
                    f"setex for {key}"
                )

            # Minimal tile hash for the dashboard
            r.hset(
                tile_key,
                mapping={
                    "status": status,
                    "expected": summary["counts"]["expected"],
                    "actual": summary["counts"]["actual"],
                    "missing": summary["counts"]["missing"],
                    "drift": summary["counts"]["drift"],
                    "extras": summary["counts"]["extras"],
                    "last_audit_iso": now_iso,
                    "last_audit_epoch": now_epoch,
                },
            )
            r.expire(tile_key, tile_ttl)
        except Exception as e:
            click.echo(f"[WARN] Failed to write audit result to Redis: {e}", err=True)

        # Optional JSON output for CI/pipelines
        if print_json:
            click.echo(json.dumps(summary, ensure_ascii=False))
        else:
            # Human-friendly report
            click.echo("=== Blueprint Audit ===")
            click.echo(f"Status: {status}")
            click.echo(f"- Expected count: {summary['counts']['expected']}")
            click.echo(f"- Actual count:    {summary['counts']['actual']}")
            click.echo(f"- Missing:         {summary['counts']['missing']}")
            click.echo(f"- Drift:           {summary['counts']['drift']}")
            click.echo(f"- Extras:          {summary['counts']['extras']}")
            click.echo(f"- Last audit:      {now_iso} (epoch {now_epoch})")

            if summary["result"]["missing"]:
                click.echo("\nMissing blueprints:")
                for name in summary["result"]["missing"]:
                    click.echo(f"  - {name} (expected prefix: {expected_prefixes.get(name)})")

            if summary["result"]["drift"]:
                click.echo("\nPrefix drift detected:")
                for d in summary["result"]["drift"]:
                    click.echo(
                        f"  - {d['name']}: expected='{d['expected']}' " f"actual='{d['actual']}'"
                    )

            if summary["result"]["extras"]:
                click.echo("\nUnexpected blueprints present:")
                for name in summary["result"]["extras"]:
                    act_pfx = summary["actual"].get(name, {}).get("url_prefix")
                    click.echo(f"  - {name} (prefix: {act_pfx})")

        sys.exit(0 if ok else 1)
