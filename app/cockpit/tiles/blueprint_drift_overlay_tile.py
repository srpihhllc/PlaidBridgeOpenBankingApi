# app/cockpit/tiles/blueprint_drift_overlay_tile.py

"""
Cockpit overlay tile: Live Blueprint Drift Details + Drilldown
Consumes TTL pulse from tiles/blueprint_drift_pulse_tile.py
and renders a clickable list of failing blueprints in the cockpit UI.
Now includes exact line numbers for Blueprint definitions (or defaults to 1 if missing).
"""

import os
import re

from app.cli_commands import blueprint_drift_tracer
from app.cockpit.telemetry.emitters import ttl

TILE_ID = "blueprint_drift_overlay"
REPO_BASE_PATH = "/home/srpihhllc/PlaidBridgeOpenBankingApi"
BLUEPRINT_DEF_RE = re.compile(r"\b\w+\s*=\s*Blueprint\b")


def render():
    ttl_status = ttl.ttl_summary().get("boot:blueprint_drift", {})
    failures = blueprint_drift_tracer.audit_blueprint_attributes()

    drilldown = []
    for f in failures:
        abs_path = os.path.join(REPO_BASE_PATH, f.replace(".", "/") + ".py")
        line_num = 1  # default if not found

        try:
            with open(abs_path, encoding="utf-8") as fh:
                for idx, line in enumerate(fh, start=1):
                    if BLUEPRINT_DEF_RE.search(line):
                        line_num = idx
                        break
        except FileNotFoundError:
            # Keep default line_num = 1 if file missing
            pass

        drilldown.append(
            {
                "name": f,
                "path": abs_path,
                "line": line_num,
                "link": f"/cockpit/drilldown?file={f.replace('.', '/')}.py&line={line_num}",
            }
        )

    return {
        "title": "Blueprint Drift Details",
        "status": "fail" if failures else "ok",
        "ttl_remaining": ttl_status.get("remaining_seconds"),
        "failures": drilldown,
        "count": len(failures),
    }


if __name__ == "__main__":
    data = render()
    print(f"Status: {data['status']}")
    print(f"TTL Remaining: {data['ttl_remaining']}")
    if data["failures"]:
        print("❌ Drift detected in:")
        for f in data["failures"]:
            print(f"   - {f['name']} ({f['path']}:{f['line']})")
    else:
        print("✅ No blueprint drift detected")
