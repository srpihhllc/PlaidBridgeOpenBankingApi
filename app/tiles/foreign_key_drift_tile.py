# app/tiles/foreign_key_drift_tile.py

from flask import Blueprint, render_template, current_app
from sqlalchemy import inspect

from app.extensions import db

foreign_key_drift_tile = Blueprint("foreign_key_drift_tile", __name__)


@foreign_key_drift_tile.route("/foreign_key_drift")
def foreign_key_drift():
    """
    Inspect foreign key drift at runtime inside an application context.
    Use db.get_engine(current_app) so the engine is resolved for the active app
    and avoid "Working outside of application context" errors.
    """
    drift_report = []

    # Resolve engine for the active Flask app and run inspection inside app context
    with current_app.app_context():
        engine = db.get_engine(current_app)
        inspector = inspect(engine)

        table_names = inspector.get_table_names() or []
        for table_name in table_names:
            fks = inspector.get_foreign_keys(table_name) or []
            for fk in fks:
                ref_table = fk.get("referred_table")
                ref_columns = fk.get("referred_columns")
                if not ref_table or not ref_columns:
                    drift_report.append(
                        {
                            "table": table_name,
                            "fk_columns": fk.get("constrained_columns"),
                            "issue": "Missing reference table or columns",
                        }
                    )
                else:
                    # Check existence of referenced table using the already-fetched table list
                    if ref_table not in table_names:
                        drift_report.append(
                            {
                                "table": table_name,
                                "fk_columns": fk.get("constrained_columns"),
                                "issue": f"Referenced table '{ref_table}' does not exist",
                            }
                        )

    return render_template("foreign_key_drift_tile.html", drift_report=drift_report)
