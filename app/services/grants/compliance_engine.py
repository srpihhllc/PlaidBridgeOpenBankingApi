"""Eligibility and compliance analysis."""

from __future__ import annotations

from typing import Any

from .schemas import GrantProject


class ComplianceEngine:
    """Checks whether known requirements are addressed."""

    def assess(self, project: GrantProject) -> dict[str, Any]:
        opportunity = project.funding_opportunity
        requirements = opportunity.get("requirements", [])
        applicant = project.applicant_data

        results = []
        for requirement in requirements:
            results.append(
                {
                    "requirement": requirement,
                    "status": self._status(requirement, applicant),
                    "evidence": self._matching_evidence(project, requirement),
                }
            )

        return {
            "requirements": results,
            "missing_requirements": [
                item["requirement"]
                for item in results
                if item["status"] == "missing"
            ],
            "human_verification_required": True,
        }

    @staticmethod
    def _status(requirement: str, applicant: dict[str, Any]) -> str:
        return "addressed" if requirement in applicant else "missing"

    @staticmethod
    def _matching_evidence(
        project: GrantProject,
        requirement: str,
    ) -> list[str]:
        return [
            item.claim
            for item in project.evidence
            if requirement.lower() in item.claim.lower()
        ]