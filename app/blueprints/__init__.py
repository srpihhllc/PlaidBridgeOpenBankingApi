# =============================================================================
# FILE: app/blueprints/__init__.py
# DESCRIPTION:
#    Deterministic, collision-proof blueprint registration system with
#    explicit ordering + auto-discovery + double-registration guards.
# =============================================================================

import logging
import pkgutil
from importlib import import_module
from types import ModuleType

from flask import Blueprint, Flask

logger = logging.getLogger(__name__)

# Root package for blueprints
_BLUEPRINT_PACKAGE = "app.blueprints"

# Explicit ordering for critical blueprints.
# - admin_ui_routes MUST come after admin_routes (imports mock models from it).
# - Reference "admin_bp" — the primary attribute name in admin_ui_routes.py.
#   "admin_ui_bp" is just an alias in that module pointing to the same object.
_EXPLICIT_ORDER: list[tuple[str, list[str]]] = [
    ("app.blueprints.pulse_routes", ["pulse_bp"]),
    ("app.blueprints.main_routes", ["main_bp"]),
    ("app.blueprints.api_routes", ["api_bp"]),
    ("app.blueprints.api_v1_routes", ["api_v1_bp"]),
    ("app.blueprints.auth_routes", ["auth_bp"]),
    ("app.blueprints.admin_routes", ["admin_api_bp"]),      # API-only; name="admin_api", no admin_index
    ("app.blueprints.admin_ui_routes", ["admin_bp"]),       # UI blueprint; name="admin", has admin_index
]

# Modules to ignore during auto-discovery.
#
# - oauth_routes: oauth_bp is registered manually inside create_app(). Auto-discovering
#   it causes double-registration and duplicate route rules (/oauth/callback/<provider>).
# - admin_ui_routes: explicitly ordered above. Auto-discovery would find both "admin_bp"
#   and "admin_ui_bp" (alias) as separate Blueprint instances and attempt to register
#   the "admin" blueprint a second time. The bp.name guard would skip it, but excluding
#   the module entirely keeps the registry clean and log output unambiguous.
_IGNORE_MODULES = {
    "register_blueprints",
    "__init__",
    "__pycache__",
    "admin_ui_routes",  # handled explicitly in _EXPLICIT_ORDER above
}


# ---------------------------------------------------------------------------
# MODULE DISCOVERY
# ---------------------------------------------------------------------------

def _iter_blueprint_modules() -> list[ModuleType]:
    """Auto-discover blueprint modules under app.blueprints."""
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
    Build an ordered registry of (module_path, bp_name, blueprint):
    1. Explicit ordering for critical blueprints.
    2. Auto-discovery for everything else.
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

    # 2) Auto-discovery
    for mod in _iter_blueprint_modules():
        module_path = mod.__name__
        for bp_name, bp in _discover_blueprints_in_module(mod).items():
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
    - No blueprint is registered twice (guards on bp.name).
    - Blueprints explicitly registered in create_app() are respected.
    - Auto-discovery fills in the rest.
    """
    registry = _build_blueprint_registry()

    for module_path, bp_name, bp in registry:
        # Skip if already registered (e.g. registered explicitly in create_app)
        if bp.name in app.blueprints:
            app.logger.debug(
                "⏭️ Skipping blueprint '%s' from %s (already registered)",
                bp.name,
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

    logger.info("✅ All blueprints registered successfully (explicit + auto-discovered).")


# ---------------------------------------------------------------------------
# BLUEPRINT GRAPH VALIDATION
# ---------------------------------------------------------------------------

def validate_blueprints_graph(app: Flask) -> None:
    """Emit a simple blueprint coverage graph and warn on prefix overlaps."""
    by_prefix: dict[str | None, list[str]] = {}

    for name, bp in app.blueprints.items():
        by_prefix.setdefault(bp.url_prefix, []).append(name)

    logger.info("📊 Blueprint graph (by url_prefix):")
    for prefix, names in sorted(by_prefix.items(), key=lambda x: str(x[0])):
        logger.info("  prefix=%r -> blueprints=%s", prefix, names)

    overlaps = {p: n for p, n in by_prefix.items() if p is not None and len(n) > 1}
    if overlaps:
        logger.warning("⚠️ Detected overlapping blueprint url_prefix assignments:")
        for prefix, names in overlaps.items():
            logger.warning("  prefix=%r used by: %s", prefix, names)
    else:
        logger.info("✅ No overlapping blueprint url_prefix assignments detected.")
