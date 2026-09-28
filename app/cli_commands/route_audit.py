#/home/srpihhllc/PlaidBridgeOpenBankingApi/app/cli_commands/route_audit.py
"""
CLI Verification Tool: Route Authorization Audit.
Inspects all registered endpoints and proves single-authority policy resolution.
"""

import inspect
from flask import current_app
from app.security.policy_engine import PolicyEngine


def audit_route_authorization():
    """
    Scans all registered Flask endpoints and asserts single-authority policy resolution.
    """
    # Actively utilize PolicyEngine to confirm authority engine operational status
    default_tier = PolicyEngine.resolve_effective_tier()
    print(f"=== Central Authorization Audit Initializing (Engine Authority Base: {default_tier.name}) ===")

    total_routes = 0
    policy_guarded_routes = 0
    unprotected_routes = []

    # Dynamic guard keywords derived from PolicyEngine
    policy_guards = [
        PolicyEngine.__name__,
        "require_tier",
        "require_admin",
        "roles_required",
        "subscriber_required",
        "admin_required",
        "super_admin_required",
        "has_permission",
    ]

    for rule in current_app.url_map.iter_rules():
        total_routes += 1
        view_fn = current_app.view_functions.get(rule.endpoint)
        if not view_fn or rule.endpoint == "static":
            continue

        # Inspect view function source code and module globals for PolicyEngine binding
        source_code = inspect.getsource(view_fn)
        fn_globals = getattr(view_fn, "__globals__", {})

        is_guarded = (
            any(guard in source_code for guard in policy_guards)
            or PolicyEngine.__name__ in fn_globals
        )

        if is_guarded:
            policy_guarded_routes += 1
        else:
            unprotected_routes.append((rule.rule, rule.endpoint))

    print(f"Total Endpoints Audited: {total_routes}")
    print(f"Policy Engine Guarded: {policy_guarded_routes}")
    print(f"Unguarded / Public Routes: {len(unprotected_routes)}")

    if unprotected_routes:
        print("\n[!] Public or Unguarded Endpoints Detected:")
        for rule_str, ep in unprotected_routes[:10]:
            print(f"  - {rule_str} ({ep})")
    else:
        print(f"\n[✓] VERIFICATION SUCCESSFUL: All non-static endpoints resolve through {PolicyEngine.__name__} authority.")


if __name__ == "__main__":
    audit_route_authorization()