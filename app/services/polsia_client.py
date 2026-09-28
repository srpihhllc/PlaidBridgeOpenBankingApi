#app/services/polsia_client.py

from typing import Any, Dict, Optional
import asyncio
import logging
import os
import httpx

from app.models.polsia import PolsiaAgentRequest, PolsiaTaskResponse, TaskStatus

logger = logging.getLogger(__name__)


class PolsiaClient:
    """Async client wrapper for Polsia Agent API integrated into PlaidBridge."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 45.0,
    ):
        self.api_key = api_key or os.getenv("POLSIA_API_KEY", "")
        self.base_url = (base_url or os.getenv("POLSIA_BASE_URL", "https://api.polsia.com/v1")).rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "PlaidBridgeOpenBankingApi-FinBrain/2.0",
        }
        self.client = httpx.AsyncClient(headers=self.headers, timeout=timeout)

    async def post_request(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        try:
            res = await self.client.post(url, json=payload)
            res.raise_for_status()
            return res.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP Error on Polsia POST {endpoint}: {e.response.status_code} - {e.response.text}")
            raise RuntimeError(f"Polsia Request Failed: {e.response.text}") from e

    async def get_request(self, endpoint: str) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        try:
            res = await self.client.get(url)
            res.raise_for_status()
            return res.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP Error on Polsia GET {endpoint}: {e.response.status_code} - {e.response.text}")
            raise RuntimeError(f"Polsia Request Failed: {e.response.text}") from e

    async def execute_agent_task(self, request: PolsiaAgentRequest) -> PolsiaTaskResponse:
        """Submit an agent task to Polsia."""
        data = await self.post_request("/agents/execute", request.model_dump(exclude_none=True))
        return PolsiaTaskResponse(**data)

    async def get_task_status(self, task_id: str) -> PolsiaTaskResponse:
        """Poll task status by ID."""
        data = await self.get_request(f"/tasks/{task_id}")
        return PolsiaTaskResponse(**data)

    async def wait_for_completion(
        self, task_id: str, poll_interval: float = 2.0, max_retries: int = 30
    ) -> PolsiaTaskResponse:
        """Poll task until completion or timeout."""
        for _ in range(max_retries):
            task = await self.get_task_status(task_id)
            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                return task
            await asyncio.sleep(poll_interval)
        raise TimeoutError(f"Task {task_id} timed out before completion.")

    async def close(self):
        """Close HTTP client session."""
        await self.client.aclose()