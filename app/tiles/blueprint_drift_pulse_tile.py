from app.cli_commands import blueprint_drift_tracer
from app.cockpit.telemetry.emitters import ttl

TILE_KEY = "boot:blueprint_drift"
TTL_SECONDS = 300


def emit():
    failures = blueprint_drift_tracer.audit_blueprint_attributes()
    status = "fail" if failures else "ok"

    # Register TTL freshness
    ttl.emit_ttl_pulse(TILE_KEY, TTL_SECONDS)

    # Optionally: store payload in a cockpit data channel if you have one
    # so UI can render failure count/details
    return {"status": status, "count": len(failures), "failures": failures}


if __name__ == "__main__":
    # Allow manual run to behave like CLI
    result = emit()
    if result["status"] == "fail":
        print(f"❌ {result['count']} blueprint drift issues detected")
        for f in result["failures"]:
            print(f"   - {f}")
    else:
        print("✅ No blueprint drift detected")
