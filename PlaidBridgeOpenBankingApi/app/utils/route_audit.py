# FILE: /home/srpihhllc/PlaidBridgeOpenBankingApi/app/utils/route_audit.py
# DESCRIPTION: Utility to print all registered Flask routes for debugging.

from flask import current_app


def dump_routes():
    """Print all registered routes and their endpoints."""
    output = []
    for rule in current_app.url_map.iter_rules():
        methods = ",".join(sorted(m for m in rule.methods if m not in ("HEAD", "OPTIONS")))
        line = f"{rule.endpoint:30s} | {rule.rule:40s} | methods: {methods}"
        output.append(line)
    print("\n=== Registered Flask Routes ===")
    for line in sorted(output):
        print(line)
    print("=== End of Route Dump ===\n")

def run():
    """
    Compatibility wrapper so scripts/audit.py can call route_audit.run().
    Runs dump_routes() inside the current_app context (script orchestrator
    already creates an app or uses create_app where required).
    """
    try:
        dump_routes()
    except RuntimeError:
        # If called outside an app context, create a real app and run inside it
        from app import create_app

        app = create_app()
        with app.app_context():
            dump_routes()
