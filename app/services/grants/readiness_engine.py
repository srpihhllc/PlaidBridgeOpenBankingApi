"""Grant-readiness scoring without award prediction."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .schemas import (
    GrantProject,
    ReadinessDimensions,
    ReadinessReport,
    ReviewerReport,
)


READINESS_WEIGHTS = {
    "eligibility_readiness": 0.20,
    "funder_alignment": 0.15,
    "evidence_strength": 0.15,
    "program_feasibility": 0.15,
    "organizational_capacity": 0.10,
    "evaluation_quality": 0.10,
    "budget_defensibility": 0.10,
    "sustainability_strength": 0.05,
}


class ReadinessEngine:
    """Calculates auditable application-readiness indicators."""

    def assess(
        self,
        project: GrantProject,
        *,
        compliance: dict[str, Any],
        reviewers: list[ReviewerReport],
    ) -> ReadinessReport:
        dimensions = self._score_dimensions(project, compliance, reviewers)
        score = self._weighted_score(dimensions)
        risks = list(project.risks)

        for reviewer in reviewers:
            if reviewer.severity in {"high", "critical"}:
                risks.append(
                    {
                        "title": f"{reviewer.reviewer} concern",
                        "description": reviewer.required_revision,
                        "severity": reviewer.severity,
                    }
                )

        revisions = [
            reviewer.required_revision
            for reviewer in reviewers
            if reviewer.required_revision
        ]

        return ReadinessReport(
            readiness_score=score,
            classification=self._classify(score),
            dimensions=dimensions,
            risks=risks,
            required_revisions=revisions,
            human_approval_required=True,
        )

    def _score_dimensions(
        self,
        project: GrantProject,
        compliance: dict[str, Any],
        reviewers: list[ReviewerReport],
    ) -> ReadinessDimensions:
        sections = project.proposal_sections

        return ReadinessDimensions(
            eligibility_readiness=self._presence_score(
                compliance.get("requirements")
            ),
            funder_alignment=self._presence_score(
                sections.get("funder_alignment")
            ),
            evidence_strength=self._evidence_score(project),
            program_feasibility=self._presence_score(
                sections.get("work_plan")
            ),
            organizational_capacity=self._presence_score(
                project.applicant_data.get("capacity")
            ),
            budget_defensibility=self._budget_score(project),
            evaluation_quality=self._presence_score(
                sections.get("evaluation_plan")
            ),
            sustainability_strength=self._presence_score(
                sections.get("sustainability_plan")
            ),
            submission_completeness=self._completeness_score(project),
        )

    @staticmethod
    def _presence_score(value: Any) -> float:
        return 100.0 if value else 0.0

    @staticmethod
    def _evidence_score(project: GrantProject) -> float:
        if not project.evidence:
            return 0.0

        verified = sum(
            item.evidence_type == "verified_fact"
            for item in project.evidence
        )
        return round((verified / len(project.evidence)) * 100, 2)

    @staticmethod
    def _budget_score(project: GrantProject) -> float:
        if not project.budget:
            return 0.0

        complete = all(
            item.get("amount") is not None
            and item.get("justification")
            and item.get("activity")
            and item.get("outcome")
            for item in project.budget
        )
        return 100.0 if complete else 50.0

    @staticmethod
    def _completeness_score(project: GrantProject) -> float:
        populated = sum(
            bool(value) for value in project.proposal_sections.values()
        )
        total = max(len(REQUIRED_SECTIONS), 1)
        return round(min(populated / total, 1.0) * 100, 2)

    @staticmethod
    def _weighted_score(dimensions: ReadinessDimensions) -> float:
        values = asdict(dimensions)
        return round(
            sum(values[name] * weight for name, weight in READINESS_WEIGHTS.items()),
            2,
        )

    @staticmethod
    def _classify(score: float) -> str:
        if score >= 85:
            return "Submission Ready"
        if score >= 70:
            return "Nearly Ready"
        if score >= 50:
            return "Requires Revision"
        return "Not Ready"


REQUIRED_SECTIONS = (
    "funder_alignment",
    "needs_assessment",
    "program_narrative",
    "smart_objectives",
    "logic_model",
    "work_plan",
    "evaluation_plan",
    "budget",
    "budget_narrative",
    "sustainability_plan",
)