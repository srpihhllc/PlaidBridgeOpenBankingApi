# app/services/polsia_client.py

import asyncio
import logging
import os
from typing import Any, Optional, cast

import httpx

from app.models.polsia import PolsiaAgentRequest, PolsiaTaskResponse, TaskStatus

logger = logging.getLogger(__name__)


class PolsiaClient:
    """Async client wrapper for the Polsia Agent API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 45.0,
    ) -> None:
        resolved_api_key = api_key or os.getenv("POLSIA_API_KEY", "")

        configured_base_url = (
            base_url
            if base_url is not None
            else os.getenv("POLSIA_BASE_URL")
        )
        resolved_base_url = (
            configured_base_url or "https://api.polsia.com/v1"
        )
        self.base_url = resolved_base_url.rstrip("/")

        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {resolved_api_key}",
                "Content-Type": "application/json",
                "User-Agent": "PlaidBridgeOpenBankingApi-FinBrain/2.0",
            },
            timeout=timeout,
        )

    async def __aenter__(self) -> "PolsiaClient":
        return self

    async def __aexit__(
        self,
        exc_type: Any,
        exc: Any,
        traceback: Any,
    ) -> None:
        await self.close()

    def _url(self, endpoint: str) -> str:
        """Build a URL whether or not the endpoint starts with a slash."""
        return f"{self.base_url}/{endpoint.lstrip('/')}"

    @staticmethod
    def _json_object(response: httpx.Response) -> dict[str, Any]:
        """Decode a response and require its JSON value to be an object."""
        data: Any = response.json()
        if not isinstance(data, dict):
            raise ValueError("Polsia API response must be a JSON object.")
        return cast(dict[str, Any], data)

    async def post_request(
        self,
        endpoint: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            response = await self.client.post(
                self._url(endpoint),
                json=payload,
            )
            response.raise_for_status()
            return self._json_object(response)
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Polsia POST %s failed with status %s",
                endpoint,
                exc.response.status_code,
            )
            raise RuntimeError(
                f"Polsia request failed with HTTP {exc.response.status_code}."
            ) from exc
        except httpx.RequestError as exc:
            logger.error("Polsia POST %s request failed: %s", endpoint, exc)
            raise RuntimeError(
                f"Polsia request to {endpoint} failed."
            ) from exc

    async def get_request(self, endpoint: str) -> dict[str, Any]:
        try:
            response = await self.client.get(self._url(endpoint))
            response.raise_for_status()
            return self._json_object(response)
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Polsia GET %s failed with status %s",
                endpoint,
                exc.response.status_code,
            )
            raise RuntimeError(
                f"Polsia request failed with HTTP {exc.response.status_code}."
            ) from exc
        except httpx.RequestError as exc:
            logger.error("Polsia GET %s request failed: %s", endpoint, exc)
            raise RuntimeError(
                f"Polsia request to {endpoint} failed."
            ) from exc

    async def execute_agent_task(
        self,
        request: PolsiaAgentRequest,
    ) -> PolsiaTaskResponse:
        """Submit an agent task to Polsia."""
        data = await self.post_request(
            "/agents/execute",
            request.model_dump(exclude_none=True),
        )
        return PolsiaTaskResponse(**data)

    async def get_task_status(self, task_id: str) -> PolsiaTaskResponse:
        """Fetch the status of a task by ID."""
        data = await self.get_request(f"/tasks/{task_id}")
        return PolsiaTaskResponse(**data)

    async def wait_for_completion(
        self,
        task_id: str,
        poll_interval: float = 2.0,
        max_retries: int = 30,
    ) -> PolsiaTaskResponse:
        """Poll until the task completes, fails, or reaches the retry limit."""
        if poll_interval < 0:
            raise ValueError("poll_interval must be non-negative")
        if max_retries < 1:
            raise ValueError("max_retries must be at least 1")

        for attempt in range(max_retries):
            task = await self.get_task_status(task_id)
            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                return task

            if attempt < max_retries - 1:
                await asyncio.sleep(poll_interval)

        raise TimeoutError(
            f"Task {task_id} did not finish after {max_retries} checks."
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self.client.aclose()