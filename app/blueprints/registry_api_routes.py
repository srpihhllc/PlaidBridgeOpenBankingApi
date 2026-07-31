# =============================================================================
# FILE: app/blueprints/registry_api_routes.py
# DESCRIPTION: API route for dynamic cockpit tile serialization
# =============================================================================

from flask import Blueprint, jsonify, current_app
from app.services.registry import get_service_registry

registry_api_bp = Blueprint("registry_api", __name__, url_prefix="/api/v1/registry")

@registry_api_bp.get("/")
def get_dynamic_registry_json():
    """Serves the 39 dynamic backend service objects directly to the Cockpit UI."""
    try:
        services = get_service_registry()
        return jsonify({
            "status": "healthy",
            "count": len(services),
            "services": [
                {
                    "name": s.name,
                    "module": s.module,
                    "description": s.description,
                    "icon": s.icon or "fa-cube",
                    "category": s.category or "general"
                }
                for s in services
            ]
        }), 200
    except Exception as err:
        current_app.logger.error(f"❌ Registry API payload delivery failed: {err}")
        return jsonify({"status": "degraded", "error": str(err)}), 500