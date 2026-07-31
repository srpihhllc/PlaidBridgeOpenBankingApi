# =============================================================================
# FILE: app/blueprints/registry_ui_routes.py
# DESCRIPTION: UI route for server-side rendered admin/registry template
# =============================================================================

from flask import Blueprint, render_template, current_app
from app.services.registry import get_service_registry

registry_ui_bp = Blueprint("registry_ui", __name__, url_prefix="/registry")

@registry_ui_bp.get("/")
def show_registry_html():
    """Renders the HTML layout view using the live filesystem discovery context."""
    try:
        services = get_service_registry()
        return render_template("registry.html", registries=services, count=len(services))
    except Exception as err:
        current_app.logger.error(f"❌ Registry HTML rendering failed: {err}")
        return render_template("registry.html", registries=[], count=0, error=str(err))