# app/blueprints/tracer_routes.py

from flask import Blueprint, jsonify
from flask_login import login_required

from app.decorators import admin_required

tracer_bp = Blueprint("tracer", __name__, url_prefix="/tracer")


@tracer_bp.route("/template_tracer")
@login_required
@admin_required
def template_tracer():
    """Admin-only, non-destructive template tracer stub."""
    return jsonify({
        "status": "stub",
        "endpoint": "tracer.template_tracer",
        "message": "Template tracer stub (no-op).",
    }), 501
