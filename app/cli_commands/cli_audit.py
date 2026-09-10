# =============================================================================
# FILE: app/cli_commands/cli_audit.py
# DESCRIPTION: CLI Audit Command — Cockpit-grade safety net.
#              Remediated to bind Flask context execution frames.
# =============================================================================

import importlib
import inspect
import sys
from pathlib import Path
from types import ModuleType

import click
from flask.cli import with_appcontext  # ✅ Added for context safety

from app.telemetry.ttl_emit import emit_schema_trace

TARGET_DIRS = [
    Path(__file__).resolve().parent.parent / "cli",
    Path(__file__).resolve().parent.parent / "cli_commands",
]


@click.command("cli_audit")
@with_appcontext  # ✅ Pushes application context onto the proxy stack before module reflection
def cli_audit():
    """Audit CLI modules for non-compliant command registrations."""
    violations = []

    def scan_module(mod: ModuleType, mod_path: Path):
        try:
            # Pass 1: Scan for explicit structural violations (Groups)
            for name, obj in inspect.getmembers(mod):
                if isinstance(obj, click.Group):
                    violations.append(
                        f"{mod_path}:{name} — click.Group detected (should be pure Command)"
                    )

            # Pass 2: Check if this module successfully satisfies the manage.py discovery loop
            has_pure_command = any(
                isinstance(obj, click.Command)
                and not isinstance(obj, click.Group)
                for _, obj in inspect.getmembers(mod)
            )

            # If a valid command exists, any other functions are safely isolated internal helpers
            if has_pure_command:
                return

            # Pass 3: If no command exists, flag locally defined public functions as un-decorated
            for name, obj in inspect.getmembers(mod):
                if name.startswith("_") or name in (
                    "init_app",
                    "run_cli",
                    "COMMANDS",
                ):
                    continue

                if inspect.isfunction(obj) and obj.__module__ == mod.__name__:
                    violations.append(
                        f"{mod_path}:{name} — function is not a click.Command"
                    )
        except Exception as scan_err:
            violations.append(
                f"❌ Metaprogramming reflection failure in {mod_path}: {scan_err}"
            )

    for target_dir in TARGET_DIRS:
        for py_file in target_dir.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            module_path = ".".join(
                py_file.relative_to(Path(__file__).resolve().parent.parent)
                .with_suffix("")
                .parts
            )
            try:
                mod = importlib.import_module(f"app.{module_path}")
                scan_module(mod, py_file)
            except Exception as e:
                violations.append(f"❌ Import failed for {py_file}: {e}")

    if violations:
        try:
            emit_schema_trace(
                domain="cli",
                event="audit",
                detail="fail",
                value=f"violations:{len(violations)}",
                status="error",
                ttl=300,
                meta={"violations": violations},
            )
        except Exception as redis_err:
            click.echo(
                f"⚠️ Telemetry fallback: Trace log failed: {redis_err}",
                err=True,
            )

        click.echo("🚨 CLI Audit Failed:")
        for v in violations:
            click.echo(f" - {v}")
        sys.exit(1)

    try:
        emit_schema_trace(
            domain="cli",
            event="audit",
            detail="pass",
            value="success",
            status="ok",
            ttl=300,
            meta={"violations": 0},
        )
    except Exception:
        pass

    click.echo(
        "✅ CLI Audit Passed — all commands are @click.command and no Groups found."
    )
