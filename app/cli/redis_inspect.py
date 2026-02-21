# app/cli/redis_inspect.py

import click
from dotenv import load_dotenv

from app.utils.redis_utils import get_redis_client

load_dotenv()


@click.command("view-lockouts")
def view_lockouts():
    """List current login failure keys and their TTLs."""
    redis_conn = get_redis_client()
    keys = redis_conn.keys("login_failures:*")
    if not keys:
        click.echo("✅ No active lockouts.")
        return
    for key in keys:
        ttl = redis_conn.ttl(key)
        value = redis_conn.get(key)
        click.echo(f"{key} → {value} failures, {ttl} seconds remaining")


@click.command("purge-lockouts")
def purge_lockouts():
    """Delete all login failure tracking keys."""
    redis_conn = get_redis_client()
    keys = redis_conn.keys("login_failures:*")
    if not keys:
        click.echo("✅ Nothing to delete.")
        return
    for key in keys:
        redis_conn.delete(key)
    click.echo(f"🧹 Deleted {len(keys)} lockout keys.")


@click.command("report-ttl")
def report_ttl():
    """Print all Redis keys and their TTLs."""
    redis_conn = get_redis_client()
    keys = redis_conn.keys("*")
    if not keys:
        click.echo("📭 No Redis keys found.")
        return
    for key in keys:
        ttl = redis_conn.ttl(key)
        click.echo(f"{key} → TTL: {ttl if ttl >= 0 else '∞'}")


def init_app(app):
    app.cli.add_command(view_lockouts)
    app.cli.add_command(purge_lockouts)
    app.cli.add_command(report_ttl)
