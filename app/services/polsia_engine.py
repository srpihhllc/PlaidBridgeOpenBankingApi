# app/services/polsia_engine.py

from typing import Any, Dict
import logging

from app.models.polsia import (
    DomainConnectRequest,
    DeployRollbackRequest,
    MetaAdCampaignRequest,
    NewsletterRequest,
    PolsiaAgentRequest,
    PolsiaTaskResponse,
    RefactorRequest,
    SecretManagementRequest,
    SubscriptionPlanRequest,
    TaskStatus,
    TweetRequest,
)
from app.services.polsia_client import PolsiaClient

logger = logging.getLogger(__name__)


class PolsiaDevOpsEngine:
    def __init__(self, client: PolsiaClient):
        self.client = client

    async def trigger_refactor_or_ultrafix(self, req: RefactorRequest) -> PolsiaTaskResponse:
        endpoint = "/dev/ultra-fix" if req.enable_ultra_fix else "/dev/refactor"
        res = await self.client.post_request(endpoint, req.model_dump())
        return PolsiaTaskResponse(**res)

    async def add_secrets(self, req: SecretManagementRequest) -> Dict[str, Any]:
        return await self.client.post_request("/dev/secrets", req.model_dump())

    async def rollback_deployment(self, req: DeployRollbackRequest) -> Dict[str, Any]:
        return await self.client.post_request("/dev/rollback", req.model_dump())

    async def export_database_snapshot(self, company_id: str) -> Dict[str, Any]:
        return await self.client.get_request(f"/dev/database/export?company_id={company_id}")


class PolsiaGrowthEngine:
    def __init__(self, client: PolsiaClient):
        self.client = client

    async def create_meta_ad_campaign(self, req: MetaAdCampaignRequest) -> PolsiaTaskResponse:
        res = await self.client.post_request("/growth/meta-ads", req.model_dump())
        return PolsiaTaskResponse(**res)

    async def publish_or_schedule_tweet(self, req: TweetRequest) -> Dict[str, Any]:
        return await self.client.post_request("/growth/x-twitter", req.model_dump())

    async def dispatch_weekly_newsletter(self, req: NewsletterRequest) -> PolsiaTaskResponse:
        res = await self.client.post_request("/growth/newsletter", req.model_dump())
        return PolsiaTaskResponse(**res)


class PolsiaCommerceEngine:
    def __init__(self, client: PolsiaClient):
        self.client = client

    async def configure_custom_domain(self, req: DomainConnectRequest) -> Dict[str, Any]:
        return await self.client.post_request("/commerce/domains", req.model_dump())

    async def create_membership_plan(self, req: SubscriptionPlanRequest) -> Dict[str, Any]:
        return await self.client.post_request("/commerce/subscriptions", req.model_dump())


class PolsiaNightCycleRunner:
    def __init__(self, client: PolsiaClient):
        self.client = client

    async def trigger_night_task(self, company_id: str, plaid_financial_summary: Dict[str, Any]) -> PolsiaTaskResponse:
        payload = PolsiaAgentRequest(
            company_id=company_id,
            agent_id="finbrain-night-executive",
            prompt="Run autonomous night task: Reconcile subscriptions, optimize growth budgets, output morning report.",
            context=plaid_financial_summary,
            auto_mode=True,
        )
        logger.info(f"Triggering Polsia Night Task for company {company_id}")
        res = await self.client.post_request("/agents/night-task", payload.model_dump())
        return PolsiaTaskResponse(**res)


class PolsiaPlaidBridge:
    """Connects Plaid Open Banking triggers with Polsia Agent workflows."""

    def __init__(self, polsia_client: PolsiaClient):
        self.polsia = polsia_client

    async def analyze_plaid_cashflow(self, account_id: str, plaid_transactions: Dict[str, Any]) -> PolsiaTaskResponse:
        prompt = (
            f"Analyze Plaid banking transaction history for account {account_id}. "
            "Identify recurring subscriptions, spending anomalies, and generate risk profile."
        )
        request = PolsiaAgentRequest(
            agent_id="finbrain-risk-analyzer",
            prompt=prompt,
            context={"account_id": account_id, "plaid_data": plaid_transactions},
        )
        logger.info(f"Dispatching Plaid transaction context to Polsia for account {account_id}")
        initial_res = await self.polsia.execute_agent_task(request)
        if initial_res.status not in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
            return await self.polsia.wait_for_completion(initial_res.task_id)
        return initial_res