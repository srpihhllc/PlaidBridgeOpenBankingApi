# app/tiles/foreign_key_drift_tile.py

from flask import Blueprint, render_template
from sqlalchemy import inspect
from yourapp import db  # adjust import to match your app structure

foreign_key_drift_tile = Blueprint("foreign_key_drift_tile", __name__)


@foreign_key_drift_tile.route("/foreign_key_drift")
def foreign_key_drift():
    inspector = inspect(db.engine)
    drift_report = []

    for table_name in inspector.get_table_names():
        fks = inspector.get_foreign_keys(table_name)
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
            elif ref_table not in inspector.get_table_names():
                drift_report.append(
                    {
                        "table": table_name,
                        "fk_columns": fk.get("constrained_columns"),
                        "issue": f"Referenced table '{ref_table}' does not exist",
                    }
                )

    return render_template("foreign_key_drift_tile.html", drift_report=drift_report)
