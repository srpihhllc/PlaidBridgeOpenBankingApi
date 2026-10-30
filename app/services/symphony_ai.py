# =============================================================================
# FILE: app/services/symphony_ai.py
# DESCRIPTION: Cockpit-grade Orchestration Cortex (Refactored for google-genai)
# =============================================================================

import json
from datetime import datetime, timezone
from typing import Any

from flask import current_app
from google import genai
from google.genai import types

from app.agents.banking_tools import FINANCIAL_CORTEX_TOOLS
from app.services.bank_simulator import BankSimulator
from app.utils.redis_utils import get_redis_client


SYSTEM_INSTRUCTION = """
You are the master executive brain of a cockpit-grade open-banking orchestration network.
You possess expert-level knowledge of credit architecture, grant procurement, and
regulatory compliance (FCRA, FDCPA).
Your objective: evaluate financial interactions, inspect contracts for predatory
patterns, and enforce state-driven account security protocols.
"""


class SymphonyAI:
    def __init__(self) -> None:
        self.client = genai.Client()
        self.model_id = "gemini-2.0-flash"

        self.simulator = BankSimulator()
        self.redis = get_redis_client()

    def execute_instruction(
        self,
        instruction: str,
        subscriber_id: str | None = None,
    ) -> dict[str, Any]:
        """Route an instruction through Gemini and return the resulting state."""
        current_app.logger.info(
            "⚡ [SYMPHONY_AI] Processing: %s...",
            instruction[:50],
        )

        try:
            config = types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                tools=FINANCIAL_CORTEX_TOOLS,
                temperature=0.1,
            )

            response = self.client.models.generate_content(
                model=self.model_id,
                contents=instruction,
                config=config,
            )

            if response.function_calls:
                function_call = response.function_calls[0]
                tool_name = function_call.name
                tool_args = function_call.args or {}

                current_app.logger.warning(
                    "🚨 [CORTEX_INTENT] Gemini invoked enforcement tool: %s",
                    tool_name,
                )

                effective_subscriber_id = (
                    subscriber_id or tool_args.get("subscriber_id")
                )

                simulator_result = self.simulator.apply(
                    agent_name="Gemini_Cortex",
                    payload={
                        "action": tool_name,
                        "data": tool_args,
                    },
                    subscriber_id=effective_subscriber_id,
                )

                final_result: dict[str, Any] = {
                    "status": "ENFORCEMENT_TRIGGERED",
                    "tool_executed": tool_name,
                    "simulator_state": simulator_result,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                self._log_orchestration_event(
                    effective_subscriber_id,
                    instruction,
                    final_result,
                )
                return final_result

            final_result = {
                "status": "CORTEX_ANALYSIS_COMPLETE",
                "ai_response": response.text,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            self._log_orchestration_event(
                subscriber_id,
                instruction,
                final_result,
            )
            return final_result

        except Exception as exc:
            current_app.logger.error(
                "🚨 [CORTEX_CRITICAL_FAILURE]: %s",
                str(exc),
            )
            return {
                "status": "ERROR",
                "message": str(exc),
            }

    def _log_orchestration_event(
        self,
        subscriber_id: str | None,
        instruction: str,
        result: dict[str, Any],
    ) -> None:
        """Write orchestration telemetry to Redis."""
        if not self.redis:
            return

        trace_key = (
            f"symphony_tracer:{datetime.now(timezone.utc).timestamp()}"
        )
        payload = {
            "subscriber_id": subscriber_id or "ANONYMOUS",
            "instruction": instruction,
            "outcome": result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self.redis.setex(
            trace_key,
            86400 * 30,
            json.dumps(payload),
        )