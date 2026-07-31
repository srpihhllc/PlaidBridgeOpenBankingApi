# app/blueprints/tracer_routes.py
from flask import Blueprint, jsonify

tracer_bp = Blueprint("tracer", __name__, url_prefix="/tracer")

@tracer_bp.route("/template_tracer")
def template_tracer():
    """Template tracer stub used by admin tiles; non-destructive audit stub."""
    return jsonify({
        "status": "stub",
        "endpoint": "tracer.template_tracer",
        "message": "Template tracer stub (no-op)."
    }), 501
