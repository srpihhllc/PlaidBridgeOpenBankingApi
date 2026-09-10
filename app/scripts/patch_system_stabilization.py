"""
Unified System Stabilization & Diagnostic Suite
-----------------------------------------------
1. Clean Operator Switcher (Session & Cookie Sync)
2. God-Mode Stabilization Patch (Safe Redirection & Context Binding)
3. Dashboard Crash Guard (Fallback Context & Error Handling)
4. Comprehensive Routing Topology Mapping Engine
"""

from functools import wraps

from flask import (
    Flask,
    current_app,
    jsonify,
    redirect,
    render_template_string,
    request,
    session,
    url_for,
)

# ==============================================================================
# SECTION 1: CLEAN OPERATOR SWITCHING SYSTEM
# ==============================================================================

OPERATOR_SESSION_KEY = "operator_mode"
OPERATOR_ROLES = {"GUEST": 0, "SUBSCRIBER": 1, "ADMIN": 2, "GOD_MODE": 3}


def set_operator_mode(mode_name: str, response_obj=None):
    """
    Safely transitions the active operator mode state across Flask Session
    and client cookies to prevent deserialization or out-of-sync drift.
    """
    mode = mode_name.upper()
    if mode not in OPERATOR_ROLES:
        raise ValueError(f"Invalid Operator Mode requested: {mode_name}")

    session[OPERATOR_SESSION_KEY] = {
        "role": mode,
        "level": OPERATOR_ROLES[mode],
        "active": True,
    }
    session.modified = True

    if response_obj:
        response_obj.set_cookie(
            "op_state",
            mode,
            httponly=True,
            samesite="Lax",
            secure=request.is_secure,
        )
    return response_obj


def get_current_operator():
    """Retrieves current operator metadata with fallback to GUEST."""
    return session.get(
        OPERATOR_SESSION_KEY,
        {"role": "GUEST", "level": OPERATOR_ROLES["GUEST"], "active": False},
    )


# ==============================================================================
# SECTION 2: GOD-MODE STABILIZATION PATCH
# ==============================================================================


def stabilize_god_mode_route(app: Flask):
    """
    Decorates/overrides the /ignite-cortex route to ensure God-Mode state
    is bound clean before redirecting to the administrative cockpit.
    """

    @app.route("/ignite-cortex", methods=["GET"])
    def ignite_cortex_stabilized():
        try:
            current_app.logger.info(
                "🔑 Initiating God-Mode operator escalation..."
            )

            # 1. Target endpoint determination with fallback check
            target_endpoint = (
                "admin.cockpit"
                if "admin.cockpit" in app.view_functions
                else "admin_bp.cockpit"
            )
            if target_endpoint not in app.view_functions:
                # Direct route path fallback if blueprint endpoint aliases are unmapped
                target_url = "/admin/cockpit"
            else:
                target_url = url_for(target_endpoint)

            # 2. Construct response and bind session/cookie states cleanly
            response = redirect(target_url)
            set_operator_mode("GOD_MODE", response)

            current_app.logger.info(
                f"✅ God-Mode active. Redirecting to {target_url}"
            )
            return response

        except Exception as err:
            current_app.logger.error(
                f"❌ God-Mode Ignition Failure: {str(err)}", exc_info=True
            )
            # Fail-safe redirect to baseline admin or root
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "God-Mode escalation failed to serialize.",
                        "detail": str(err),
                    }
                ),
                500,
            )


# ==============================================================================
# SECTION 3: DASHBOARD CRASH DIAGNOSTIC PATCH
# ==============================================================================


def safe_dashboard_renderer(
    template_name: str, fallback_template_str: str = None
):
    """
    Decorator for cockpit/dashboard routes that catches render/data exceptions
    and returns a safe diagnostic error payload instead of an uncaught HTTP 500.
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except Exception as exc:
                current_app.logger.error(
                    f"💥 Dashboard Rendering Error in [{f.__name__}]: {exc}",
                    exc_info=True,
                )

                # Context payload for debugging
                debug_payload = {
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "endpoint": request.endpoint,
                    "operator_state": get_current_operator(),
                }

                if (
                    request.is_json
                    or request.headers.get("X-Requested-With")
                    == "XMLHttpRequest"
                ):
                    return (
                        jsonify(
                            {"status": "error", "diagnostics": debug_payload}
                        ),
                        500,
                    )

                fallback_html = (
                    fallback_template_str
                    or """
                <!doctype html>
                <title>Dashboard Recovered</title>
                <body style="font-family: monospace; background: #1a1a1a; color: #f8f8f2; padding: 2rem;">
                    <h2 style="color: #ff5555;">⚠️ Dashboard Diagnostic Catch Active</h2>
                    <p>An uncaught view/template exception occurred in <strong>{{ endpoint }}</strong>.</p>
                    <hr style="border-color: #444;">
                    <h3>Trace Summary</h3>
                    <pre style="background: #282a36; padding: 1rem; border-radius: 4px; color: #ff79c6;">
Exception: {{ error_type }}
Details:   {{ error_message }}
User Mode: {{ operator_state.role }}
                    </pre>
                </body>
                """
                )
                return render_template_string(
                    fallback_html, **debug_payload
                ), 500

        return decorated_function

    return decorator


# ==============================================================================
# SECTION 4: ROUTING TOPOLOGY MAPPER
# ==============================================================================


def generate_routing_topology_map(app: Flask):
    """
    Scans the application rule tree and dumps a detailed routing tree,
    mapping prefixes, endpoints, HTTP methods, and Blueprint origins.
    """
    topology = {}

    for rule in app.url_map.iter_rules():
        endpoint_name = rule.endpoint
        blueprint_name = (
            endpoint_name.split(".")[0] if "." in endpoint_name else "ROOT"
        )

        methods = [m for m in rule.methods if m not in ("HEAD", "OPTIONS")]

        route_entry = {
            "rule": rule.rule,
            "endpoint": endpoint_name,
            "methods": methods,
            "blueprint": blueprint_name,
        }

        if blueprint_name not in topology:
            topology[blueprint_name] = []
        topology[blueprint_name].append(route_entry)

    return topology


def print_routing_topology(app: Flask):
    """Prints a formatted ASCII topology tree to standard output."""
    topology = generate_routing_topology_map(app)

    print("\n" + "=" * 80)
    print(" 📊 FULL APPLICATION ROUTING TOPOLOGY MAP")
    print("=" * 80)

    for bp, routes in sorted(topology.items()):
        print(f"\n🔹 Blueprint Node: [{bp}] ({len(routes)} active endpoints)")
        for r in sorted(routes, key=lambda x: x["rule"]):
            methods_str = "|".join(r["methods"])
            print(
                f"  ├── {r['rule']:<35} [{methods_str:<10}] -> {r['endpoint']}"
            )

    print("\n" + "=" * 80 + "\n")


# ==============================================================================
# CLI INITIALIZER & PATCH TESTER
# ==============================================================================

if __name__ == "__main__":
    from app import create_app

    print("🔧 Initializing application for stabilization patching...")
    flask_app = create_app()

    # Apply God-Mode Route Patch
    stabilize_god_mode_route(flask_app)

    # Output Full Routing Topology
    print_routing_topology(flask_app)

    # Test God-Mode endpoint locally via Test Client
    with flask_app.test_client() as client:
        print("🧪 Testing /ignite-cortex route execution...")
        res = client.get("/ignite-cortex", follow_redirects=False)
        print(f"Response Code: {res.status_code}")
        print(f"Redirect URL:  {res.headers.get('Location')}")
        print(f"Cookie Output: {res.headers.get('Set-Cookie')}")
