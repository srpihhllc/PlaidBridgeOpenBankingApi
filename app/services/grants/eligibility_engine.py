"""Eligibility assessment."""

from __future__ import annotations

from typing import Any

from .schemas import GrantProject


class EligibilityEngine:
    """Evaluates documented eligibility conditions."""

    def assess(self, project: GrantProject) -> dict[str, Any]:
        requirements = project.funding_opportunity.get("eligibility", [])
        applicant = project.applicant_data

        checks = [
            {
                "requirement": requirement,
                "status": "verified"
                if requirement in applicant
                else "unverified",
            }
            for requirement in requirements
        ]

        return {
            "checks": checks,
            "ready_for_human_verification": True,
        }