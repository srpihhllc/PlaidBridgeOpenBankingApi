# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/utils/schema_drift_audit.py

import click
import shutil
import sys
from flask.cli import with_appcontext
from flask import current_app

from app.utils.generate_model_manifest import generate_manifest
from app.utils.schema_drift_detector import detect_schema_drift

@click.command("audit-schema")
@click.option("--update-baseline", is_flag=True, help="Set the current schema as the new stable baseline.")
@with_appcontext
def schema_drift_audit(update_baseline):
    """Generates manifest and checks for structural drift."""

    # 1. Generate the current state manifest
    generate_manifest()

    # 2. Handle baseline reset
    if update_baseline:
        try:
            shutil.copy("storage/manifest/model_manifest.json", "storage/manifest/model_manifest_stable.json")
            click.secho("✅ Baseline updated. Current database schema is now marked as STABLE.", fg="green", bold=True)
        except FileNotFoundError:
            click.secho("❌ Failed to update baseline: Current manifest not found.", fg="red")
        return

    # 3. Perform standard drift audit
    click.echo("🔍 [Schema Audit] Checking for drift...")
    redis_client = getattr(current_app, "extensions", {}).get("redis")
    report = detect_schema_drift(redis_client=redis_client)

    if report["drift_detected"]:
        click.secho("🚨 DRIFT DETECTED", fg="red", bold=True)
        for model, detail in report.get("drift_details", {}).items():
            click.echo(f"   • {model}: {detail}")
        sys.exit(1)
    else:
        click.secho("✅ Schema is stable.", fg="green", bold=True)