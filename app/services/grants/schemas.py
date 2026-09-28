"""Schemas for FinBrain Grant Intelligence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


Severity = Literal["low", "medium", "high", "critical"]


@dataclass
class EvidenceItem:
    claim: str
    source: str | None = None
    citation: str | None = None
    evidence_type: Literal[
        "verified_fact",
        "applicant_claim",
        "assumption",
        "missing_information",
    ] = "verified_fact"
    confidence: float | None = None
    notes: str | None = None


@dataclass
class ReviewerReport:
    reviewer: str
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    severity: Severity = "low"
    evidence_needed: list[str] = field(default_factory=list)
    required_revision: str = ""


@dataclass
class Risk:
    title: str
    description: str
    severity: Severity
    mitigation: str = ""
    owner: str | None = None


@dataclass
class ReadinessDimensions:
    eligibility_readiness: float = 0.0
    funder_alignment: float = 0.0
    evidence_strength: float = 0.0
    program_feasibility: float = 0.0
    organizational_capacity: float = 0.0
    budget_defensibility: float = 0.0
    evaluation_quality: float = 0.0
    sustainability_strength: float = 0.0
    submission_completeness: float = 0.0


@dataclass
class ReadinessReport:
    readiness_score: float
    classification: str
    dimensions: ReadinessDimensions
    risks: list[Risk] = field(default_factory=list)
    required_revisions: list[str] = field(default_factory=list)
    human_approval_required: bool = True


@dataclass
class GrantProject:
    project_name: str
    organization_name: str
    applicant_data: dict[str, Any] = field(default_factory=dict)
    funding_opportunity: dict[str, Any] = field(default_factory=dict)
    evidence: list[EvidenceItem] = field(default_factory=list)
    proposal_sections: dict[str, Any] = field(default_factory=dict)
    budget: list[dict[str, Any]] = field(default_factory=list)
    risks: list[Risk] = field(default_factory=list)
    reviewer_reports: list[ReviewerReport] = field(default_factory=list)