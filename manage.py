#!/usr/bin/env python3
"""manage.py — Supreme Executive‑Grade Operational CLI for PlaidBridgeOpenBankingApi.

Combines Flask CLI commands and DevOps orchestrations into a single Unified
Cockpit.
"""

from __future__ import annotations

from contextlib import redirect_stdout
import io
import os
import subprocess
import sys
import traceback

import click
from flask.cli import FlaskGroup, with_appcontext

from app import create_app
from app.cli.doctor import doctor
from app.cli.doctor_pa import doctor_pa

# Authoritative factory injection (automatically attaches Flask-Migrate 'db' group)
cli = FlaskGroup(create_app=create_app)

# -----------------------------------------------------------------------------
# Explicitly Registered Executive Commands
# -----------------------------------------------------------------------------
cli.add_command(doctor)
cli.add_command(doctor_pa)

# -----------------------------------------------------------------------------
# CLI Registry configuration (Cockpit-Grade CLI Modules)
# -----------------------------------------------------------------------------
_command_modules = [
    # 🛠️ Audit, Security, & Telemetry Infrastructure (app/cli_commands)
    "app.cli_commands.sweep_endpoints",
    "app.cli_commands.cli_template_audit",
    "app.cli_commands.cli_template_block_audit",
    "app.cli_commands.cli_template_inheritance",
    "app.cli_commands.cli_audit",
    "app.cli_commands.diagnostics_cli",
    "app.cli_commands.audit_blueprints",
    "app.cli_commands.blueprint_drift_tracer",
    "app.cli_commands.blueprint_emit",
    "app.cli_commands.emit_blueprint_inspector",
    "app.cli_commands.route_drift",
    "app.cli_commands.route_graph",
    "app.cli_commands.route_map_dump",
    "app.cli_commands.ttl_audit",
    "app.cli_commands.validate_relationships",
    "app.cli_commands.schema_drift_audit",
    "app.cli_commands.endpoint_autofix",
    "app.cli_commands.combined_template_endpoint_audit",
    "app.cli_commands.email_telemetry",
    "app.cli_commands.omega_templates",
    # ⚡ Core Identity Seeders & Pipeline Orchestrators (app/cli)
    "app.cli.reset_and_reseed",
    "app.cli.seed_admin",
    "app.cli.seed_subscriber",
    "app.cli.seed_lender",
    "app.cli.seed_all",
    "app.cli.seed_everything",
    # 📦 Extended Fintech Systems & Mock Environment Hydration (app/cli)
    "app.cli.cockpit_pdf_test",
    # "app.cli.doctor",  <-- Explicitly registered above
    "app.cli.grant_pulse",
    "app.cli.probe_db_auth",
    "app.cli.redis_inspect",
    "app.cli.seed_fraud_cases",
    "app.cli.seed_mock_bank_transfers",
    "app.cli.seed_mock_bank_transfers_all",
    "app.cli.seed_mock_bank_transfers_audit",
    "app.cli.seed_mock_bank_transfers_flags",
    "app.cli.seed_mock_bank_transfers_summary",
    "app.cli.seed_mock_transactions",
    "app.cli.seed_timeline",
    "app.cli.seed_todos",
    "app.cli.seeder_doctor",
    "app.cli.simulate_form_submission",
    "app.cli.statement_leaders",
    "app.cli.statement_pulse",
    "app.cli.trace_probe",
]


def _safe_register(module_path: str) -> None:
    """Safely registers CLI modules while providing cockpit‑grade visibility."""
    try:
        mod = __import__(module_path, fromlist=["*"])
        for v in mod.__dict__.values():
            if isinstance(v, click.core.Command):
                if v.name and "_" in v.name:
                    v.name = v.name.replace("_", "-")
                # Avoid double registration if command already exists
                if v.name not in cli.commands:
                    cli.add_command(v)
    except Exception as exc:
        print(
            f"❌ [CLI Registry Failure] Core drift in module '{module_path}': {exc}",
            file=sys.stderr,
        )
        traceback.print_exc(file=sys.stderr)


for mod_path in _command_modules:
    _safe_register(mod_path)


# -----------------------------------------------------------------------------
# Doctor Orchestration Wrappers
# -----------------------------------------------------------------------------
@cli.command("doctor-auto")
@click.pass_context
def doctor_auto(ctx):
    """Auto-detects environment and runs the appropriate doctor diagnostic."""
    # Detect PythonAnywhere by checking standard PA environment variables or path structure
    is_pa = (
        "PYTHONANYWHERE_DOMAIN" in os.environ
        or "PYTHONANYWHERE_SITE" in os.environ
        or "/home/srpihhllc/" in os.getcwd()
    )

    if is_pa:
        click.secho(
            "\n[🚀] Environment Auto-Detected: PythonAnywhere Production",
            fg="cyan",
            bold=True,
        )
        ctx.invoke(doctor_pa)
    else:
        click.secho(
            "\n[💻] Environment Auto-Detected: Local / CI / Docker",
            fg="cyan",
            bold=True,
        )
        ctx.invoke(doctor)


@cli.command("doctor-suite")
@click.pass_context
def doctor_suite(ctx):
    """Executes both doctor modules and prints results side-by-side."""
    click.secho(
        "\n=== DOCTOR SUITE: SIDE-BY-SIDE DIAGNOSTIC COMPARISON ===",
        fg="cyan",
        bold=True,
    )

    # Capture local doctor output
    f_local = io.StringIO()
    with redirect_stdout(f_local):
        try:
            ctx.invoke(doctor)
        except Exception:
            pass
    local_lines = f_local.getvalue().splitlines()

    # Capture PA doctor output
    f_pa = io.StringIO()
    with redirect_stdout(f_pa):
        try:
            ctx.invoke(doctor_pa)
        except Exception:
            pass
    pa_lines = f_pa.getvalue().splitlines()

    # Pad lists to equal length for side-by-side rendering
    max_len = max(len(local_lines), len(pa_lines))
    local_lines.extend([""] * (max_len - len(local_lines)))
    pa_lines.extend([""] * (max_len - len(pa_lines)))

    click.secho(
        f"{'LOCAL DIAGNOSTICS (flask doctor)':<60} | {'PA DIAGNOSTICS (flask doctor-pa)'}",
        fg="yellow",
        bold=True,
    )
    click.secho("-" * 130)

    for local_line, p in zip(local_lines, pa_lines):
        # Truncate slightly to prevent terminal wrapping issues, maintaining 60 chars per side
        l_trunc = local_line[:58]
        p_trunc = p[:68]
        click.echo(f"{l_trunc:<60} | {p_trunc}")


# -----------------------------------------------------------------------------
# DevOps & Subprocess Execution Engine (Former Makefile Targets)
# -----------------------------------------------------------------------------
VENV = "venv"
RUNTIME_LOCK = "requirements.lock"
DEV_LOCK = "requirements-dev.lock"


def run_shell(command: str, abort_on_fail: bool = True):
    """Executes a shell command cleanly and routes output to stdout."""
    click.secho(f"\n[+] Executing: {command}", fg="cyan", bold=True)
    result = subprocess.run(command, shell=True, executable="/bin/bash")
    if abort_on_fail and result.returncode != 0:
        click.secho(
            f"\n[-] FAILED with exit code {result.returncode}",
            fg="red",
            bold=True,
        )
        sys.exit(result.returncode)
    return result.returncode


@cli.command("sync")
def sync_env():
    """Sync venv to lockfiles."""
    run_shell(f"{VENV}/bin/pip-sync {RUNTIME_LOCK} {DEV_LOCK}")


@cli.command("update-locks")
def update_locks():
    """Recompile lockfiles and sync."""
    run_shell(f"{VENV}/bin/pip install -U pip-tools")
    run_shell(
        f"{VENV}/bin/pip-compile requirements.txt --output-file={RUNTIME_LOCK}"
    )
    run_shell(
        f"{VENV}/bin/pip-compile requirements-dev.txt --output-file={DEV_LOCK}"
    )
    run_shell(f"{VENV}/bin/pip-sync {RUNTIME_LOCK} {DEV_LOCK}")


@cli.command("test")
def run_tests():
    """Run pytest with coverage."""
    run_shell(f"{VENV}/bin/pytest --cov=app --cov-report=term-missing")


@cli.command("migrate-head")
def migrate_head():
    """Apply latest Alembic migrations."""
    run_shell(f"{VENV}/bin/alembic upgrade head")


@cli.command("migrate-rollback")
def migrate_rollback():
    """Downgrade one Alembic migration."""
    run_shell(f"{VENV}/bin/alembic downgrade -1")


@cli.command("initdb")
def init_database():
    """Drop, recreate, and migrate the database."""
    click.secho(
        "\n[!] Dropping and recreating database...", fg="yellow", bold=True
    )
    run_shell(f"{VENV}/bin/alembic downgrade base", abort_on_fail=False)
    run_shell(f"{VENV}/bin/alembic upgrade head")
    click.secho("\n[✔] Database initialized.", fg="green", bold=True)


@cli.command("lint")
def run_lint():
    """Run flake8 linting."""
    run_shell(f"{VENV}/bin/flake8 app")


@cli.command("typecheck")
def run_typecheck():
    """Run mypy type checks."""
    run_shell(f"{VENV}/bin/mypy app")


@cli.command("format")
def run_format():
    """Auto-format code with black and isort."""
    run_shell(f"{VENV}/bin/black app")
    run_shell(f"{VENV}/bin/isort app")


@cli.command("check")
@click.pass_context
def run_all_checks(ctx):
    """Run lint, typecheck, and tests (full suite)."""
    ctx.invoke(run_lint)
    ctx.invoke(run_typecheck)
    ctx.invoke(run_tests)


@cli.command("ci")
def run_ci():
    """Run full CI suite locally (lint, typecheck, tests, coverage XML)."""
    run_shell(f"{VENV}/bin/flake8 app")
    run_shell(f"{VENV}/bin/mypy app | tee mypy-report.txt")
    run_shell(
        f"{VENV}/bin/pytest --cov=app --cov-report=xml --cov-report=term-missing"
        " --maxfail=1 --disable-warnings -q"
    )


@cli.command("env-doctor")
def run_doctor():
    """Check environment health."""
    run_shell("python --version")
    click.echo(f"Virtualenv: {VENV}")
    if not os.path.exists(RUNTIME_LOCK):
        click.secho(f"[-] Missing {RUNTIME_LOCK}", fg="red")
        sys.exit(1)
    if not os.path.exists(DEV_LOCK):
        click.secho(f"[-] Missing {DEV_LOCK}", fg="red")
        sys.exit(1)
    click.secho("\n[✔] Environment looks good.", fg="green", bold=True)


@cli.command("dev")
def run_dev():
    """Run Flask app locally in development mode."""
    env = os.environ.copy()
    env["FLASK_APP"] = "app"
    env["FLASK_ENV"] = "development"
    click.secho(
        "[+] Starting Flask Development Server...", fg="cyan", bold=True
    )
    subprocess.run([f"{VENV}/bin/flask", "run"], env=env)


@cli.command("clean")
def run_clean():
    """Remove venv and caches."""
    run_shell(
        f"rm -rf {VENV} __pycache__ .pytest_cache .mypy_cache .coverage"
    )


# -----------------------------------------------------------------------------
# Application & Architecture Inspection Commands
# -----------------------------------------------------------------------------
@cli.command("entrypoints")
@with_appcontext
def entrypoints():
    """Show routes that matter for operator access and cockpit entry."""
    from flask import current_app

    targets = ["terence", "ignite", "operator", "admin/cockpit"]
    click.echo("\n=== EXECUTIVE ENTRY POINTS ===")
    for rule in current_app.url_map.iter_rules():
        if any(t in rule.rule for t in targets):
            click.echo(f"{rule.rule:35}  {rule.endpoint}")


@cli.command("verify-sandbox")
@click.option(
    "--route",
    default="/api/v1/fintech/sandbox/account_snapshot",
    help="Sandbox route to verify",
)
@with_appcontext
def verify_sandbox(route: str):
    """Verify sandbox mock endpoints for anti-phishing & compliance schema

    attributes.
    """
    from flask import current_app

    click.secho(
        f"\n[+] Executing schema verification on endpoint: {route}", fg="cyan"
    )
    with current_app.test_client() as client:
        response = client.get(route)
        if response.status_code != 200:
            click.secho(
                f"[-] FAILED: Route returned HTTP {response.status_code}",
                fg="red",
            )
            return
        payload = response.get_json() or {}
        data = payload.get("data", {})
        inst = data.get("institution", {})
        compliance = data.get("compliance_audit", {})

        errors = []
        if "phishing_risk_level" not in inst:
            errors.append("Missing 'institution.phishing_risk_level' attribute.")
        if "unethical_lending_flag" not in compliance:
            errors.append(
                "Missing 'compliance_audit.unethical_lending_flag' attribute."
            )
        if "predatory_score" not in compliance:
            errors.append(
                "Missing 'compliance_audit.predatory_score' attribute."
            )

        if errors:
            click.secho(
                "\n[!] SCHEMA VERIFICATION FAILED:", fg="red", bold=True
            )
            for err in errors:
                click.secho(f"  - {err}", fg="red")
        else:
            click.secho(
                "\n[✔] SCHEMA VERIFICATION PASSED: All defensive flags present.",
                fg="green",
                bold=True,
            )


@cli.command("verify-routes")
@with_appcontext
def verify_routes():
    """Audit registered routes and highlight duplicate path/method rules."""
    from flask import current_app

    click.secho("\n[+] Auditing application route tree...", fg="cyan")
    seen_routes = {}
    duplicates = []
    for rule in current_app.url_map.iter_rules():
        key = (rule.rule, tuple(sorted(rule.methods or [])))
        if key in seen_routes:
            duplicates.append((rule.endpoint, seen_routes[key], rule.rule))
        else:
            seen_routes[key] = rule.endpoint

    if duplicates:
        click.secho(
            "\n[!] DUPLICATE ROUTE REGISTRATIONS DETECTED:",
            fg="yellow",
            bold=True,
        )
        for ep1, ep2, rule in duplicates:
            click.echo(f"  - Path '{rule}' registered in '{ep1}' and '{ep2}'")
    else:
        click.secho(
            "\n[✔] ROUTE TREE CLEAN: No duplicate endpoint registrations"
            " found.",
            fg="green",
            bold=True,
        )


# -----------------------------------------------------------------------------
# CLI Entrypoint
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    cli()