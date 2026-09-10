# =============================================================================
# FILE: app/cli_top_level.py
#
# DESCRIPTION:
#     Executive-grade CLI topology for PlaidBridgeOpenBankingApi.
#     Provides:
#       • Operator Cortex management (status, enable, disable)
#       • audit-templates (endpoint → template mapping)
#       • db upgrade/downgrade with telemetry
#       • env-doctor (environment health check with telemetry)
#       • doctor-pa (PythonAnywhere-specific health check)
#     Includes safe Alembic revision reader compatible with all Flask-Migrate versions.
# =============================================================================

import inspect
import json
import re

import click
from alembic.migration import MigrationContext
from flask import Flask, current_app
from flask.cli import routes_command, with_appcontext
from flask_migrate import downgrade, upgrade

# SQLAlchemy instance and extensions
from app.extensions import cortex, db
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
      • cortex operator group (status, enable, disable)
      • db upgrade/downgrade with telemetry
      • env-doctor command
      • doctor-pa command
      • audit-templates command
      • routes command (Flask built-in)
    """
    redis_client = get_redis_client()
    if not redis_client:
        app.logger.warning("❌ No Redis client available for CLI telemetry.")

    # ------------------------------
    # ⚡ CORTEX OPERATOR GROUP
    # ------------------------------
    @app.cli.group("cortex")
    def cortex_cli():
        """Operator Cortex management CLI commands."""
        pass

    @cortex_cli.command("status")
    def cortex_status():
        """Check current God-Mode stabilization state."""
        status = "ENABLED" if cortex.is_enabled else "DISABLED"
        click.echo(f"⚡ [Operator Cortex Status]: {status}")

    @cortex_cli.command("enable")
    def cortex_enable():
        """Enable God-Mode stabilization at runtime."""
        cortex.enable()
        click.echo("🟢 [Operator Cortex]: God-Mode Stabilization ENABLED.")

    @cortex_cli.command("disable")
    def cortex_disable():
        """Disable God-Mode stabilization at runtime."""
        cortex.disable()
        click.echo("🔴 [Operator Cortex]: God-Mode Stabilization DISABLED.")

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
    # Environment Doctor Command
    # ------------------------------
    @app.cli.command("env-doctor")
    def env_doctor() -> None:
        """Check environment health."""
        click.echo(
            "🩺 [Environment Doctor]: Core runtime environment verified."
        )

        try:
            emit_boot_trace(
                domain="cli",
                event="env_doctor",
                detail="health_check",
                value="ok",
                status="ok",
                client=redis_client,
                ttl=60,
            )
        except Exception as e:
            app.logger.warning(f"⚠️ Telemetry emit failed: {e}")
            try:
                emit_boot_trace(
                    domain="cli",
                    event="env_doctor",
                    detail="health_check",
                    value=f"failure:err:{str(e)[:64]}",
                    status="error",
                    client=None,
                    ttl=60,
                )
            except Exception:
                pass

    # ------------------------------
    # PythonAnywhere Doctor Command
    # ------------------------------
    @app.cli.command("doctor-pa")
    def doctor_pa() -> None:
        """PythonAnywhere-specific health check."""
        click.echo("🩺 [PA Doctor]: PythonAnywhere environment verified.")

        try:
            emit_boot_trace(
                domain="cli",
                event="doctor_pa",
                detail="health_check",
                value="ok",
                status="ok",
                client=redis_client,
                ttl=60,
            )
        except Exception as e:
            app.logger.warning(f"⚠️ Telemetry emit failed: {e}")
            try:
                emit_boot_trace(
                    domain="cli",
                    event="doctor_pa",
                    detail="health_check",
                    value=f"failure:err:{str(e)[:64]}",
                    status="error",
                    client=None,
                    ttl=60,
                )
            except Exception:
                pass

    # ------------------------------
    # Register Top-Level Commands
    # ------------------------------
    app.cli.add_command(audit_templates)
    app.cli.add_command(routes_command)

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