# =============================================================================
# FILE: app/services/symphony_ai.py
# DESCRIPTION: Orchestration brain for grant workflows with Redis-backed telemetry.
# =============================================================================

import json
import queue
import re
import threading
from datetime import datetime
from pathlib import Path

from flask import current_app

from app.models import User
from app.utils.redis_utils import get_redis_client

ROLE_WEIGHTS = {
    "grant_manager": 0.9,
    "compliance_officer": 0.75,
    "gov_liaison": 0.85,
    "admin": 1.0,
}

# Initialize global Redis client
redis_client = get_redis_client()

# 🧠 Grant Decision Subroutines


def extract_org_id(instruction):
    match = re.search(r"OrgID[:\s]*([A-Za-z0-9_-]+)", instruction)
    return match.group(1) if match else "unknown_org"


def simulate_grant_approval_risk(redis_keys):
    score = 100
    for key in redis_keys:
        value = redis_client.get(key)
        if value:
            decoded = value.decode("utf-8")
            if "fraud" in key and "flag" in decoded:
                score -= 40
            elif "velocity" in key:
                try:
                    velocity = float(decoded)
                    if velocity < 1000.0:
                        score -= 30
                except ValueError:
                    score -= 10
    return max(score, 0)


def save_to_dashboard(org_id, score):
    log = {"org_id": org_id, "score": score, "timestamp": datetime.utcnow().isoformat()}
    client = getattr(current_app, "redis_client", None) or get_redis_client()
    if client:
        client.set(f"org_scores:{org_id}", json.dumps(log))
    else:
        current_app.logger.error(
            "[symphony_ai.save_to_dashboard] Redis unavailable — skipping set for " "org_scores:%s",
            org_id,
        )


# 🧠 SymphonyAI Brain Class


class SymphonyAI:
    def __init__(self, memory_limit=100, max_threads=5):
        self.memory = []
        self.memory_limit = memory_limit
        self.max_threads = max_threads
        self.task_queue = queue.Queue()
        self.results = {}
        self.agent_registry = self.load_registry()

    def load_registry(self):
        path = Path("app/agents/agent_registry.json")
        return json.loads(path.read_text()) if path.exists() else {}

    def dispatch_to_agent(self, task):
        for agent, meta in self.agent_registry.items():
            if task in meta.get("tasks", []):
                return f"✅ Task '{task}' routed to {agent}: {meta.get('description')}"
        return f"⚠️ No matching agent found for '{task}'"

    def run(self, instruction, user_id=None):
        """
        Executes a series of tasks based on a given instruction,
        prioritizing them based on the user's role.
        """
        tasks = self.process_instruction(instruction)
        self.results = {}

        # Role-weighted orchestration priority
        role = None
        if user_id:
            user = User.query.get(user_id)
            role = user.role if user else None

        for task in tasks:
            if role:
                weight = ROLE_WEIGHTS.get(role, 0.5)
                if weight >= 0.85:
                    task = f"[PRIORITY] {task}"
            self.task_queue.put(task)

        threads = [
            threading.Thread(target=self.worker) for _ in range(min(self.max_threads, len(tasks)))
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 🧾 Log orchestration to Redis
        log_key = f"grants_composed:{datetime.utcnow().timestamp()}"
        client = getattr(current_app, "redis_client", None) or get_redis_client()

        if client:
            try:
                client.setex(
                    log_key,
                    86400 * 30,
                    json.dumps(
                        {
                            "instruction": instruction,
                            "results": self.results,
                            "timestamp": datetime.utcnow().isoformat(),
                            "user_role": role or "anonymous",
                        }
                    ),
                )
            except Exception as log_error:
                current_app.logger.error(
                    f"[symphony_ai.run] Redis setex failed for {log_key} — {log_error}"
                )
        else:
            current_app.logger.error(
                f"[symphony_ai.run] Redis unavailable — skipping setex for {log_key}"
            )

        return self.results
