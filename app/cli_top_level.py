# =============================================================================
# FILE: app/cli_top_level.py
#
# DESCRIPTION:
#   Executive‑grade CLI topology for PlaidBridgeOpenBankingApi.
#   Provides:
#     • audit-templates (endpoint → template mapping)
#     • db upgrade/downgrade with telemetry
#     • hello (telemetry test)
#   Includes safe Alembic revision reader compatible with all Flask-Migrate versions.
# =============================================================================

import inspect
import json
import re

import click
from flask import Flask, current_app
from flask.cli import with_appcontext

# Flask-Migrate only exposes upgrade/downgrade; revision must be read via Alembic.
from flask_migrate import upgrade, downgrade
from alembic.migration import MigrationContext

# SQLAlchemy instance (adjust if your db lives elsewhere)
from app.extensions import db

from app.telemetry.ttl_emit import emit_boot_trace
from app.utils.redis_utils import get_redis_client

# Regex to extract template names from render_template() calls
TEMPLATE_RE = re.compile(r"render_template\(\s*['\"]([^'\"]+)['\"]")


# -------------------------------------------------------------------------
# Safe Alembic Revision Reader
# -------------------------------------------------------------------------
def get_current_revision() -> str | None:
    """
    Programmatically fetches the current Alembic database revision.
    Works across all Flask-Migrate versions.
    """
    with db.engine.connect() as connection:
        context = MigrationContext.configure(connection)
        return context.get_current_revision()


# -------------------------------------------------------------------------
# Template Audit Command
# -------------------------------------------------------------------------
@click.command("audit-templates")
@with_appcontext
def audit_templates() -> None:
    """
    Scans all Flask view functions for render_template() calls
    and outputs a JSON mapping of endpoint → rule → templates.
    """
    mapping = []

    for rule in current_app.url_map.iter_rules():
        func = current_app.view_functions.get(rule.endpoint)
        templates = []

        if func:
            try:
                src = inspect.getsource(func)
                templates = TEMPLATE_RE.findall(src)
            except (OSError, TypeError):
                pass

        mapping.append(
            {
                "endpoint": rule.endpoint,
                "rule": rule.rule,
                "methods": sorted(
                    m for m in rule.methods if m not in ("HEAD", "OPTIONS")
                ),
                "templates": templates,
            }
        )

    click.echo(json.dumps(mapping, indent=2))


# -------------------------------------------------------------------------
# CLI Registrar
# -------------------------------------------------------------------------
def register_cli_commands(app: Flask) -> None:
    """
    Registers custom CLI commands for the application:
      • db upgrade/downgrade with telemetry
      • hello command
      • audit-templates command
    """
    redis_client = get_redis_client()
    if not redis_client:
        app.logger.warning("❌ No Redis client available for CLI telemetry.")

    # ------------------------------
    # DB Migration Command Group
    # ------------------------------
    @app.cli.group()
    def db() -> None:
        """Perform database migrations."""
        pass

    # ------------------------------
    # DB Upgrade
    # ------------------------------
    @db.command("upgrade")
    def upgrade_with_telemetry() -> None:
        """Run database migrations and emit telemetry."""
        app.logger.info("🛠 Starting database upgrade with telemetry...")

        try:
            initial = get_current_revision() or "base"
        except Exception:
            initial = "unknown"

        try:
            emit_boot_trace(
                domain="migration",
                event="upgrade",
                detail="start",
                value=f"from_rev:{initial}",
                status="ok",
                client=redis_client,
                ttl=60,
            )

            upgrade()

            final = get_current_revision() or "base"
            app.logger.info(f"✅ Upgrade successful: to {final}")

            emit_boot_trace(
                domain="migration",
                event="upgrade",
                detail="complete",
                value=f"success:to_rev:{final}",
                status="ok",
                client=redis_client,
                ttl=300,
            )

        except Exception as e:
            app.logger.error(f"❌ Upgrade failed: {e}")
            failed = get_current_revision() or "unknown"

            emit_boot_trace(
                domain="migration",
                event="upgrade",
                detail="failure",
                value=f"failure:from_rev:{failed}:err:{str(e)[:64]}",
                status="error",
                client=redis_client,
                ttl=300,
            )
            raise

    # ------------------------------
    # DB Downgrade
    # ------------------------------
    @db.command("downgrade")
    @click.argument("revision", default="-1")
    def downgrade_with_telemetry(revision: str) -> None:
        """Rollback database migrations and emit telemetry."""
        app.logger.info(f"🛠 Starting database downgrade to {revision}...")

        try:
            initial = get_current_revision() or "base"
        except Exception:
            initial = "unknown"

        try:
            emit_boot_trace(
                domain="migration",
                event="downgrade",
                detail="start",
                value=f"from_rev:{initial}:to_rev:{revision}",
                status="ok",
                client=redis_client,
                ttl=60,
            )

            downgrade(revision)

            final = get_current_revision() or "base"
            app.logger.info(f"✅ Downgrade successful: to {final}")

            emit_boot_trace(
                domain="migration",
                event="downgrade",
                detail="complete",
                value=f"success:to_rev:{final}",
                status="ok",
                client=redis_client,
                ttl=300,
            )

        except Exception as e:
            app.logger.error(f"❌ Downgrade failed: {e}")
            failed = get_current_revision() or "unknown"

            emit_boot_trace(
                domain="migration",
                event="downgrade",
                detail="failure",
                value=f"failure:from_rev:{failed}:err:{str(e)[:64]}",
                status="error",
                client=redis_client,
                ttl=300,
            )
            raise

    # ------------------------------
    # Hello Command
    # ------------------------------
    @app.cli.command("hello")
    def hello_command() -> None:
        """Example command to say hello with telemetry."""
        app.logger.info("👋 Hello, World!")

        try:
            emit_boot_trace(
                domain="cli",
                event="hello_command",
                detail="run",
                value="success",
                status="ok",
                client=redis_client,
                ttl=60,
            )
        except Exception as e:
            app.logger.warning(f"⚠️ Telemetry emit failed: {e}")
            emit_boot_trace(
                domain="cli",
                event="hello_command",
                detail="run",
                value=f"failure:err:{str(e)[:64]}",
                status="error",
                client=None,
                ttl=60,
            )

    # ------------------------------
    # Register audit-templates
    # ------------------------------
    app.cli.add_command(audit_templates)

    # ------------------------------
    # Boot Telemetry
    # ------------------------------
    emit_boot_trace(
        domain="boot",
        event="cli",
        detail="migrations",
        value="registered",
        status="ok",
        client=redis_client,
        ttl=300,
    )

    app.logger.info("✅ CLI commands registered with telemetry.")
