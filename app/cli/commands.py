# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/cli/commands.py

import logging
import sys

import click

# --- Telemetry & Utility Mockups/Constants ---
# In a real application, these would be imported from your services/telemetry module.

# Setup basic logging for demonstration
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Constants (Mocked as if imported from app.constants.telemetry_keys)
REDIS_DEFAULT_TTL = 300  # Default 5-minute TTL
REDIS_ROUTE_COUNT_TTL = REDIS_DEFAULT_TTL
REDIS_VALIDATE_RELATIONSHIPS_TTL = REDIS_DEFAULT_TTL  # New constant for clarity

TTL_ROUTE_COUNT_KEY = "ttl:boot:route_count"  # Key constant
TTL_VALIDATE_RELATIONSHIPS_KEY = "ttl:boot:validate_relationships"  # Key constant


# Mock Functions (for demonstration)
def get_redis_client():
    """Simulates getting a Redis client."""
    return object()


def flush_emit_queue(client):
    """Simulates flushing the queued TTL emits."""
    return 5


def ttl_emit(**kwargs):
    """Mock function for keyword-only TTL emission."""
    pass


def get_total_routes():
    """Mock function for route count."""
    return 142


def get_route_map_data():
    """Mock function for route data."""
    return [
        {"endpoint": "index", "rule": "/", "methods": "GET"},
        {"endpoint": "admin.console_view", "rule": "/admin/console", "methods": "GET"},
        {"endpoint": "api.users", "rule": "/api/v1/users", "methods": "POST, GET"},
    ]


def validate_relationships():
    """Mock function for the actual relationship validation logic."""
    logger.info("Starting complex data relationship validation...")


# --- Helper Function ---
def emit_ttl_safe(client, key, status, ttl):
    """
    Refactors the guarded flush and keyword-only TTL emit logic.
    Ensures no telemetry failure can crash the CLI command.
    """
    if not client:
        logger.debug(f"Skipping TTL emit for {key}: No Redis client available.")
        return

    try:
        # Pulled in flush_emit_queue(client)
        count = flush_emit_queue(client)
        logger.info(f"Flushed {count} queued TTL emits.")

        # Keyword-only TTL emit with constants
        ttl_emit(client=client, key=key, status=status, ttl=ttl)
        logger.info(f"TTL emit {key}={status} succeeded.")
    except Exception as e:
        logger.warning(f"Telemetry emit for {key} failed: {e}")


# --- Click Commands ---


@click.group()
def cli():
    """Cockpit-aligned CLI commands for the application."""
    pass


@cli.command("cockpit:route-map")
def route_map_command():
    """Displays the current route map and emits a TTL telemetry pulse."""
    total_routes = get_total_routes()
    route_data = get_route_map_data()

    # 1. Uniform Click Output
    click.echo("\n📡 Route Map Constellation:\n")
    click.echo(f"Total Routes: {total_routes}\n")

    # Broken pipe guard
    try:
        for route in route_data:
            click.echo(f"  [{route['methods']:<10}] {route['rule']:<30} -> {route['endpoint']}")
        click.echo("")
    except BrokenPipeError:
        sys.exit(0)

    # Use the new safe helper function
    client = get_redis_client()
    emit_ttl_safe(
        client=client,
        key=TTL_ROUTE_COUNT_KEY,
        status=str(total_routes),
        ttl=REDIS_ROUTE_COUNT_TTL,
    )


@cli.command("cockpit:validate-relationships")
def validate_relationships_command():
    """Runs data relationship validation and emits a TTL telemetry pulse."""

    validate_relationships()

    # 1. Uniform Click Output
    click.echo("✅ Relationship validation trace emitted.")

    # Use the new safe helper function
    client = get_redis_client()
    emit_ttl_safe(
        client=client,
        key=TTL_VALIDATE_RELATIONSHIPS_KEY,
        status="success",
        ttl=REDIS_VALIDATE_RELATIONSHIPS_TTL,
    )


if __name__ == "__main__":
    cli()
