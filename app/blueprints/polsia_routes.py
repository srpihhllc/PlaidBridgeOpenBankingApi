#app/blueprints/polsia_routes.py

from functools import wraps
import hashlib
import hmac
import logging
import os

from flask import Blueprint, current_app, jsonify, request

from app.extensions import csrf

logger = logging.getLogger(__name__)

polsia_bp = Blueprint("polsia", __name__, url_prefix="/v1/webhooks/polsia")


def verify_polsia_signature(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        signature = request.headers.get("X-Polsia-Signature")
        if not signature:
            return jsonify({"detail": "Missing X-Polsia-Signature header"}), 401

        webhook_secret = current_app.config.get(
            "POLSIA_WEBHOOK_SECRET",
            os.getenv("POLSIA_WEBHOOK_SECRET", "default_secret_key"),
        )
        raw_body = request.get_data()

        expected_signature = hmac.new(
            key=webhook_secret.encode("utf-8"),
            msg=raw_body,
            digestmod=hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected_signature, signature):
            return jsonify({"detail": "Invalid webhook signature"}), 401

        return f(*args, **kwargs)

    return decorated_function


@polsia_bp.route("", methods=["POST"])
@csrf.exempt
@verify_polsia_signature
def handle_polsia_webhook():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"detail": "Malformed JSON payload"}), 400

    task_id = data.get("task_id")
    event = data.get("event")

    logger.info(f"Received Polsia webhook event '{event}' for task_id: {task_id}")

    # Async dispatch to Celery background task if available
    try:
        from app.workers.polsia_tasks import process_polsia_webhook_event
        process_polsia_webhook_event.delay(data)
    except Exception as exc:
        logger.warning(f"Could not enqueue Celery task directly: {exc}")

    return jsonify({"status": "acknowledged", "task_id": task_id}), 200