# =============================================================================
# FILE: cockpit/tiles/lender_risk_tile.py
# DESCRIPTION: Cockpit tile surfacing lender risk signals, AI evaluations,
#              compliance violations, and fraud trend indicators.
# =============================================================================

import json
from datetime import datetime

from flask import Blueprint, render_template
from sqlalchemy import desc

from app.models.fraud_report import FraudReport
from app.models.schema_event import SchemaEvent
from app.utils.redis_utils import get_redis_client

lender_risk_tile_bp = Blueprint(
    "lender_risk_tile_bp", __name__, url_prefix="/cockpit/tiles/lender_risk"
)


# -----------------------------------------------------------------------------
# Helper: Load recent AI risk evaluations from Redis
# -----------------------------------------------------------------------------
def load_ai_risk_logs(limit=20):
    r = get_redis_client()
    if not r:
        return []

    keys = sorted([k.decode() for k in r.keys("grants_composed:*")], reverse=True)[:limit]

    logs = []
    for key in keys:
        try:
            raw = r.get(key)
            if raw:
                logs.append(json.loads(raw))
        except Exception:
            continue

    return logs


# -----------------------------------------------------------------------------
# Helper: Load recent fraud trend summaries
# -----------------------------------------------------------------------------
def load_recent_fraud_cases(limit=20):
    cases = FraudReport.query.order_by(desc(FraudReport.timestamp)).limit(limit).all()

    return [
        {
            "id": c.id,
            "transaction_id": c.transaction_id,
            "reason": c.flagged_reason,
            "timestamp": c.timestamp.isoformat(),
        }
        for c in cases
    ]


# -----------------------------------------------------------------------------
# Helper: Load recent lender self-link events
# -----------------------------------------------------------------------------
def load_lender_events(limit=20):
    events = (
        SchemaEvent.query.filter(
            SchemaEvent.event_type.in_(
                [
                    "LENDER_SELF_LINKED",
                    "LENDER_SELF_LINK_BLOCKED",
                    "LENDER_RISK_ALERT",
                ]
            )
        )
        .order_by(desc(SchemaEvent.timestamp))
        .limit(limit)
        .all()
    )

    return [
        {
            "event_type": e.event_type,
            "detail": e.detail,
            "timestamp": e.timestamp.isoformat(),
            "user_id": e.user_id,
        }
        for e in events
    ]


# -----------------------------------------------------------------------------
# Main Tile Route
# -----------------------------------------------------------------------------
@lender_risk_tile_bp.route("/", methods=["GET"])
def lender_risk_tile():
    """
    Cockpit tile showing:
    - Recent lender self-link attempts
    - AI risk evaluations
    - Fraud trend indicators
    - Compliance violations
    - Telemetry counters
    """

    # Load telemetry counters from Redis
    r = get_redis_client()
    counters = {}
    if r:
        for key in [
            "lender_self_link_success",
            "lender_self_link_fail",
            "lender_self_link_blocked_risk",
            "link_request_created",
            "link_code_issued",
            "link_finalized_success",
        ]:
            try:
                val = r.get(key)
                counters[key] = int(val.decode()) if val else 0
            except Exception:
                counters[key] = 0

    context = {
        "ai_risk_logs": load_ai_risk_logs(),
        "fraud_cases": load_recent_fraud_cases(),
        "lender_events": load_lender_events(),
        "counters": counters,
        "timestamp": datetime.utcnow().isoformat(),
    }

    return render_template("admin/cockpit/lender_risk_tile.html", **context)


# -----------------------------------------------------------------------------
# Heatmap Visualization Route
# -----------------------------------------------------------------------------
@lender_risk_tile_bp.route("/heatmap", methods=["GET"])
def lender_risk_heatmap():
    """
    Render a heatmap visualization of lender risk over time.
    Groups SchemaEvent entries by day and counts:
    - LENDER_RISK_ALERT events (high‑risk lenders)
    - LENDER_SELF_LINKED events (successful verifications)
    """

    # Fetch relevant events
    events = (
        SchemaEvent.query.filter(
            SchemaEvent.event_type.in_(["LENDER_RISK_ALERT", "LENDER_SELF_LINKED"])
        )
        .order_by(SchemaEvent.timestamp.asc())
        .all()
    )

    # Aggregate counts per day
    risk_data = {}
    for e in events:
        day = e.timestamp.date().isoformat()
        if day not in risk_data:
            risk_data[day] = {"alerts": 0, "links": 0}

        if e.event_type == "LENDER_RISK_ALERT":
            risk_data[day]["alerts"] += 1
        else:
            risk_data[day]["links"] += 1

    return render_template(
        "admin/cockpit/lender_risk_heatmap.html",
        risk_data=risk_data,
    )


# -----------------------------------------------------------------------------
# Drill‑Down: Events for a Specific Day
# -----------------------------------------------------------------------------
@lender_risk_tile_bp.route("/day/<date_str>", methods=["GET"])
def lender_risk_day_detail(date_str):
    """
    Drill‑down page showing all lender‑risk activity for a specific day.
    Includes:
    - Risk alerts
    - Self‑link attempts
    - Fraud cases
    - AI evaluations (if timestamps match)
    """

    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return render_template("admin/cockpit/lender_risk_day_invalid.html", date_str=date_str)

    # Start/end of day
    start_dt = datetime.combine(target_date, datetime.min.time())
    end_dt = datetime.combine(target_date, datetime.max.time())

    # Schema events for that day
    events = (
        SchemaEvent.query.filter(SchemaEvent.timestamp >= start_dt)
        .filter(SchemaEvent.timestamp <= end_dt)
        .order_by(SchemaEvent.timestamp.asc())
        .all()
    )

    # Fraud cases for that day
    fraud_cases = (
        FraudReport.query.filter(FraudReport.timestamp >= start_dt)
        .filter(FraudReport.timestamp <= end_dt)
        .order_by(FraudReport.timestamp.asc())
        .all()
    )

    # AI logs (Redis) — filter by timestamp inside the JSON
    ai_logs = []
    for log in load_ai_risk_logs(limit=200):
        try:
            ts = datetime.fromisoformat(log.get("timestamp"))
            if start_dt <= ts <= end_dt:
                ai_logs.append(log)
        except Exception:
            continue

    return render_template(
        "admin/cockpit/lender_risk_day_detail.html",
        date_str=date_str,
        events=events,
        fraud_cases=fraud_cases,
        ai_logs=ai_logs,
    )


# -----------------------------------------------------------------------------
# Unified Lender Risk Overview Page
# -----------------------------------------------------------------------------
@lender_risk_tile_bp.route("/overview", methods=["GET"])
def lender_risk_overview():
    """
    Unified operator overview combining:
    - Recent lender events
    - Fraud cases
    - AI evaluations
    - Heatmap summary (aggregated)
    """

    # Load recent data
    recent_events = load_lender_events(limit=10)
    recent_fraud = load_recent_fraud_cases(limit=10)
    recent_ai = load_ai_risk_logs(limit=10)

    # Build a small heatmap preview (last 14 days)
    events = (
        SchemaEvent.query.filter(
            SchemaEvent.event_type.in_(["LENDER_RISK_ALERT", "LENDER_SELF_LINKED"])
        )
        .order_by(SchemaEvent.timestamp.asc())
        .all()
    )

    heatmap = {}
    for e in events:
        day = e.timestamp.date().isoformat()
        if day not in heatmap:
            heatmap[day] = {"alerts": 0, "links": 0}

        if e.event_type == "LENDER_RISK_ALERT":
            heatmap[day]["alerts"] += 1
        else:
            heatmap[day]["links"] += 1

    return render_template(
        "admin/cockpit/lender_risk_overview.html",
        recent_events=recent_events,
        recent_fraud=recent_fraud,
        recent_ai=recent_ai,
        heatmap=heatmap,
    )
