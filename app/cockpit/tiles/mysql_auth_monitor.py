# cockpit/tiles/mysql_auth_monitor.py

from flask import Blueprint
from sqlalchemy.exc import OperationalError

from app.extensions import db
from app.telemetry.ttl_emit import ttl_emit

mysql_monitor = Blueprint("mysql_monitor", __name__)


@mysql_monitor.route("/cockpit/mysql-auth-health", methods=["GET"])
def mysql_auth_health():
    try:
        result = db.session.execute("SELECT 1")
        ttl_emit("ttl:mysql:access:srpihhllc", status="success")
        return {
            "status": "✅ connected",
            "latency_ms": result.context.execution_options.get("max_row_buffer", "n/a"),
        }
    except OperationalError as e:
        ttl_emit("ttl:mysql:access:srpihhllc", status="error")
        return {"status": "❌ error", "details": str(e)}, 503
