# =============================================================================
# FILE: app/services/symphony_ai.py
# DESCRIPTION: Cockpit-grade Orchestration Cortex (Refactored for google-genai)
# =============================================================================

import json
from datetime import datetime
from flask import current_app

# Modern Gemini SDK
from google import genai
from google.genai import types

from app.services.bank_simulator import BankSimulator
from app.agents.banking_tools import FINANCIAL_CORTEX_TOOLS
from app.utils.redis_utils import get_redis_client

SYSTEM_INSTRUCTION = """
You are the master executive brain of a cockpit-grade open-banking orchestration network.
You possess expert-level knowledge of credit architecture, grant procurement, and 
regulatory compliance (FCRA, FDCPA, CFPB).
Your objective: evaluate financial interactions, inspect contracts for predatory 
patterns, and enforce state-driven account security protocols.
"""

class SymphonyAI:
    def __init__(self):
        # Initialize modern Gemini client
        self.client = genai.Client()
        self.model_id = "gemini-2.0-flash"

        # Enforcement engine
        self.simulator = BankSimulator()

        # Telemetry engine
        self.redis = get_redis_client()

    def execute_instruction(self, instruction: str, subscriber_id: str = None) -> dict:
        """
        Routes instructions through the Gemini Cortex using the modern SDK.
        Captures function calls, executes them via BankSimulator, and returns the state.
        """
        current_app.logger.info(f"⚡ [SYMPHONY_AI] Processing: {instruction[:50]}...")

        try:
            # Configure system instruction + tools
            config = types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                tools=FINANCIAL_CORTEX_TOOLS,
                temperature=0.1  # deterministic enforcement
            )

            # AI reasoning
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=instruction,
                config=config
            )

            # --- FUNCTION CALL DETECTED ---
            if response.function_calls:
                fc = response.function_calls[0]
                tool_name = fc.name
                tool_args = fc.args

                current_app.logger.warning(
                    f"🚨 [CORTEX_INTENT] Gemini invoked enforcement tool: {tool_name}"
                )

                # Route into BankSimulator
                simulator_result = self.simulator.apply(
                    agent_name="Gemini_Cortex",
                    payload={"action": tool_name, "data": tool_args},
                    subscriber_id=subscriber_id or tool_args.get("subscriber_id")
                )

                final_result = {
                    "status": "ENFORCEMENT_TRIGGERED",
                    "tool_executed": tool_name,
                    "simulator_state": simulator_result,
                    "timestamp": datetime.utcnow().isoformat()
                }

                self._log_orchestration_event(subscriber_id, instruction, final_result)
                return final_result

            # --- NO TOOL CALL: ANALYSIS ONLY ---
            final_result = {
                "status": "CORTEX_ANALYSIS_COMPLETE",
                "ai_response": response.text,
                "timestamp": datetime.utcnow().isoformat()
            }

            self._log_orchestration_event(subscriber_id, instruction, final_result)
            return final_result

        except Exception as e:
            current_app.logger.error(f"🚨 [CORTEX_CRITICAL_FAILURE]: {str(e)}")
            return {"status": "ERROR", "message": str(e)}

    def _log_orchestration_event(self, subscriber_id: str, instruction: str, result: dict):
        """Writes cockpit-grade telemetry into Redis."""
        if not self.redis:
            return

        trace_key = f"symphony_tracer:{datetime.utcnow().timestamp()}"
        payload = {
            "subscriber_id": subscriber_id or "ANONYMOUS",
            "instruction": instruction,
            "outcome": result,
            "timestamp": datetime.utcnow().isoformat()
        }

        self.redis.setex(trace_key, 86400 * 30, json.dumps(payload))
