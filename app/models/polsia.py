#app/models/polsia.py

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


class CompanyMode(str, Enum):
    CREATE = "create"
    GROW = "grow"


class AdStyle(str, Enum):
    IMAGE = "image"
    CAROUSEL = "carousel"
    VIDEO = "video"


# --- Core Agent Models ---
class PolsiaAgentRequest(BaseModel):
    company_id: str = Field(default="comp_plaidbridge_01", description="Target Company ID")
    agent_id: str = Field(default="finbrain-core-agent", description="Target Polsia Agent ID")
    prompt: str = Field(..., description="Prompt or instructions for the agent")
    context: Dict[str, Any] = Field(default_factory=dict, description="Plaid/Financial context data")
    auto_mode: bool = Field(default=True, description="Enable auto-mode executions")
    budget_limit: Optional[float] = Field(default=None, description="Max spend limit for action")


class PolsiaTaskResponse(BaseModel):
    task_id: str
    company_id: Optional[str] = None
    status: TaskStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    actions_taken: List[Dict[str, Any]] = Field(default_factory=list)


# --- DevOps & Code Models ---
class RefactorRequest(BaseModel):
    company_id: str
    target_module: str
    instructions: str
    enable_ultra_fix: bool = False


class DeployRollbackRequest(BaseModel):
    company_id: str
    target_version_id: str


class SecretManagementRequest(BaseModel):
    company_id: str
    secrets: Dict[str, str]


# --- Growth & Marketing Models ---
class MetaAdCampaignRequest(BaseModel):
    company_id: str
    campaign_name: str
    ad_style: AdStyle
    daily_budget: float
    target_audience: Dict[str, Any]


class TweetRequest(BaseModel):
    company_id: str
    content: str
    auto_tweet_schedule: Optional[str] = None


class NewsletterRequest(BaseModel):
    company_id: str
    subject: str
    body_markdown: str
    recipient_segment: str = "all"


# --- Commerce & Domain Models ---
class DomainConnectRequest(BaseModel):
    company_id: str
    domain_name: str
    buy_new: bool = False


class SubscriptionPlanRequest(BaseModel):
    company_id: str
    plan_name: str
    price_cents: int
    interval: str = "month"