
# =============================================================================

# FILE: app/services/polsia_memory.py

# DESCRIPTION: Closed-loop learning memory connecting Polsia webhook outcomes

#              with FinBrain / SymphonyAI context and nightly telemetry.

# =============================================================================



from __future__ import annotations



from datetime import datetime, timezone

import json

import logging

from typing import Any



from app.utils.redis_utils import get_redis_client



logger = logging.getLogger(__name__)



INSIGHT_KEY_PREFIX = "finbrain:polsia:insights"

INSIGHT_TTL_SECONDS = 86400 * 90

MAX_INSIGHTS_PER_COMPANY = 50





class PolsiaMemoryStore:

    """Persists Polsia agent outcomes in Redis + DB and retrieves learned rules."""



    def __init__(self) -> None:

        self.redis = get_redis_client()



    def _key(self, company_id: str) -> str:

        return f"{INSIGHT_KEY_PREFIX}:{company_id or 'comp_plaidbridge_01'}"



    def record_outcome(self, event_data: dict[str, Any]) -> dict[str, Any]:

        """Persist a completed/failed Polsia task result into FinBrain memory."""

        company_id = str(event_data.get("company_id") or "comp_plaidbridge_01")

        task_id = str(event_data.get("task_id") or "unknown")

        event_type = str(event_data.get("event") or "unknown")

        result = event_data.get("result") or {}

        actions_taken = event_data.get("actions_taken") or []



        record = {

            "task_id": task_id,

            "company_id": company_id,

            "event": event_type,

            "agent_id": event_data.get("agent_id", "polsia-agent"),

            "summary": result.get("summary") or result.get("insights") or result,

            "anomalies": result.get("anomalies", []),

            "risk_adjustments": result.get("risk_adjustments", {}),

            "actions_taken": actions_taken,

            "recorded_at": datetime.now(timezone.utc).isoformat(),

        }



        if self.redis:

            try:

                redis_key = self._key(company_id)

                self.redis.lpush(redis_key, json.dumps(record, default=str))

                self.redis.ltrim(redis_key, 0, MAX_INSIGHTS_PER_COMPANY - 1)

                self.redis.expire(redis_key, INSIGHT_TTL_SECONDS)

            except Exception as exc:

                logger.warning("Failed to persist Polsia memory to Redis: %s", exc)



        self._persist_audit_log(record)

        return record



    def _persist_audit_log(self, record: dict[str, Any]) -> None:

        """Best-effort write to MySQL AuditLog when running inside a Flask app context."""

        try:

            from flask import has_app_context

            if not has_app_context():

                return

            from app.extensions import db

            from app.models.audit_log import AuditLog



            entry = AuditLog(

                action=f"POLSIA_LEARNING:{record['event']}",

                details=json.dumps(record, default=str)[:2000],

            )

            db.session.add(entry)

            db.session.commit()

        except Exception as exc:

            logger.debug("Skipped DB AuditLog write for Polsia memory: %s", exc)



    def get_recent_insights(

        self,

        company_id: str = "comp_plaidbridge_01",

        limit: int = 10,

    ) -> list[dict[str, Any]]:

        """Retrieve recent Polsia insights for prompt conditioning or night cycles."""

        if not self.redis:

            return []

        try:

            raw_items = self.redis.lrange(self._key(company_id), 0, max(limit - 1, 0))

            insights: list[dict[str, Any]] = []

            for raw in raw_items or []:

                text = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)

                insights.append(json.loads(text))

            return insights

        except Exception as exc:

            logger.warning("Failed to read Polsia memory from Redis: %s", exc)

            return []



    def format_prompt_context(

        self,

        company_id: str = "comp_plaidbridge_01",

        limit: int = 5,

    ) -> str:

        """Format learned Polsia insights for injection into SymphonyAI / Gemini."""

        insights = self.get_recent_insights(company_id=company_id, limit=limit)

        if not insights:

            return ""

        lines = ["\n\nLEARNED_CORTEX_MEMORY (Recent Polsia Autonomous Findings):"]

        for item in insights:

            lines.append(

                f"- [{item.get('recorded_at', 'recent')}] "

                f"({item.get('agent_id')} / {item.get('event')}): "

                f"{json.dumps(item.get('summary'), default=str)[:400]}"

            )

        return "\n".join(lines)

