# =============================================================================
# FILE: app/cli_commands/blueprint_drift_tracer.py
# DESCRIPTION: CLI utility to detect blueprint drift and emit cockpit-grade
#              telemetry traces for operator visibility.
# =============================================================================

import importlib
import pkgutil
from collections.abc import Iterable
from pathlib import Path

from flask import Blueprint

from app.telemetry.ttl_emit import emit_schema_trace


def _find_blueprint_attrs(module, attr_name: str | None) -> list[str]:
    """
    Return attribute names that reference Flask Blueprint instances.
    If attr_name is provided and exists, it is returned preferentially.
    """
    if attr_name and hasattr(module, attr_name):
        if isinstance(getattr(module, attr_name), Blueprint):
            return [attr_name]

    found = []
    for name in dir(module):
        try:
            value = getattr(module, name)
        except Exception:
            continue
        if isinstance(value, Blueprint):
            found.append(name)
    return found


def audit_blueprint_attributes(
    base_package: str = "app.blueprints",
    attr_name: str | None = "bp",
    extra_attr_names: Iterable[str] | None = None,
    exclude_modules: Iterable[str] | None = None,
) -> list[str]:
    """
    Scans all modules in base_package for a Flask Blueprint instance.
    If attr_name is provided, it is checked first. If missing or not a Blueprint,
    the scanner falls back to any Blueprint instance in the module.
    """
    base_path = Path(__file__).resolve().parents[1] / "blueprints"
    failures: list[str] = []
    preferred_names = set(extra_attr_names or [])
    exclude: set[str] = set(exclude_modules or {"grant_writer"})

    if attr_name:
        preferred_names.add(attr_name)

    for _, module_name, _ in pkgutil.iter_modules([str(base_path)]):
        if module_name in exclude:
            continue

        full_module = f"{base_package}.{module_name}"
        try:
            mod = importlib.import_module(full_module)
            found = _find_blueprint_attrs(mod, attr_name)

            if not found:
                # Try any explicitly preferred names (e.g., admin_bp, sub_bp)
                for name in preferred_names:
                    if hasattr(mod, name) and isinstance(getattr(mod, name), Blueprint):
                        found.append(name)
                        break

            if not found:
                failures.append(f"{full_module} missing Blueprint instance")
        except Exception as e:
            failures.append(f"{full_module} import failed: {e}")

    return failures


def run_cli() -> None:
    failures = audit_blueprint_attributes()
    if failures:
        print("❌ Blueprint drift detected:")
        for f in failures:
            print(f"   - {f}")

        # Emit schema-compliant telemetry for drift failure
        emit_schema_trace(
            domain="cli",
            event="blueprint_drift",
            detail="fail",
            value=f"violations:{len(failures)}",
            status="error",
            ttl=300,
            meta={"failures": failures},
        )
    else:
        print("✅ All blueprints present and attribute matches.")

        # Emit schema-compliant telemetry for drift success
        emit_schema_trace(
            domain="cli",
            event="blueprint_drift",
            detail="pass",
            value="success",
            status="ok",
            ttl=300,
            meta={"failures": 0},
        )


if __name__ == "__main__":
    run_cli()
