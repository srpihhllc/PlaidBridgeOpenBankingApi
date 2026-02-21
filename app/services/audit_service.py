# =============================================================================
# FILE: app/services/audit_service.py
# DESCRIPTION: Cockpit audit logging + blueprint audit summary.
# =============================================================================

from datetime import datetime

from app.extensions import db

# -----------------------------------------------------------------------------
# Database Model (inline import to avoid circulars)
# -----------------------------------------------------------------------------
# If you already have an AuditLog model, remove this and import it instead.
# Otherwise, this creates a simple audit table.
# -----------------------------------------------------------------------------


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(64), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


# -----------------------------------------------------------------------------
# Cockpit Audit Logger
# -----------------------------------------------------------------------------


def log_event(event_type: str, message: str):
    """Record an audit event for cockpit visibility."""
    entry = AuditLog(event_type=event_type, message=message)
    db.session.add(entry)
    db.session.commit()
    return entry


def get_recent_events(limit=50):
    """Return the most recent audit events."""
    return AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(limit).all()


# -----------------------------------------------------------------------------
# Blueprint Audit Summary (your existing tile)
# -----------------------------------------------------------------------------


def get_blueprint_audit():
    """Return a simple audit summary for the cockpit dashboard tile."""
    return {
        "last_audit_date": datetime.utcnow().isoformat(),
        "audit_status": "Pass",
        "audit_issues": 0,
    }
