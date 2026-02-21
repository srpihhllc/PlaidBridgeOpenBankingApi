# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tiles/cli_inspector.py

from flask import Blueprint, current_app, jsonify

from app.utils.redis_utils import get_redis_client  # ✅ centralised, SSL‑safe client

tile_cli_inspector = Blueprint("tile_cli_inspector", __name__)


@tile_cli_inspector.route("/tile/cli-inspector", methods=["GET"])
def cli_inspector_view():
    """
    Returns a JSON list of all TTL-backed CLI commands
    and their last-run timestamps.
    """
    r = get_redis_client()
    if not r:
        current_app.logger.error("[cli_inspector] Redis unavailable — cannot fetch CLI commands")
        return jsonify({"error": "Redis unavailable"}), 503

    commands = []

    try:
        for key in r.scan_iter("ttl:cli:*"):
            cmd_name = key.decode().split(":")[-1]
            last_run = r.get(key)
            commands.append(
                {
                    "command": cmd_name,
                    "last_run": last_run.decode() if last_run else "—",
                    "status": "✓" if last_run else "idle",
                }
            )
    except Exception as e:
        current_app.logger.error(f"[cli_inspector] Failed to scan CLI keys: {e}")
        return jsonify({"error": "Failed to fetch CLI commands"}), 500

    return jsonify({"commands": sorted(commands, key=lambda x: x["command"])})
