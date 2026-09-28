"""Skeptical reviewer simulation."""

from __future__ import annotations

from .schemas import GrantProject, ReviewerReport


REVIEWER_ROLES = (
    "Compliance Reviewer",
    "Program Reviewer",
    "Finance Reviewer",
    "Evaluation Reviewer",
    "Community Impact Reviewer",
)


class RedTeamEngine:
    """Identifies weaknesses without making funding decisions."""

    def review(self, project: GrantProject) -> list[ReviewerReport]:
        reports = []

        for role in REVIEWER_ROLES:
            weaknesses = self._weaknesses(project, role)
            reports.append(
                ReviewerReport(
                    reviewer=role,
                    strengths=self._strengths(project),
                    weaknesses=weaknesses,
                    severity="high" if weaknesses else "low",
                    evidence_needed=[
                        "Provide supporting documentation for unresolved claims."
                    ]
                    if weaknesses
                    else [],
                    required_revision=(
                        "Resolve identified weaknesses and document supporting evidence."
                        if weaknesses
                        else ""
                    ),
                )
            )

        return reports

    @staticmethod
    def _strengths(project: GrantProject) -> list[str]:
        strengths = []
        if project.project_name:
            strengths.append("Project is explicitly identified.")
        if project.funding_opportunity:
            strengths.append("Funding opportunity information is present.")
        return strengths

    @staticmethod
    def _weaknesses(
        project: GrantProject,
        role: str,
    ) -> list[str]:
        weaknesses = []

        if not project.funding_opportunity:
            weaknesses.append("Funding opportunity requirements are missing.")

        if not project.evidence:
            weaknesses.append("No evidence register has been provided.")

        if role == "Finance Reviewer" and not project.budget:
            weaknesses.append("No budget has been provided.")

        if role == "Evaluation Reviewer":
            if "evaluation_plan" not in project.proposal_sections:
                weaknesses.append("Evaluation plan is missing.")

        return weaknesses