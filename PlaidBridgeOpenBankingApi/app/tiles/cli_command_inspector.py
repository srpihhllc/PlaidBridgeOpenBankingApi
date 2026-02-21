# app/tiles/cli_command_inspector.py

from flask import Blueprint, jsonify

from app.utils.redis_utils import get_redis_client

tile_cli_inspector = Blueprint("tile_cli_inspector", __name__)


@tile_cli_inspector.route("/tile/cli-inspector")
def cli_inspector_view():
    r = get_redis_client()
    commands = []

    if r:
        for name in r.scan_iter("ttl:cli:*"):  # All TTL-backed command runs
            cmd = name.decode().split(":")[-1]
            last_run = r.get(name)
            commands.append(
                {
                    "command": cmd,
                    "last_run": last_run.decode() if last_run else "—",
                    "status": "✓" if last_run else "idle",
                }
            )
    else:
        # Optional: mark Redis as unavailable in the response
        commands.append({"command": None, "last_run": None, "status": "❌ Redis unavailable"})

    return jsonify({"commands": sorted(commands, key=lambda x: (x["command"] or ""))})
