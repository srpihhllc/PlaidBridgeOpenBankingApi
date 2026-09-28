# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_polsia.py

import hashlib
import hmac
import json

import httpx
import pytest
import pytest_asyncio

from app.flask_app import create_app
from app.models.polsia import AdStyle, MetaAdCampaignRequest, RefactorRequest
from app.services.polsia_client import PolsiaClient
from app.services.polsia_engine import (
    PolsiaDevOpsEngine,
    PolsiaGrowthEngine,
    PolsiaNightCycleRunner,
)


@pytest.fixture
def mock_polsia_handler():
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        body = json.loads(request.read().decode("utf-8")) if request.read() else {}

        if path == "/v1/dev/ultra-fix":
            return httpx.Response(
                200,
                json={
                    "task_id": "task_ultrafix_123",
                    "company_id": body.get("company_id"),
                    "status": "completed",
                    "actions_taken": [{"step": "hotfix_applied", "status": "success"}],
                },
            )
        if path == "/v1/growth/meta-ads":
            return httpx.Response(
                200,
                json={
                    "task_id": "task_meta_789",
                    "company_id": body.get("company_id"),
                    "status": "running",
                    "result": {"campaign_id": "meta_camp_999"},
                },
            )
        if path == "/v1/agents/night-task":
            return httpx.Response(
                200,
                json={
                    "task_id": "task_night_001",
                    "company_id": body.get("company_id"),
                    "status": "completed",
                    "result": {"report": "Reconciled Plaid transaction ledger"},
                },
            )
        return httpx.Response(404, json={"error": "Not Found"})

    return handler


@pytest_asyncio.fixture
async def polsia_client(mock_polsia_handler):
    client = PolsiaClient(api_key="test_key", base_url="https://api.polsia.com/v1")
    client.client = httpx.AsyncClient(
        transport=httpx.MockTransport(mock_polsia_handler),
        base_url="https://api.polsia.com/v1",
    )
    yield client
    await client.close()


@pytest.mark.asyncio
async def test_ultra_fix_engine(polsia_client):
    devops = PolsiaDevOpsEngine(polsia_client)
    req = RefactorRequest(
        company_id="comp_plaid_01",
        target_module="app.services.plaid_api",
        instructions="Fix connection timeout",
        enable_ultra_fix=True,
    )
    res = await devops.trigger_refactor_or_ultrafix(req)
    assert res.task_id == "task_ultrafix_123"
    assert res.status == "completed"


@pytest.mark.asyncio
async def test_growth_engine_meta_ads(polsia_client):
    growth = PolsiaGrowthEngine(polsia_client)
    req = MetaAdCampaignRequest(
        company_id="comp_plaid_01",
        campaign_name="Plaid Bridge Launch",
        ad_style=AdStyle.CAROUSEL,
        daily_budget=100.0,
        target_audience={"geos": ["US"]},
    )
    res = await growth.create_meta_ad_campaign(req)
    assert res.task_id == "task_meta_789"
    assert res.result["campaign_id"] == "meta_camp_999"


@pytest.mark.asyncio
async def test_night_cycle_runner(polsia_client):
    night_runner = PolsiaNightCycleRunner(polsia_client)
    res = await night_runner.trigger_night_task(
        company_id="comp_plaid_01", plaid_financial_summary={"balance": 50000.0}
    )
    assert res.task_id == "task_night_001"
    assert res.status == "completed"


def test_webhook_hmac_verification():
    app = create_app()
    app.config["POLSIA_WEBHOOK_SECRET"] = "test_secret_123"

    with app.test_client() as client:
        payload = {"event": "task.completed", "task_id": "task_night_001", "payload": {}}
        raw_bytes = json.dumps(payload).encode("utf-8")

        sig = hmac.new(b"test_secret_123", raw_bytes, hashlib.sha256).hexdigest()

        # Test Valid Signature
        res = client.post(
            "/v1/webhooks/polsia",
            data=raw_bytes,
            content_type="application/json",
            headers={"X-Polsia-Signature": sig},
        )
        assert res.status_code == 200
        assert res.json["task_id"] == "task_night_001"

        # Test Invalid Signature
        bad_res = client.post(
            "/v1/webhooks/polsia",
            data=raw_bytes,
            content_type="application/json",
            headers={"X-Polsia-Signature": "bad_sig"},
        )
        assert bad_res.status_code == 401