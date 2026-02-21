# =============================================================================
# FILE: app/scripts/cli_template_tracer.py
# DESCRIPTION: CLI command to trace template wiring and report misfires.
#              Uses @with_appcontext instead of manual app.app_context().
#              Extended to emit results into Redis for cockpit visualization.
# =============================================================================

import inspect
import json
import os

import click
from flask import current_app
from flask.cli import with_appcontext

from app.cockpit.template_tracer import trace_templates
from app.utils.redis_utils import get_redis_client


def classify_error(err_text: str) -> str:
    """Return a human-friendly category for the error."""
    if not err_text:
        return "Unknown"
    if "TemplateNotFound" in err_text:
        return "Missing template"
    if "BuildError" in err_text:
        return "Bad url_for() / endpoint mismatch"
    if "Unauthorized" in err_text or "NoAuthorizationError" in err_text:
        return "Auth‑blocked"
    if "missing 1 required positional argument" in err_text:
        return "Route parameter mismatch"
    if "AttributeError" in err_text:
        return "Backend attribute error"
    if "BadRequest" in err_text:
        return "Bad request / missing form or query param"
    return "Other backend error"


@click.command("trace-templates")
@with_appcontext
def trace_templates_command():
    """
    CLI command: Trace template wiring and report broken/misfiring endpoints.
    Run with: flask trace-templates
    """
    results = trace_templates()

    # Emit results into Redis for cockpit tiles
    redis_client = get_redis_client()
    if redis_client:
        try:
            redis_client.setex("audit:template_wiring", 600, json.dumps(results))
            click.echo("✅ Template wiring audit emitted to Redis (key=audit:template_wiring)")
        except Exception as e:
            click.echo(f"⚠️ Failed to emit template wiring audit to Redis: {e}")

    click.echo("\n=== TEMPLATE WIRING REPORT ===\n")
    for r in results:
        if r["status"] == "ok":
            continue  # Only show broken/misfiring ones

        # Locate backend source
        try:
            view_func = current_app.view_functions.get(r["endpoint"])
            if view_func:
                src_file = inspect.getsourcefile(view_func)
                _, start_line = inspect.getsourcelines(view_func)
                src_path = os.path.relpath(src_file, start=os.getcwd())
                location = f"{src_path}:{start_line}"
            else:
                location = "⚠️ endpoint not found in view_functions"
        except Exception as e:
            location = f"⚠️ could not inspect source: {e}"

        # Error classification
        last_line = r["error"].splitlines()[-1] if r["error"] else ""
        category = classify_error(last_line)

        # Print cockpit‑grade detail
        click.echo(f"❌ {r['rule']} → {r['endpoint']}")
        click.echo(f"   ↳ Category: {category}")
        click.echo(f"   ↳ Template: {r.get('template', 'unknown')}")
        click.echo(f"   ↳ Backend:  {location}")
        if last_line:
            click.echo(f"   ↳ Error:    {last_line}")
        click.echo("-" * 60)


# -------------------------------------------------------------------------
# Registration helper
# -------------------------------------------------------------------------
def register_commands(app):
    """Register this CLI command with the Flask app."""
    app.cli.add_command(trace_templates_command)
