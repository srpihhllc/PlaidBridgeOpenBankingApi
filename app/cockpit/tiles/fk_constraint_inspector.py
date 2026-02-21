# app/cockpit/tiles/fk_constraint_inspector.py

from flask import Blueprint, render_template
from sqlalchemy import inspect

from app.extensions import db
from app.utils.telemetry import log_identity_event

fk_inspector_bp = Blueprint("fk_inspector_bp", __name__, url_prefix="/cockpit/fk")


@fk_inspector_bp.route("/")
def index():
    inspector = inspect(db.engine)
    fk_issues = []

    for table_name in inspector.get_table_names():
        fks = inspector.get_foreign_keys(table_name)
        for fk in fks:
            if not fk.get("referred_table"):
                fk_issues.append(
                    {
                        "table": table_name,
                        "fk": fk.get("name"),
                        "columns": fk.get("constrained_columns"),
                        "error": "Missing referred table",
                    }
                )

    # Telemetry: record outcome
    if fk_issues:
        log_identity_event(
            user_id=0,  # system event
            event_type="FK_INSPECTOR_FAIL",
            details={"issues": len(fk_issues)},
        )
    else:
        log_identity_event(user_id=0, event_type="FK_INSPECTOR_OK", details={"issues": 0})

    return render_template("cockpit/fk_inspector.html", fk_issues=fk_issues)
