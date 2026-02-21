# =============================================================================
# FILE: app/blueprints/__init__.py
# DESCRIPTION:
#    Deterministic blueprint registration and auto-discovery system.
# =============================================================================

import logging
import pkgutil
from importlib import import_module
from types import ModuleType

from flask import Blueprint, Flask

logger = logging.getLogger(__name__)

# Root package for blueprints
_BLUEPRINT_PACKAGE = "app.blueprints"

# Explicit ordering for critical blueprints (others auto‑discovered)
_EXPLICIT_ORDER: list[tuple[str, list[str]]] = [
    ("app.blueprints.pulse_routes", ["pulse_bp"]),
    ("app.blueprints.main_routes", ["main_bp"]),
    ("app.blueprints.api_routes", ["api_bp"]),
    ("app.blueprints.api_v1_routes", ["api_v1_bp"]),
    ("app.blueprints.auth_routes", ["auth_bp"]),
    ("app.blueprints.admin_routes", ["admin_bp", "admin_api_bp"]),
]

# Modules to ignore during auto‑discovery
_IGNORE_MODULES = {
    "register_blueprints",
    "__init__",
    "__pycache__",
}


def _iter_blueprint_modules() -> list[ModuleType]:
    """Auto‑discover blueprint modules under app.blueprints."""
    modules: list[ModuleType] = []

    pkg = import_module(_BLUEPRINT_PACKAGE)
    for _finder, name, _ispkg in pkgutil.iter_modules(pkg.__path__, pkg.__name__ + "."):
        short_name = name.rsplit(".", 1)[-1]
        if short_name in _IGNORE_MODULES:
            continue
        try:
            mod = import_module(name)
            modules.append(mod)
        except Exception as exc:
            logger.error(f"❌ Failed importing blueprint module {name}: {exc}", exc_info=True)
            raise
    return modules


def _discover_blueprints_in_module(mod: ModuleType) -> dict[str, Blueprint]:
    """Return all Blueprint instances defined at module level."""
    bps: dict[str, Blueprint] = {}
    for attr_name, value in vars(mod).items():
        if isinstance(value, Blueprint):
            bps[attr_name] = value
    return bps


def _build_blueprint_registry() -> list[tuple[str, str, Blueprint]]:
    """
    Build a registry of (module_path, bp_name, blueprint) with:
    - explicit ordering for critical blueprints
    - auto‑discovery for the rest
    """
    registry: list[tuple[str, str, Blueprint]] = []
    seen: set[tuple[str, str]] = set()

    # 1) Explicitly ordered blueprints
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

    # 2) Auto‑discover remaining blueprints
    for mod in _iter_blueprint_modules():
        module_path = mod.__name__
        discovered = _discover_blueprints_in_module(mod)
        for bp_name, bp in discovered.items():
            key = (module_path, bp_name)
            if key in seen:
                continue  # already explicitly registered in step 1
            seen.add(key)
            registry.append((module_path, bp_name, bp))

    return registry


def register_blueprints(app: Flask) -> None:
    """
    Deterministically register all blueprints with the Flask app.

    Logic:
    - Fetches the ordered registry.
    - SKIPS blueprints already registered (handles explicit factory registration).
    - Prevents ValueError: The name 'admin' is already registered.
    """
    registry = _build_blueprint_registry()

    for module_path, bp_name, bp in registry:
        # ⭐ GUARD: Skip if already registered (e.g., admin_bp registered in create_app)
        if bp.name in app.blueprints:
            logger.info(
                f"⏭️ Skipping already-registered blueprint: '{bp.name}' " f"(found in {module_path})"
            )
            continue

        try:
            app.register_blueprint(bp)
            logger.info(
                f"🔗 Registered blueprint: {bp_name} from {module_path} "
                f"(url_prefix={bp.url_prefix})"
            )
        except Exception as exc:
            logger.error(
                f"❌ Failed registering blueprint '{bp_name}' from '{module_path}': {exc}",
                exc_info=True,
            )
            raise

    logger.info("✅ All blueprints registered successfully (factory-explicit + auto‑discovered).")


def validate_blueprints_graph(app: Flask) -> None:
    """
    Emit a simple blueprint dependency/coverage graph:
    - list all blueprints
    - list all url_prefixes
    - detect obvious overlaps
    """
    by_prefix: dict[str | None, list[str]] = {}
    for name, bp in app.blueprints.items():
        by_prefix.setdefault(bp.url_prefix, []).append(name)

    logger.info("📊 Blueprint graph (by url_prefix):")
    for prefix, names in sorted(by_prefix.items(), key=lambda x: str(x[0])):
        logger.info(f"  prefix={prefix!r} -> blueprints={names}")

    # Simple overlap detection: same prefix with multiple blueprints
    overlaps = {p: n for p, n in by_prefix.items() if p is not None and len(n) > 1}
    if overlaps:
        logger.warning("⚠️ Detected overlapping blueprint url_prefix assignments:")
        for prefix, names in overlaps.items():
            logger.warning(f"  prefix={prefix!r} used by: {names}")
    else:
        logger.info("✅ No overlapping blueprint url_prefix assignments detected.")
