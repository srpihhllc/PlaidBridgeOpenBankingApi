#PlaidBridgeOpenBankingApi/PlaidBridgeOpenBankingApi/app/tools/run_all_audits_oneoff.py

#!/usr/bin/env python3
"""
One-off audit runner: calls nav_audit.audit_templates(app) (nav_audit has no run())
and then invokes other audit.run() functions the same way app/scripts/audit.py intended.
Run from repo root with PYTHONPATH pointing at PlaidBridgeOpenBankingApi (see instructions).
"""
import json
from app import create_app
from app.utils import nav_audit, route_audit, template_audit, relationship_audit
from app.cli_commands import cli_audit, ttl_audit
from app.scripts.audit import run_blueprint_template_audit
from app.utils.redis_utils import get_redis_client

def safe_run(mod, name):
    if hasattr(mod, "run"):
        print(f"\n▶ Running {name}.run() ...")
        try:
            mod.run()
        except Exception as e:
            print(f"[ERROR] {name}.run() raised: {e}")
    else:
        print(f"[SKIP] {name} has no run() — skipping.")

def main():
    app = create_app()
    with app.app_context():
        print("🔍 Running cockpit audits (one-off)\n")

        # nav_audit has no run(), call its audit function directly
        print("=== NAV TEMPLATE AUDIT ===")
        try:
            nav_report = nav_audit.audit_templates(app)
            print(json.dumps(nav_report, indent=2))
        except Exception as e:
            print(f"[ERROR] nav_audit.audit_templates raised: {e}")

        # run other audits (they should expose run())
        safe_run(route_audit, "route_audit")
        safe_run(template_audit, "template_audit")
        safe_run(relationship_audit, "relationship_audit")
        safe_run(ttl_audit, "ttl_audit")
        safe_run(cli_audit, "cli_audit")

        # integrated blueprint/template manifest audit (uses get_redis_client)
        redis_client = get_redis_client()
        run_blueprint_template_audit(redis_client)

        print("\n✅ One-off audits complete")

if __name__ == "__main__":
    main()
