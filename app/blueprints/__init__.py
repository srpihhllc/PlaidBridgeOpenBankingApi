# =============================================================================
# FILE: app/blueprints/__init__.py
# DESCRIPTION:
#    Deterministic, collision‑proof blueprint registration system with
#    explicit ordering + auto‑discovery + double‑registration guards.
# =============================================================================

import logging
import pkgutil
from importlib import import_module
from types import ModuleType
from flask import Blueprint, Flask

logger = logging.getLogger(__name__)

# Root package for blueprints
_BLUEPRINT_PACKAGE = "app.blueprints"

# Explicit ordering for critical blueprints
_EXPLICIT_ORDER: list[tuple[str, list[str]]] = [
    ("app.blueprints.pulse_routes", ["pulse_bp"]),
    ("app.blueprints.main_routes", ["main_bp"]),
    ("app.blueprints.api_routes", ["api_bp"]),
    ("app.blueprints.api_v1_routes", ["api_v1_bp"]),
    ("app.blueprints.auth_routes", ["auth_bp"]),
    ("app.blueprints.admin_routes", ["admin_bp", "admin_api_bp"]),
]

# Modules to ignore during auto‑discovery
# IMPORTANT:
# oauth_routes MUST remain ignored because oauth_bp is registered manually
# inside create_app(). Removing this causes double‑registration and duplicate
# route rules such as /oauth/callback/<provider>.
_IGNORE_MODULES = {
    "register_blueprints",
    "__init__",
    "__pycache__",
}


# ---------------------------------------------------------------------------
# MODULE DISCOVERY
# ---------------------------------------------------------------------------

def _iter_blueprint_modules() -> list[ModuleType]:
    """Auto‑discover blueprint modules under app.blueprints."""
    modules: list[ModuleType] = []
    pkg = import_module(_BLUEPRINT_PACKAGE)

    for _finder, name, _ispkg in pkgutil.iter_modules(pkg.__path__, pkg.__name__ + "."):
        short = name.rsplit(".", 1)[-1]
        if short in _IGNORE_MODULES:
            continue
        try:
            modules.append(import_module(name))
        except Exception as exc:
            logger.error(f"❌ Failed importing blueprint module {name}: {exc}", exc_info=True)
            raise

    return modules


def _discover_blueprints_in_module(mod: ModuleType) -> dict[str, Blueprint]:
    """Return all Blueprint instances defined at module level."""
    return {
        attr_name: value
        for attr_name, value in vars(mod).items()
        if isinstance(value, Blueprint)
    }

# ---------------------------------------------------------------------------
# REGISTRY BUILDING
# ---------------------------------------------------------------------------

def _build_blueprint_registry() -> list[tuple[str, str, Blueprint]]:
    """
    Build a registry of (module_path, bp_name, blueprint) with:
    - explicit ordering for critical blueprints
    - auto‑discovery for the rest
    """
    registry: list[tuple[str, str, Blueprint]] = []
    seen: set[tuple[str, str]] = set()

    # 1) Explicit ordering
    for module_path, bp_names in _EXPLICIT_ORDER:
        mod = import_module(module_path)
        for bp_name in bp_names:
            bp = getattr(mod, bp_name, None)
            if not isinstance(bp, Blueprint):
                raise RuntimeError(
                    f"Expected Blueprint '{bp_name}' in '{module_path}', "
                    f"found {type(bp).__name__ if bp is not None else 'None'}"
                )
            key = (module_path, bp_name)
            if key in seen:
                raise RuntimeError(f"Duplicate blueprint registration entry: {key}")
            seen.add(key)
            registry.append((module_path, bp_name, bp))

    # 2) Auto‑discovery
    for mod in _iter_blueprint_modules():
        module_path = mod.__name__
        discovered = _discover_blueprints_in_module(mod)

        for bp_name, bp in discovered.items():
            key = (module_path, bp_name)
            if key in seen:
                continue
            seen.add(key)
            registry.append((module_path, bp_name, bp))

    return registry

# ---------------------------------------------------------------------------
# BLUEPRINT REGISTRATION
# ---------------------------------------------------------------------------

def register_blueprints(app: Flask) -> None:
    """
    Deterministically register all blueprints with the Flask app.

    Guarantees:
    - No blueprint is ever registered twice.
    - Explicitly registered blueprints in create_app() are respected.
    - Auto‑discovery fills in the rest.
    - Logging is narratable and operator‑friendly.
    """
    registry = _build_blueprint_registry()

    for module_path, bp_name, bp in registry:
        instance_name = bp.name  # canonical blueprint key

        # Guard 1: skip if blueprint already registered by create_app()
        if instance_name in app.blueprints:
            app.logger.debug(
                "⏭️ Skipping blueprint '%s' from %s (already registered in create_app)",
                instance_name,
                module_path,
            )
            continue

        # Guard 2: skip if attribute name collides with existing blueprint key
        if bp_name in app.blueprints:
            app.logger.debug(
                "⏭️ Skipping blueprint '%s' from %s (attribute name already present)",
                bp_name,
                module_path,
            )
            continue

        try:
            app.register_blueprint(bp)
            app.logger.info(
                "🔗 Registered blueprint: %s from %s (url_prefix=%s)",
                bp_name,
                module_path,
                bp.url_prefix,
            )
        except Exception as exc:
            app.logger.exception(
                "❌ Failed registering blueprint '%s' from '%s': %s",
                bp_name,
                module_path,
                exc,
            )
            raise

    logger.info("✅ All blueprints registered successfully (explicit + auto‑discovered).")

# ---------------------------------------------------------------------------
# BLUEPRINT GRAPH VALIDATION
# ---------------------------------------------------------------------------

def validate_blueprints_graph(app: Flask) -> None:
    """Emit a simple blueprint dependency/coverage graph."""
    by_prefix: dict[str | None, list[str]] = {}

    for name, bp in app.blueprints.items():
        by_prefix.setdefault(bp.url_prefix, []).append(name)

    logger.info("📊 Blueprint graph (by url_prefix):")
    for prefix, names in sorted(by_prefix.items(), key=lambda x: str(x[0])):
        logger.info(f"  prefix={prefix!r} -> blueprints={names}")

    overlaps = {p: n for p, n in by_prefix.items() if p is not None and len(n) > 1}

    if overlaps:
        logger.warning("⚠️ Detected overlapping blueprint url_prefix assignments:")
        for prefix, names in overlaps.items():
            logger.warning(f"  prefix={prefix!r} used by: {names}")
    else:
        logger.info("✅ No overlapping blueprint url_prefix assignments detected.")
