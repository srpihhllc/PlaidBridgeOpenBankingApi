# app/cockpit/tiles/__init__.py

from flask import Flask

from app.cockpit.tiles.blueprint_inspector import tile_blueprint_inspector

# Cockpit-grade tile blueprints
from app.tiles.cli_inspector import tile_cli_inspector

from .api_usage_tile import bp_api_usage
from .ignition_trace import bp_ignition
from .login_trace_monitor import bp_login
from .mutation_submit_tile import bp_mutation
from .mysql_auth_monitor import mysql_monitor


def register_tiles(app: Flask):
    """
    Registers all cockpit tiles into the Flask app.
    Each tile is isolated by blueprint for audit visibility and trace alignment.
    """
    try:
        app.register_blueprint(mysql_monitor, url_prefix="/cockpit")
        print("[✔] MySQL Auth Health Monitor registered at /cockpit/mysql-auth-health")
    except Exception as e:
        print(f"[❌] Error registering mysql_monitor: {e}")

    try:
        app.register_blueprint(bp_ignition)
        print("[✔] CortexIgnitionPulse tile registered at /cockpit/ignition")
    except Exception as e:
        print(f"[❌] Error registering bp_ignition: {e}")

    try:
        app.register_blueprint(bp_login)
        print("[✔] LoginTraceMonitor tile registered at /cockpit/login-trace")
    except Exception as e:
        print(f"[❌] Error registering bp_login: {e}")

    try:
        app.register_blueprint(bp_mutation)
        print("[✔] MutationSubmit tile registered at /cockpit/mutation")
    except Exception as e:
        print(f"[❌] Error registering bp_mutation: {e}")

    try:
        app.register_blueprint(bp_api_usage)
        print("[✔] APIKeyAccountUsage tile registered at /cockpit/api-usage")
    except Exception as e:
        print(f"[❌] Error registering bp_api_usage: {e}")

    try:
        app.register_blueprint(tile_cli_inspector, url_prefix="/cockpit")
        print("[✔] CLI Inspector registered at /cockpit/tile/cli-inspector")
    except Exception as e:
        print(f"[❌] Error registering CLI Inspector: {e}")

    try:
        app.register_blueprint(tile_blueprint_inspector, url_prefix="/cockpit")
        print("[✔] Blueprint Inspector registered at /cockpit/blueprint_inspector")
    except Exception as e:
        print(f"[❌] Error registering Blueprint Inspector: {e}")
