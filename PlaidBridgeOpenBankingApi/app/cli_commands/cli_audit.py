# =============================================================================
# FILE: app/cli_commands/cli_audit.py
# DESCRIPTION: CLI Audit Command — Cockpit-grade safety net.
#
# Scans app/cli and app/cli_commands for:
#   - Any functions registered to Flask CLI that are NOT @click.command objects.
#   - Any click.Groups (group shadowing) instead of pure Commands.
#
# Emits cockpit telemetry + exits non-zero if violations found.
# =============================================================================

import importlib
import inspect
import sys
from pathlib import Path
from types import ModuleType

import click

from app.telemetry.ttl_emit import emit_schema_trace

TARGET_DIRS = [
    Path(__file__).resolve().parent.parent / "cli",
    Path(__file__).resolve().parent.parent / "cli_commands",
]


@click.command("cli_audit")
def cli_audit():
    """Audit CLI modules for non-compliant command registrations."""
    violations = []

    def scan_module(mod: ModuleType, mod_path: Path):
        for name, obj in inspect.getmembers(mod):
            if callable(obj) and not isinstance(obj, click.Command):
                # Catch functions that look like CLI but aren't decorated
                if inspect.isfunction(obj) and obj.__module__.startswith("app.cli"):
                    violations.append(f"{mod_path}:{name} — function is not a click.Command")
            if isinstance(obj, click.Group):
                violations.append(
                    f"{mod_path}:{name} — click.Group detected (should be pure Command)"
                )

    for target_dir in TARGET_DIRS:
        for py_file in target_dir.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            module_path = ".".join(
                py_file.relative_to(Path(__file__).resolve().parent.parent).with_suffix("").parts
            )
            try:
                mod = importlib.import_module(f"app.{module_path}")
                scan_module(mod, py_file)
            except Exception as e:
                violations.append(f"❌ Import failed for {py_file}: {e}")

    if violations:
        # Schema-compliant telemetry emit for failure
        emit_schema_trace(
            domain="cli",
            event="audit",
            detail="fail",
            value=f"violations:{len(violations)}",
            status="error",
            ttl=300,
            meta={"violations": violations},
        )
        click.echo("🚨 CLI Audit Failed:")
        for v in violations:
            click.echo(f" - {v}")
        sys.exit(1)

    # Schema-compliant telemetry emit for success
    emit_schema_trace(
        domain="cli",
        event="audit",
        detail="pass",
        value="success",
        status="ok",
        ttl=300,
        meta={"violations": 0},
    )
    click.echo("✅ CLI Audit Passed — all commands are @click.command and no Groups found.")

def run():
    ...
