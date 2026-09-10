# =============================================================================
# FILE: app/cli_commands/ttl_audit.py
# DESCRIPTION: Cockpit-grade TTL audit engine with dynamic Redis type decoding.
# =============================================================================

import click
from flask.cli import with_appcontext

from app.telemetry.ttl_emit import emit_schema_trace
from app.utils.redis_utils import get_redis_client


@click.command("ttl_audit")
@click.option(
    "--domain",
    default="boot",
    help="Telemetry domain to audit (boot, cli, migration, etc.)",
)
@with_appcontext
def ttl_audit(domain: str):
    """
    Scans Redis for all ttl:{domain}:* keys, dynamically determines their
    underlying Redis data type, extracts payload data, and audits TTL states.
    Emits a schema-compliant summary trace back into Redis for observability.
    """
    redis_client = get_redis_client()
    if not redis_client:
        click.echo("❌ Redis client not configured.")
        return

    pattern = f"ttl:{domain}:*"

    # Production-safe SCAN instead of KEYS
    keys = []
    cursor = 0
    try:
        while True:
            cursor, partial = redis_client.scan(
                cursor=cursor, match=pattern, count=100
            )
            keys.extend(partial)
            if cursor == 0:
                break
    except Exception as e:
        click.echo(f"❌ SCAN failed for pattern {pattern}: {e}")
        return

    if not keys:
        click.echo(f"⚠️ No telemetry keys found under {pattern}")
        return

    click.echo(
        f"📡 Found {len(keys)} telemetry keys under domain '{domain}':\n"
    )

    readable = 0
    unreadable = 0
    status_counts = {}

    for key_bytes in keys:
        key = (
            key_bytes.decode("utf-8")
            if isinstance(key_bytes, bytes)
            else key_bytes
        )

        try:
            ttl = redis_client.ttl(key)
            key_type = redis_client.type(key)
            if isinstance(key_type, bytes):
                key_type = key_type.decode("utf-8")

            value_summary = None
            status = "unknown"

            # ------------------------------
            # Dynamic Type Decoding
            # ------------------------------
            if key_type == "string":
                val = redis_client.get(key)
                if val:
                    decoded = (
                        val.decode("utf-8")
                        if isinstance(val, bytes)
                        else str(val)
                    )
                    value_summary = decoded
                    status = "string"

            elif key_type == "hash":
                fields = redis_client.hgetall(key)
                decoded = {
                    (k.decode("utf-8") if isinstance(k, bytes) else k): (
                        v.decode("utf-8") if isinstance(v, bytes) else v
                    )
                    for k, v in fields.items()
                }
                value_summary = f"HashData({decoded})"
                status = "hash"

            elif key_type == "list":
                elements = redis_client.lrange(key, 0, -1)
                value_summary = f"ListData(length={len(elements)})"
                status = "list"

            elif key_type == "set":
                members = redis_client.smembers(key)
                value_summary = f"SetData(size={len(members)})"
                status = "set"

            # ------------------------------
            # Output Formatting
            # ------------------------------
            if value_summary is not None:
                readable += 1
                status_counts[status] = status_counts.get(status, 0) + 1
                status_str = f"Readable → {value_summary[:70]}"
            else:
                unreadable += 1
                status_counts["unreadable"] = (
                    status_counts.get("unreadable", 0) + 1
                )
                status_str = "Unreadable (unknown type)"

            click.echo(f"🔹 {key}")
            click.echo(
                f"    TTL: {ttl}s | Type: {key_type} | Status: {status_str}\n"
            )

        except Exception as e:
            unreadable += 1
            status_counts["error"] = status_counts.get("error", 0) + 1
            click.echo(f"🔹 {key}")
            click.echo(
                f"    TTL: Error | Status: unreadable (Exception: {str(e)[:40]})\n"
            )

    # ------------------------------
    # Summary
    # ------------------------------
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
        meta={"domain": domain, "status_counts": status_counts},
    )

    click.echo(f"\n✨ Emitted audit summary trace for domain '{domain}'")
