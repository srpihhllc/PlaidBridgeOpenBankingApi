# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/blueprints/pulse_routes.py


from flask import Blueprint, jsonify, make_response

pulse_bp = Blueprint("pulse", __name__, url_prefix="/pulse")


@pulse_bp.route("/health", methods=["GET"])
def health_check():
    """
    Health check endpoint for deployment monitoring.
    Used by:
    - Docker HEALTHCHECK
    - Azure Container Apps health probes
    - PythonAnywhere monitoring
    - Load balancers
    """
    health_status = {
        "status": "healthy",
        "service": "PlaidBridge Open Banking API",
        "version": "1.0.0"  # Update from environment or git tag
    }
    
    # Optional: Add database connectivity check
    # try:
    #     db.session.execute('SELECT 1')
    #     health_status["database"] = "connected"
    # except Exception as e:
    #     health_status["status"] = "unhealthy"
    #     health_status["database"] = "disconnected"
    
    status_code = 200 if health_status["status"] == "healthy" else 503
    
    resp = make_response(jsonify(health_status), status_code)
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@pulse_bp.route("/vault/<int:vault_id>", methods=["GET"])
def vault_pulse(vault_id):
    payload = {"vault_id": vault_id, "status": "ok", "data": None}
    resp = make_response(jsonify(payload))
    resp.headers["Cache-Control"] = "public, max-age=5"
    return resp


@pulse_bp.route("/access_token/<int:token_id>", methods=["GET"])
def access_token_pulse(token_id):
    payload = {"token_id": token_id, "status": "ok", "data": None}
    resp = make_response(jsonify(payload))
    resp.headers["Cache-Control"] = "public, max-age=5"
    return resp
