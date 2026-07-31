# =============================================================================
# FILE: app/blueprints/__init__.py
# DESCRIPTION:
#    Deterministic, collision-proof blueprint registration engine with
#    explicit execution topology, auto-discovery, and lifecycle validation.
# =============================================================================

import logging
import pkgutil
from importlib import import_module
from types import MappingProxyType, ModuleType
from typing import Final

from flask import Blueprint, Flask

# Initialize isolated logger module context
logger = logging.getLogger(__name__)

# Root module namespace target for discovery operations
_BLUEPRINT_PACKAGE: Final[str] = "app.blueprints"

# Explicit registration topology for critical structural blueprints.
# Enforces exact boot ordering requirements across complex execution bounds.
_EXPLICIT_ORDER: Final[tuple[tuple[str, tuple[str, ...]], ...]] = (
    ("app.blueprints.pulse_routes", ("pulse_bp",)),
    ("app.blueprints.main_routes", ("main_bp",)),
    ("app.blueprints.api_routes", ("api_bp",)),
    ("app.blueprints.api_v1_routes", ("api_v1_bp",)),
    ("app.blueprints.auth_routes", ("auth_bp",)),
    ("app.blueprints.admin_routes", ("admin_api_bp",)),   # Core operational API layer (name="admin_api")
    ("app.blueprints.admin_ui_routes", ("admin_bp",)),     # Canonical administration UI layer
    ("app.cockpit.routes.drilldown", ("drilldown_bp",)),   # Isolated out-of-tree template diagnostics layer
)

# Immutable exclusion set used to protect against double registration during engine discovery
_IGNORE_MODULES: Final[set[str]] = set(MappingProxyType({
    "register_blueprints": None,
    "__init__": None,
    "__pycache__": None,
    "admin_ui_routes": None,  # Hard exclusion: handled explicitly in _EXPLICIT_ORDER tracking matrix
}).keys())


# ---------------------------------------------------------------------------
# CORE DISCOVERY ENGINE
# ---------------------------------------------------------------------------

def _iter_blueprint_modules() -> list[ModuleType]:
    """
    Scan target blueprint package workspace paths dynamically using pkgutil.
    
    Returns:
        list[ModuleType]: Successfully imported runtime module instances.
    """
    discovered_modules: list[ModuleType] = []
    
    try:
        package_context = import_module(_BLUEPRINT_PACKAGE)
    except ImportError as err:
        logger.critical(f"💥 Failed to establish base blueprint context package space: {_BLUEPRINT_PACKAGE}", exc_info=True)
        raise err

    # Iterate package target bounds safely using native runtime paths
    for _, module_name, _ in pkgutil.iter_modules(package_context.__path__, f"{package_context.__name__}."):
        module_identifier = module_name.rsplit(".", 1)[-1]
        if module_identifier in _IGNORE_MODULES:
            continue

        try:
            discovered_modules.append(import_module(module_name))
        except Exception as exc:
            logger.error(f"❌ Aborted import sequence on dynamic blueprint target module: {module_name} | Reason: {exc}", exc_info=True)
            raise exc

    return discovered_modules


def _discover_blueprints_in_module(module_context: ModuleType) -> list[tuple[str, Blueprint]]:
    """
    Extract exported Blueprint primitives defined directly at module level scope.
    
    Args:
        module_context (ModuleType): Target compiled module structure.
    Returns:
        list[tuple[str, Blueprint]]: Named tuples containing export identifiers and instances.
    """
    extracted_targets: list[tuple[str, Blueprint]] = []
    
    # Defensive verification of public module dictionary attributes
    for attribute_key in dir(module_context):
        if attribute_key.startswith("_"):
            continue
            
        runtime_value = getattr(module_context, attribute_key, None)
        if isinstance(runtime_value, Blueprint):
            extracted_targets.append((attribute_key, runtime_value))
            
    return extracted_targets


# ---------------------------------------------------------------------------
# REGISTRY TRANSFORMATION MATRICES
# ---------------------------------------------------------------------------

def _build_blueprint_registry() -> list[tuple[str, str, Blueprint]]:
    """
    Construct compiled registry mapping tracking paths, variable tokens, and instances.
    
    Processing Phases:
        1. Enforce strict processing order defined by explicit matrix array.
        2. Execute auto-discovery sweeps over variable package scopes.
        
    Raises:
        RuntimeError: On missing targets or duplicate component declarations.
    """
    compiled_registry: list[tuple[str, str, Blueprint]] = []
    resolved_tracking_keys: set[tuple[str, str]] = set()
    registered_blueprint_names: set[str] = set()

    # Phase 1: Processing Explicit Routing Orders
    for module_path, target_blueprint_tokens in _EXPLICIT_ORDER:
        try:
            imported_module = import_module(module_path)
        except ImportError as err:
            logger.critical(f"💥 Fatal resolution failure on required blueprint source file: {module_path}")
            raise err

        for token in target_blueprint_tokens:
            blueprint_instance = getattr(imported_module, token, None)
            if not isinstance(blueprint_instance, Blueprint):
                resolved_type_string = type(blueprint_instance).__name__ if blueprint_instance is not None else "NoneType"
                raise RuntimeError(
                    f"Configuration Violation: Expected Blueprint token '{token}' within context path '{module_path}'. "
                    f"Received invalid object mapping reference of type: {resolved_type_string}."
                )

            tracking_key = (module_path, token)
            if tracking_key in resolved_tracking_keys or blueprint_instance.name in registered_blueprint_names:
                raise RuntimeError(f"Architecture Violation: Detected duplicate hard-coded registration for blueprint: {blueprint_instance.name}")
                
            resolved_tracking_keys.add(tracking_key)
            registered_blueprint_names.add(blueprint_instance.name)
            compiled_registry.append((module_path, token, blueprint_instance))

    # Phase 2: Processing Auto-Discovery Sequences
    for discovered_module in _iter_blueprint_modules():
        current_module_path = discovered_module.__name__
        for token, blueprint_instance in _discover_blueprints_in_module(discovered_module):
            tracking_key = (current_module_path, token)
            
            # Skip if either the key or the internal blueprint name has been claimed
            if tracking_key in resolved_tracking_keys or blueprint_instance.name in registered_blueprint_names:
                continue
                
            resolved_tracking_keys.add(tracking_key)
            registered_blueprint_names.add(blueprint_instance.name)
            compiled_registry.append((current_module_path, token, blueprint_instance))

    return compiled_registry


# ---------------------------------------------------------------------------
# RUNTIME INTEGRATION ENGINE
# ---------------------------------------------------------------------------

def register_blueprints(app: Flask) -> None:
    """
    Idempotently wire all discovered and explicit blueprints into the Flask engine.
    
    Guarantees:
        - Absolute execution order parity across isolated application spins.
        - Hard collision mitigation using native blueprint endpoint namespaces.
        - Preservation of boundaries established by external custom factories.
    """
    blueprint_registry_matrix = _build_blueprint_registry()

    for origin_path, export_token, blueprint in blueprint_registry_matrix:
        # Prevent collision exceptions from firing if a custom execution container registered this boundary early
        if blueprint.name in app.blueprints:
            app.logger.debug(
                "⏭️ Bypassing integration for blueprint '%s' from path: %s (Registered early via application factory context)",
                blueprint.name,
                origin_path,
            )
            continue

        try:
            app.register_blueprint(blueprint)
            app.logger.info(
                "🔗 Operational blueprint link bound: %s -> %s (Prefix mapping: %s)",
                export_token,
                origin_path,
                blueprint.url_prefix if blueprint.url_prefix is not None else "ROOT",
            )
        except Exception as initialization_error:
            app.logger.exception(
                "❌ Execution Engine Aborted registration loop for blueprint: '%s' from origin context: '%s' | Internal Trace: %s",
                export_token,
                origin_path,
                initialization_error,
            )
            raise initialization_error

    logger.info("✅ All blueprints registered successfully (explicit + auto-discovered).")


# ---------------------------------------------------------------------------
# MONITORING & TELEMETRY INTERACTION MAPS
# ---------------------------------------------------------------------------

def validate_blueprints_graph(app: Flask) -> None:
    """
    Analyze active URL path mappings across active blueprint instances to detect overlaps.
    """
    prefix_collision_matrix: dict[str | None, list[str]] = {}

    for blueprint_name, blueprint_object in app.blueprints.items():
        prefix_collision_matrix.setdefault(blueprint_object.url_prefix, []).append(blueprint_name)

    logger.info("📊 Processing Application Routing Topology Tree Graph:")
    for configured_prefix, associated_blueprints in sorted(prefix_collision_matrix.items(), key=lambda node: str(node[0])):
        logger.info("  Mapping Node Prefix: %r -> Bound Blueprints: %s", configured_prefix, associated_blueprints)

    overlapping_prefix_allocations = {
        prefix_path: blueprint_list 
        for prefix_path, blueprint_list in prefix_collision_matrix.items() 
        if prefix_path is not None and len(blueprint_list) > 1
    }

    if overlapping_prefix_allocations:
        logger.warning("⚠️ Telemetry Alert: Overlapping prefix namespaces detected in the current routing configuration matrix:")
        for duplicate_prefix, colliding_blueprints in overlapping_prefix_allocations.items():
            logger.warning("  Ambiguous Target Prefix Path: %r shared across components: %s", duplicate_prefix, colliding_blueprints)
    else:
        logger.info("✅ No overlapping blueprint url_prefix assignments detected.")