# /home/srpihhllc/PlaidBridgeOpenBankingApi/mock_api.py
"""
Lightweight mock API used for local testing.
- Exposes create_mock_app() factory as the canonical entrypoint.
- Preserves original routes and behavior.
- Optionally exposes a legacy module-level `app` when EXPORT_LEGACY_APP=1 or true.
"""

import os
import secrets

from flask import Flask, jsonify, request
from flask_cors import CORS


def create_mock_app() -> Flask:
    """Factory that creates the mock API Flask instance (flask_app)."""
    flask_app = Flask(__name__)
    CORS(flask_app)

    @flask_app.route("/mock-endpoint", methods=["POST"])
    def mock_endpoint():
        # Keep this endpoint simple and avoid unused locals
        request.get_json(silent=True)
        # Mock response logic (kept simple)
        response = {
            "accountNumber": "7030 3429 9651",
            "routingNumber": "026 015 053",
            "accountName": "Found Bank Account",
        }
        return jsonify(response), 200

    @flask_app.route("/statements", methods=["GET"])
    def get_statements():
        statements = [
            {"date": "2024-01-01", "description": "Deposit", "amount": "500.00"},
            {"date": "2024-02-01", "description": "Withdrawal", "amount": "-200.00"},
        ]
        return jsonify(statements), 200

    @flask_app.route("/<path:path>", methods=["GET", "POST"])
    def catch_all(path):
        return jsonify({"message": "Access Denied"}), 403

    @flask_app.route("/login", methods=["POST"])
    def login():
        payload = request.get_json(silent=True) or {}
        username = payload.get("username", "") or ""
        password = payload.get("password", "") or ""
        # Use a constant-time compare for secrets to reduce timing-attack surface
        expected_user = os.getenv("MOCK_USERNAME", "")
        expected_pass = os.getenv("MOCK_PASSWORD", "")
        if secrets.compare_digest(username, expected_user) and secrets.compare_digest(
            password, expected_pass
        ):
            return jsonify({"message": "Login successful"}), 200
        return jsonify({"message": "Invalid credentials"}), 403

    return flask_app


# Only export a legacy module-level `app` when the operator explicitly opts in.
# Accept "1" or "true" (case-insensitive) as truthy values.
_module_app: Flask | None = None
if os.getenv("EXPORT_LEGACY_APP", "0").lower() in ("1", "true"):
    try:
        _module_app = create_mock_app()
        app = _module_app  # legacy symbol for scripts/tests that import mock_api.app
    except Exception as exc:
        raise RuntimeError(f"Failed to construct legacy module app: {exc}") from exc

# Runnable entrypoint for quick manual testing (preserves original run behavior)
if __name__ == "__main__":
    server = create_mock_app()
    server.run(host="0.0.0.0", port=int(os.getenv("MOCK_API_PORT", "5000")))
