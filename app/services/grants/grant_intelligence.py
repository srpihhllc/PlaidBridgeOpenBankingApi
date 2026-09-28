"""Core orchestration and master directive for FinBrain Grant Intelligence."""

from __future__ import annotations

from typing import Any

from .compliance_engine import ComplianceEngine
from .readiness_engine import ReadinessEngine
from .red_team_engine import RedTeamEngine
from .schemas import GrantProject


MASTER_DIRECTIVE = """
You are FinBrain Grant Intelligence.

Your purpose is to help transform eligible projects into clear,
evidence-supported, funder-aligned applications ready for human review
and submission.

You must:

1. Analyze funding opportunities.
2. Verify eligibility.
3. Extract requirements.
4. Map requirements to proposal sections and attachments.
5. Distinguish verified facts, applicant claims, assumptions, and missing
   information.
6. Validate evidence.
7. Align need, activities, outputs, outcomes, impact, budget, and evaluation.
8. Perform consistency reviews across all application components.
9. Conduct skeptical reviewer analysis.
10. Display risks, deficiencies, and unresolved questions prominently.
11. Require human approval before submission.

Never:

- Invent statistics.
- Invent citations.
- Invent partnerships.
- Invent grants or awards.
- Invent credentials.
- Invent outcomes.
- Guarantee funding.
- Predict award probability.
- Submit an application without human approval.
"""


REQUIRED_OUTPUTS = (
    "eligibility_assessment",
    "funder_alignment_analysis",
    "evidence_register",
    "needs_assessment",
    "program_narrative",
    "smart_objectives",
    "logic_model",
    "work_plan",
    "evaluation_plan",
    "budget",
    "budget_narrative",
    "risk_register",
    "compliance_checklist",
    "attachment_checklist",
    "reviewer_critique",
    "readiness_report",
    "human_review_checklist",
)


class GrantIntelligence:
    """Coordinates grant analysis, review, and readiness assessment."""

    def __init__(
        self,
        *,
        compliance_engine: ComplianceEngine | None = None,
        red_team_engine: RedTeamEngine | None = None,
        readiness_engine: ReadinessEngine | None = None,
    ) -> None:
        self.compliance_engine = compliance_engine or ComplianceEngine()
        self.red_team_engine = red_team_engine or RedTeamEngine()
        self.readiness_engine = readiness_engine or ReadinessEngine()

    def analyze(self, project: GrantProject) -> dict[str, Any]:
        """Produce an auditable grant-readiness analysis."""
        compliance = self.compliance_engine.assess(project)
        reviewers = self.red_team_engine.review(project)
        readiness = self.readiness_engine.assess(
            project,
            compliance=compliance,
            reviewers=reviewers,
        )

        return {
            "project_name": project.project_name,
            "organization_name": project.organization_name,
            "directive": MASTER_DIRECTIVE,
            "required_outputs": list(REQUIRED_OUTPUTS),
            "eligibility_assessment": compliance,
            "reviewer_critique": reviewers,
            "readiness_report": readiness,
            "human_review_required": True,
        }

    def can_submit(self, human_approved: bool) -> bool:
        """Submission is impossible unless an authorized human approves it."""
        return human_approved