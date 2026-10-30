# =============================================================================
# FILE: app/blueprints/registry_ui_routes.py
# DESCRIPTION: UI route for server-side rendered admin/registry template
# =============================================================================

from flask import Blueprint, current_app, render_template

from app.services.registry import get_service_registry

registry_ui_bp = Blueprint("registry_ui", __name__, url_prefix="/registry")


@registry_ui_bp.route("/", methods=["GET"])
def show_registry_html() -> str:
    """Render the HTML registry view using the live filesystem discovery context."""
    try:
        services = get_service_registry()
        return render_template(
            "registry.html",
            registries=services,
            count=len(services),
        )
    except Exception as err:
        current_app.logger.error("❌ Registry HTML rendering failed: %s", err)
        return render_template(
            "registry.html",
            registries=[],
            count=0,
            error=str(err),
        )
