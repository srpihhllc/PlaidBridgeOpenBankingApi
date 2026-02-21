# app/tiles/login_link_pulse_tile.py

from flask import current_app

from app.cockpit.lib.ttl import ttl_cache


@ttl_cache(seconds=30)
def get_login_link_status():
    view_funcs = current_app.view_functions
    return {
        "route_present": "auth.login_user_route" in view_funcs,
        "endpoint_url": view_funcs.get("auth.login_user_route"),
    }
