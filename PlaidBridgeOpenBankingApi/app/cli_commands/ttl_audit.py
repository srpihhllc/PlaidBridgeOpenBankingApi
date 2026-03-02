# =============================================================================
# FILE: app/cli_commands/ttl_audit.py
# DESCRIPTION: CLI command to audit Redis TTL telemetry keys by domain.
#              Uses @with_appcontext to ensure a safe Flask context.
# =============================================================================

from collections import defaultdict

import click
from flask import current_app
from flask.cli import with_appcontext

from app.telemetry.ttl_emit import emit_schema_trace


@click.command("ttl_audit")
@click.option(
    "--domain",
    default="boot",
    help="Telemetry domain to audit (boot, cli, migration, etc.)",
)
@with_appcontext
def ttl_audit(domain: str):
    """
    Scans Redis for all ttl:{domain}:* keys and summarizes their health.
    Emits a schema-compliant summary trace back into Redis for observability.
    """
    redis_client = getattr(current_app, "redis_client", None)
    if not redis_client:
        click.echo("❌ Redis client not configured.")
        return

    try:
        pattern = f"ttl:{domain}:*"
        keys = redis_client.keys(pattern)
        if not keys:
            click.echo(f"⚠️ No telemetry keys found under {pattern}")
            return

        click.echo(f"📡 Found {len(keys)} telemetry keys under domain '{domain}':\n")

        status_counts = defaultdict(int)

        for key in sorted(keys):
            ttl = redis_client.ttl(key)
            value = redis_client.get(key)
            status = "unknown"

            if value:
                try:
                    decoded = value.decode("utf-8")
                    status = decoded.split(":")[-1]
                except Exception:
                    status = "unreadable"

            status_counts[status] += 1

            click.echo(f"🔹 {key}")
            click.echo(f"    TTL: {ttl}s | Status: {status}")
            click.echo("")

        # Summary
        click.echo("📊 Telemetry Summary:")
        for status, count in status_counts.items():
            click.echo(f" - {status}: {count} keys")

        # Emit schema-compliant audit summary trace
        emit_schema_trace(
            domain="cli",
            event="ttl_audit",
            detail="summary",
            value=f"keys:{len(keys)}",
            status="ok",
            ttl=300,
            client=redis_client,
            meta={"domain": domain, "status_counts": dict(status_counts)},
        )
        click.echo(f"\n✨ Emitted audit summary trace for domain '{domain}'")

    except Exception as e:
        click.echo(f"❌ Failed to audit Redis TTL keys: {e}")
        # Emit schema-compliant error trace
        emit_schema_trace(
            domain="cli",
            event="ttl_audit",
            detail="error",
            value="failure",
            status="error",
            ttl=300,
            client=redis_client,
            meta={"domain": domain, "error": str(e)},
        )

def run():
    """
    Compatibility wrapper so scripts/audit.py can call ttl_audit.run().
    The module defines a Click command object named `ttl_audit` (decorated
    with @click.command). This wrapper finds the command's callback and
    invokes it inside a Flask app context. Default domain is 'boot'.
    """
    # Lazy import to avoid overhead at import time
    try:
        from app import create_app
    except Exception:
        create_app = None  # type: ignore

    # The name `ttl_audit` in this module is a Click Command object.
    cmd = globals().get("ttl_audit")
    callback = getattr(cmd, "callback", None)

    def _call(domain="boot"):
        if callable(callback):
            try:
                callback(domain)  # runs with the current app context (if present)
            except TypeError:
                # if signature mismatch, try no-arg invocation
                try:
                    callback()
                except Exception as e:
                    print(f"[ERROR] ttl_audit callback raised: {e}")
        else:
            print("[SKIP] ttl_audit callback not found — skipping.")

    # Try to call inside an existing app context first
    try:
        _call("boot")
        return
    except RuntimeError:
        # No current_app; create one and run inside its context
        if not create_app:
            print("[SKIP] create_app unavailable; cannot run ttl_audit.")
            return
        app = create_app()
        with app.app_context():
            _call("boot")
