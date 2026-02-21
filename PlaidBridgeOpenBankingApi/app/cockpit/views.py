# app/cockpit/views.py

import json
from datetime import datetime

from flask import (
    Blueprint,
    Response,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    session,
)
from flask_login import current_user, login_required

from app.constants import OPERATOR_MODE_KEY  # <--- ADDED IMPORT
from app.extensions import db
from app.models import User
from app.models.borrower_card import BorrowerCard
from app.models.underwriter import UnderwriterAgent
from app.models.vault_transaction import VaultTransaction
from app.telemetry.ttl_emit import ttl_emit
from app.tiles.login_link_pulse_tile import get_login_link_status
from app.utils.export import serialize_logs_as_csv, serialize_logs_as_json
from app.utils.redis_utils import get_redis_client

# One unified cockpit blueprint
cockpit_bp = Blueprint("cockpit", __name__, url_prefix="/admin/cockpit")


# Stub for log_route_usage; replace with actual logging implementation if available elsewhere
def log_route_usage(endpoint: str):
    """Log route usage. Stub implementation; integrate with your logging system."""
    current_app.logger.info(f"Route used: {endpoint}")


# -------------------------------------------------------------------
# Decorator for TTL + route usage logging
# -------------------------------------------------------------------
def cockpit_instrument(ttl_key, ttl=300):
    """
    Decorator to wrap cockpit views with:
    - Route usage logging
    - TTL health emit (success/error)
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            client = get_redis_client()
            log_route_usage(request.endpoint)
            try:
                # Pass the Redis client to the wrapped function
                result = func(client, *args, **kwargs)
                # Use canonical ttl_emit signature: client= and ttl=
                ttl_emit(key=ttl_key, status="success", client=client, ttl=ttl)
                return result
            except Exception as e:
                # Use canonical ttl_emit signature: client= and ttl=
                ttl_emit(key=ttl_key, status="error", client=client, ttl=ttl)
                current_app.logger.warning(f"[Cockpit] {request.endpoint} failed: {e}")
                return render_template("error.html", error=str(e)), 500

        wrapper.__name__ = func.__name__
        return wrapper

    return decorator


# -------------------------------------------------------------------
# Session TTL refresh for operator mode
# -------------------------------------------------------------------
@cockpit_bp.before_request
@login_required
def refresh_operator_ttl():
    """Refresh Redis TTL for operator sessions on cockpit route access."""
    if session.get(OPERATOR_MODE_KEY):  # <--- REPLACED "operator_mode" (CHECK 1/2)
        redis = get_redis_client()
        redis.expire(f"operator_session:{current_user.email}", 900)


# -------------------------------------------------------------------
# Identity events view
# -------------------------------------------------------------------
@cockpit_bp.route("/identity-events")
@login_required
@cockpit_instrument("ttl:view:identity_events")
def identity_events_view(client):
    """Shows the last 50 identity events for cockpit operator tile."""
    event_strings = client.lrange("identity_events_stream", 0, 49)
    events = [json.loads(event_str) for event_str in event_strings]
    return render_template("identity_events.html", events=events)


# -------------------------------------------------------------------
# Me dashboard
# -------------------------------------------------------------------
@cockpit_bp.route("/me")
@login_required
@cockpit_instrument("ttl:view:me")
def me_view(client):
    """Shows the current user's cockpit identity panel."""
    return render_template("me.html", user=current_user)


# -------------------------------------------------------------------
# System health pulse
# -------------------------------------------------------------------
@cockpit_bp.route("/system-health")
@login_required
@cockpit_instrument("ttl:view:system_health")
def system_health_view(client):
    """
    Example: pull various Redis keys and system metrics for an operator dashboard.
    """
    metrics = {
        "redis_ping": client.ping(),
        "active_users": client.get("active_users_count") or 0,
    }
    return render_template("system_health.html", metrics=metrics)


# -------------------------------------------------------------------
# Ignite Dashboard (admin cockpit)
# -------------------------------------------------------------------
@cockpit_bp.route("/ignite-dashboard")
@login_required
def ignite_dashboard():
    """Renders the main cockpit dashboard with various tiles."""
    client = getattr(current_app, "redis_client", None) or get_redis_client()

    key = f"operator_session:{current_user.email}"
    ttl = None
    seeded = False

    # Read TTL safely
    if client:
        try:
            ttl = client.ttl(key)
        except Exception as e:
            current_app.logger.error(f"[cockpit.ignite_dashboard] Redis ttl failed for {key} — {e}")
    else:
        current_app.logger.error(
            f"[cockpit.ignite_dashboard] Redis unavailable — skipping ttl for {key}"
        )

    # Seed operator session if missing/expired
    if ttl is None or ttl < 0:
        if client:
            try:
                client.setex(key, 900, "true")
                ttl, seeded = 900, True
            except Exception as e:
                current_app.logger.error(
                    f"[cockpit.ignite_dashboard] Redis setex failed for {key} — {e}"
                )
        else:
            current_app.logger.error(
                f"[cockpit.ignite_dashboard] Redis unavailable — skipping setex seed for {key}"
            )

    # Low TTL alert
    if ttl is not None and ttl < 30:
        alert_flag_key = f"low_ttl_alert_fired:{current_user.email}"
        if client:
            try:
                if not client.exists(alert_flag_key):
                    event = {
                        "event_type": "LOW_TTL_ALERT",
                        "by": current_user.email,
                        "ttl_remaining": ttl,
                        "timestamp": int(datetime.utcnow().timestamp()),
                        "severity": "critical",
                    }
                    client.set(
                        f"identity_event:low_ttl:{event['timestamp']}",
                        json.dumps(event),
                    )
                    client.setex(alert_flag_key, ttl if ttl > 0 else 30, "1")
            except Exception as e:
                current_app.logger.error(
                    f"[cockpit.ignite_dashboard] Redis alert flow failed for "
                    f"{alert_flag_key} — {e}"
                )
        else:
            current_app.logger.error(
                "[cockpit.ignite_dashboard] Redis unavailable — skipping low TTL "
                f"alert for {alert_flag_key}"
            )

    # Gather ignition events
    keys = client.keys("identity_event:*")
    events = []
    for key in keys:
        raw = client.get(key)
        if raw:
            evt = json.loads(raw)
            if evt["event_type"] in [
                "CORTEX_IGNITION",
                "IGNITION_FAIL",
                "LOW_TTL_ALERT",
            ]:
                events.append(evt)
    events.sort(key=lambda e: e["timestamp"], reverse=True)

    cli_tile = {
        "status": "🟢 Reachable",
        "last_run": client.get("cli:last_run_timestamp") or "Never",
        "command_count": client.get("cli:registered_command_count") or "0",
        "trace": "TTL-backed trace from CLI emitter keys",
    }

    status = get_login_link_status()
    login_link_tile = {
        "title": "Login Link Health",
        "status": "🟢 Online" if status["route_present"] else "🔴 Missing",
        "endpoint_url": status["endpoint_url"] or "Unavailable",
        "ttl": status["ttl"],
        "timestamp": status["timestamp"],
        "trace": "Checked view_functions for route presence",
    }

    blueprint_names = list(current_app.blueprints.keys())
    blueprint_tile = {
        "count": len(blueprint_names),
        "names": blueprint_names,
        "trace": "Live introspection from current_app.blueprints",
    }

    session_bootstrap_ctx = {
        "method": (
            "Operator Cockpit" if session.get(OPERATOR_MODE_KEY) else "Standard Session"
        ),  # <--- REPLACED "operator_mode" (CHECK 2/2)
        "freshness": ttl or 0,
        "seeded": seeded,
    }

    return render_template(
        "admin/cockpit/ignite_dashboard.html",
        events=events,
        ttl=ttl,
        login_link_tile=login_link_tile,
        cli_tile=cli_tile,
        blueprint_tile=blueprint_tile,
        session_bootstrap_ctx=session_bootstrap_ctx,
    )


# -------------------------------------------------------------------
# Borrower card grid
# -------------------------------------------------------------------
@cockpit_bp.route("/borrower-card-grid")
@login_required
def borrower_card_grid():
    """Renders a grid view of borrower cards."""
    borrowers = User.query.filter_by(role="borrower").all()
    cards = []
    for b in borrowers:
        score = b.credit_score
        color = "green" if score > 700 else "orange" if score > 600 else "red"
        cards.append(
            {
                "name": b.username,
                "score": score,
                "color": color,
                "card_number": b.card_number,
                "expiration": b.card_expiration,
                "cvv": b.card_cvv,
            }
        )
    return render_template(
        "admin/cockpit/borrower_card_grid.html",
        cards=cards,
        current_time=datetime.utcnow(),
    )


# -------------------------------------------------------------------
# Vault metrics
# -------------------------------------------------------------------
@cockpit_bp.route("/card-vault/metrics")
@login_required
@cockpit_instrument("ttl:view:vault_metrics")
def vault_metrics(client=None):
    """Renders a view of the card vault's key metrics."""
    cards = BorrowerCard.query.all()
    now = datetime.utcnow()
    active = expiring = revoked = dormant = 0
    for card in cards:
        if card.revoked:
            revoked += 1
            continue
        # Card expiration date is stored as "MM/YY"
        exp_month, exp_year = map(int, card.expiration_date.split("/"))
        expiry_date = datetime(exp_year + 2000, exp_month, 1)

        if (expiry_date - now).days <= 30:
            expiring += 1
        elif card.last_used_at and (now - card.last_used_at).days > 90:
            dormant += 1
        else:
            active += 1

    total = len(cards)

    return render_template(
        "admin/cockpit/vault_metrics.html",
        active=active,
        expiring=expiring,
        dormant=dormant,
        revoked=revoked,
        total=total,
    )


# -------------------------------------------------------------------
# Card revoke / link / audit / export
# -------------------------------------------------------------------
@cockpit_bp.route("/revoke-card/<int:card_id>", methods=["POST"])
@login_required
def revoke_card(card_id):
    """Handles the revocation of a borrower's card."""
    redis = get_redis_client()
    card = BorrowerCard.query.get_or_404(card_id)
    card.revoked, card.last_used_at = True, datetime.utcnow()
    db.session.commit()
    event = {
        "event_type": "CARD_REVOKED",
        "by": current_user.email,
        "card_id": card.id,
        "timestamp": int(datetime.utcnow().timestamp()),
        "reason": "Delinquent borrowing pattern",
    }
    redis.set(f"identity_event:card:{card.id}:{event['timestamp']}", json.dumps(event))
    return redirect("/card-vault")


@cockpit_bp.route("/link-wallet/<int:card_id>", methods=["POST"])
@login_required
def link_wallet(card_id):
    """Handles the manual linking of a card to a wallet."""
    redis = get_redis_client()
    card = BorrowerCard.query.get_or_404(card_id)
    card.last_used_at = datetime.utcnow()
    db.session.commit()
    event = {
        "event_type": "CARD_LINKED_WALLET",
        "by": current_user.email,
        "card_id": card.id,
        "timestamp": int(datetime.utcnow().timestamp()),
        "method": "Operator Manual Link",
    }
    redis.set(f"identity_event:card:{card.id}:{event['timestamp']}", json.dumps(event))
    return redirect("/card-vault")


@cockpit_bp.route("/card-audit/<int:card_id>")
@login_required
def card_audit(card_id):
    """Renders a view of all audit logs for a specific card."""
    redis = get_redis_client()
    pattern = f"identity_event:card:{card_id}:*"
    keys = redis.keys(pattern)
    audit_logs = []
    for key in keys:
        raw = redis.get(key)
        if raw:
            audit_logs.append(json.loads(raw))
    audit_logs.sort(key=lambda log: log["timestamp"], reverse=True)
    return render_template("admin/cockpit/card_audit.html", logs=audit_logs, card_id=card_id)


@cockpit_bp.route("/card-vault-export")
@login_required
def card_vault_export():
    """Exports card-related identity events in JSON or CSV format."""
    redis = get_redis_client()
    keys = redis.keys("identity_event:card:*")
    logs = []
    for key in keys:
        raw = redis.get(key)
        if raw:
            logs.append(json.loads(raw))
    logs.sort(key=lambda log: log["timestamp"], reverse=True)
    export_format = request.args.get("format")
    if export_format == "json":
        return Response(
            serialize_logs_as_json(logs),
            mimetype="application/json",
            headers={"Content-Disposition": "attachment;filename=vault_export.json"},
        )
    elif export_format == "csv":
        return Response(
            serialize_logs_as_csv(logs),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=vault_export.csv"},
        )
    return render_template("admin/cockpit/card_vault_export.html", logs=logs)


@cockpit_bp.route("/underwriter-intake")
@login_required
def underwriter_intake():
    """Renders a view of all underwriter agents."""
    underwriters = UnderwriterAgent.query.order_by(UnderwriterAgent.verified_at.desc()).all()
    return render_template("admin/cockpit/underwriter_intake.html", underwriters=underwriters)


@cockpit_bp.route("/vault-intake")
@login_required
def vault_intake():
    """Renders a view of all vault transactions."""
    txns = VaultTransaction.query.order_by(VaultTransaction.received_at.desc()).all()
    return render_template("admin/cockpit/vault_intake.html", txns=txns)


@cockpit_bp.route("/debug/blueprints")
@login_required
def debug_blueprints():
    """Returns a JSON payload of all registered Flask blueprints."""
    registered = {}
    for name, bp in current_app.blueprints.items():
        registered[name] = {"url_prefix": bp.url_prefix, "import_name": bp.import_name}
    return jsonify(registered)