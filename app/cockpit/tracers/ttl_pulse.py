# =============================================================================
# FILE: app/cockpit/tracers/ttl_pulse.py
# DESCRIPTION: Emits TTL-backed Redis pulses for cockpit PDF export telemetry.
# =============================================================================

from datetime import datetime

from app.telemetry.ttl_emit import ttl_emit
from app.utils.redis_utils import get_redis_client  # ✅ import the function, not a global


def log_pdf_export_pulse(filename, operator="system", ttl_seconds=300):
    """
    Logs a TTL pulse for a PDF export event.
    Stores status in Redis for cockpit visibility.

    Args:
        filename (str): Name of the exported PDF file.
        operator (str): Who triggered the export (default: 'system').
        ttl_seconds (int): How long the pulse should live in Redis.
    """
    job_id = f"ttl:pdf:{filename}"
    status = f"exported by {operator} @ {datetime.utcnow().isoformat()}"
    try:
        ttl_emit(key=job_id, status=status, client=get_redis_client(), ttl=ttl_seconds)
    except Exception:
        # If Redis is down or unreachable, skip without crashing
        ttl_emit(key=job_id, status=status, client=None, ttl=ttl_seconds)
