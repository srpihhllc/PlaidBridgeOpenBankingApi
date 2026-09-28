# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/services/grant_writer.py

"""
grant_writer.py — Grant-readiness orchestration service.

This module preserves the existing compose_grant() API while adding
evidence-based grant analysis, compliance review, budget defensibility,
evaluation review, red-team critique, and human-approval controls.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from .grants.grant_intelligence import GrantIntelligence
from .grants.schemas import (
    EvidenceItem,
    GrantProject,
    Risk,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Legacy-compatible narrative composers
# =============================================================================


def _compose_sbir(payload: dict[str, Any]) -> str:
    """Compose a factual SBIR narrative from supplied applicant data."""
    org = payload.get("org_profile") or {}
    project = payload.get("project") or {}

    return "\n".join(
        [
            "[GRANT TYPE]: SBIR PROPOSAL NARRATIVE",
            "",
            f"Organization: {org.get('name', 'Not provided')}",
            f"Location: {org.get('location', 'Not provided')}",
            f"Project: {project.get('title', 'Not provided')}",
            f"Mission Alignment: {org.get('mission', 'Not provided')}",
            f"Funding Request: {project.get('budget', 'Not provided')}",
            f"Project Timeline: {project.get('timeline', 'Not provided')}",
            "",
            "Project Summary:",
            str(project.get("summary", "Not provided")),
            "",
            "Goals:",
            str(project.get("goals", "Not provided")),
            "",
            "Evidence and assumptions must be documented before submission.",
        ]
    )


def _compose_cdbg(payload: dict[str, Any]) -> str:
    return _compose_generic_type("CDBG", payload)


def _compose_rbdg(payload: dict[str, Any]) -> str:
    return _compose_generic_type("RBDG", payload)


def _compose_eda(payload: dict[str, Any]) -> str:
    return _compose_generic_type("EDA", payload)


def _compose_generic_type(
    grant_type: str,
    payload: dict[str, Any],
) -> str:
    org = payload.get("org_profile") or {}
    project = payload.get("project") or {}

    return "\n".join(
        [
            f"[GRANT TYPE]: {grant_type} PROPOSAL NARRATIVE",
            "",
            f"Organization: {org.get('name', 'Not provided')}",
            f"Project: {project.get('title', 'Not provided')}",
            f"Location: {org.get('location', 'Not provided')}",
            "",
            "Project Summary:",
            str(project.get("summary", "Not provided")),
            "",
            "Statement of Need:",
            str(project.get("need", "Not provided")),
            "",
            "Proposed Activities:",
            str(project.get("activities", "Not provided")),
            "",
            "Expected Outcomes:",
            str(project.get("outcomes", "Not provided")),
            "",
            "All claims, measurements, partnerships, and outcomes require "
            "supporting documentation or explicit classification as assumptions.",
        ]
    )


def _compose_general_nofo(payload: dict[str, Any]) -> str:
    grant_type = str(payload.get("grant_type", "general")).upper()
    nofo = payload.get("nofo", "No funding-opportunity guidance provided.")
    project = payload.get("project") or {}

    return "\n".join(
        [
            f"[GRANT TYPE]: {grant_type}",
            "",
            "[FUNDING OPPORTUNITY GUIDANCE]",
            str(nofo),
            "",
            "[PROJECT SUMMARY]",
            str(project.get("summary", "Not provided")),
            "",
            "[NEED]",
            str(project.get("need", "Not provided")),
            "",
            "[ACTIVITIES]",
            str(project.get("activities", "Not provided")),
            "",
            "[OUTPUTS AND OUTCOMES]",
            str(project.get("outcomes", "Not provided")),
            "",
            "[COMPLIANCE NOTICE]",
            "Eligibility, requirements, evidence, budget relationships, "
            "evaluation measures, and unresolved risks require review before "
            "submission.",
        ]
    )


_GRANT_DISPATCHER: dict[str, Callable[[dict[str, Any]], str]] = {
    "sbir": _compose_sbir,
    "cdbg": _compose_cdbg,
    "rbdg": _compose_rbdg,
    "eda": _compose_eda,
}


def compose_grant(payload: dict[str, Any]) -> str:
    """
    Compose a grant narrative using the existing public API.

    The function does not predict funding outcomes, invent evidence, or
    represent a draft as approved for submission.
    """
    grant_type = str(payload.get("grant_type") or "general").strip().lower()
    composer = _GRANT_DISPATCHER.get(grant_type, _compose_general_nofo)

    if composer is _compose_general_nofo and grant_type != "general":
        logger.info(
            "Using general NOFO composer for unsupported grant type: %s",
            grant_type,
        )

    return composer(payload)


# =============================================================================
# Grant-readiness orchestration
# =============================================================================


class GrantWriter:
    """
    Orchestrates grant-readiness analysis.

    Human approval is always required before final submission.
    """

    def __init__(
        self,
        intelligence: GrantIntelligence | None = None,
    ) -> None:
        self.intelligence = intelligence or GrantIntelligence()

    def analyze(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Analyze a project for eligibility, alignment, evidence quality,
        program feasibility, budget defensibility, evaluation quality,
        compliance, and submission readiness.
        """
        project = self._build_project(payload)
        return self.intelligence.analyze(project)

    def prepare(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Return a composed narrative together with its readiness analysis.
        """
        return {
            "narrative": compose_grant(payload),
            "readiness_analysis": self.analyze(payload),
            "human_approval_required": True,
        }

    def approve_for_submission(self, human_approved: bool) -> bool:
        """
        Return True only when an authorized human explicitly approves.
        """
        return self.intelligence.can_submit(human_approved)

    @staticmethod
    def _build_project(payload: dict[str, Any]) -> GrantProject:
        org_profile = payload.get("org_profile") or {}
        project_data = payload.get("project") or {}

        evidence = [
            item
            if isinstance(item, EvidenceItem)
            else EvidenceItem(
                claim=str(item.get("claim", "")),
                source=item.get("source"),
                citation=item.get("citation"),
                evidence_type=item.get(
                    "evidence_type",
                    "applicant_claim",
                ),
                confidence=item.get("confidence"),
                notes=item.get("notes"),
            )
            for item in payload.get("evidence", [])
        ]

        risks = [
            item
            if isinstance(item, Risk)
            else Risk(
                title=str(item.get("title", "Unspecified risk")),
                description=str(item.get("description", "")),
                severity=item.get("severity", "medium"),
                mitigation=str(item.get("mitigation", "")),
                owner=item.get("owner"),
            )
            for item in payload.get("risks", [])
        ]

        proposal_sections = dict(payload.get("proposal_sections") or {})

        # Preserve common legacy fields when they are supplied at project level.
        for field in (
            "summary",
            "need",
            "activities",
            "outputs",
            "outcomes",
            "goals",
            "timeline",
            "evaluation_plan",
            "sustainability_plan",
            "logic_model",
            "smart_objectives",
            "work_plan",
            "budget_narrative",
        ):
            if field in project_data and field not in proposal_sections:
                proposal_sections[field] = project_data[field]

        applicant_data = dict(payload.get("applicant_data") or {})
        applicant_data.setdefault("organization_name", org_profile.get("name"))
        applicant_data.setdefault("location", org_profile.get("location"))
        applicant_data.setdefault("mission", org_profile.get("mission"))
        applicant_data.setdefault("capacity", org_profile.get("capacity"))

        funding_opportunity = dict(
            payload.get("funding_opportunity") or {}
        )
        if "requirements" not in funding_opportunity:
            funding_opportunity["requirements"] = payload.get(
                "requirements",
                [],
            )
        if "eligibility" not in funding_opportunity:
            funding_opportunity["eligibility"] = payload.get(
                "eligibility",
                [],
            )
        if "priorities" not in funding_opportunity:
            funding_opportunity["priorities"] = payload.get(
                "priorities",
                [],
            )

        return GrantProject(
            project_name=str(
                project_data.get("title")
                or payload.get("project_name")
                or "Untitled Project"
            ),
            organization_name=str(
                org_profile.get("name")
                or payload.get("organization_name")
                or "Unnamed Organization"
            ),
            applicant_data=applicant_data,
            funding_opportunity=funding_opportunity,
            evidence=evidence,
            proposal_sections=proposal_sections,
            budget=list(
                payload.get("budget")
                or project_data.get("budget_items")
                or []
            ),
            risks=risks,
        )


# Optional functional entry points for existing callers.


def analyze_grant(payload: dict[str, Any]) -> dict[str, Any]:
    """Analyze a grant project without instantiating GrantWriter."""
    return GrantWriter().analyze(payload)


def prepare_grant(payload: dict[str, Any]) -> dict[str, Any]:
    """Compose a narrative and return the associated readiness analysis."""
    return GrantWriter().prepare(payload)