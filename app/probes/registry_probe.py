# /app/probes/registry_probe.py
from app.models.registry import Registry


def emit_registry_traces():
    registries = Registry.query.all()
    for reg in registries:
        print("🧭 Registry Trace —", reg.name)
        print("📡 Ping:", reg.ping())
        print("📊 Trace Status:", reg.trace_status())
