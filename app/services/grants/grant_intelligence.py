"""Core orchestration and master directive for FinBrain Grant Intelligence."""



from __future__ import annotations



from dataclasses import asdict

from typing import Any



from .budget_defense_engine import BudgetDefenseEngine

from .compliance_engine import ComplianceEngine

from .eligibility_engine import EligibilityEngine

from .evaluation_engine import EvaluationEngine

from .evidence_engine import EvidenceEngine

from .funder_alignment_engine import FunderAlignmentEngine

from .program_design_engine import ProgramDesignEngine

from .readiness_engine import ReadinessEngine

from .red_team_engine import RedTeamEngine

from .schemas import GrantProject

from .trust_engine import TrustEngine





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

    """Coordinates grant analysis, review, and readiness assessment across all 10 engines."""



    def __init__(

        self,

        *,

        compliance_engine: ComplianceEngine | None = None,

        eligibility_engine: EligibilityEngine | None = None,

        funder_alignment_engine: FunderAlignmentEngine | None = None,

        program_design_engine: ProgramDesignEngine | None = None,

        budget_defense_engine: BudgetDefenseEngine | None = None,

        evidence_engine: EvidenceEngine | None = None,

        evaluation_engine: EvaluationEngine | None = None,

        trust_engine: TrustEngine | None = None,

        red_team_engine: RedTeamEngine | None = None,

        readiness_engine: ReadinessEngine | None = None,

    ) -> None:

        self.compliance_engine = compliance_engine or ComplianceEngine()

        self.eligibility_engine = eligibility_engine or EligibilityEngine()

        self.funder_alignment_engine = funder_alignment_engine or FunderAlignmentEngine()

        self.program_design_engine = program_design_engine or ProgramDesignEngine()

        self.budget_defense_engine = budget_defense_engine or BudgetDefenseEngine()

        self.evidence_engine = evidence_engine or EvidenceEngine()

        self.evaluation_engine = evaluation_engine or EvaluationEngine()

        self.trust_engine = trust_engine or TrustEngine()

        self.red_team_engine = red_team_engine or RedTeamEngine()

        self.readiness_engine = readiness_engine or ReadinessEngine()



    def analyze(self, project: GrantProject) -> dict[str, Any]:

        """Produce an auditable grant-readiness analysis across all engines."""

        compliance = self.compliance_engine.assess(project)

        eligibility = self.eligibility_engine.assess(project)

        alignment = self.funder_alignment_engine.analyze(project)

        program_design = self.program_design_engine.assess(project)

        budget_defense = self.budget_defense_engine.assess(project)

        evaluation = self.evaluation_engine.assess(project)

        classified_evidence = self.evidence_engine.classify(project.evidence)

        missing_evidence = self.evidence_engine.missing(project.evidence)

        evidence_dicts = [asdict(item) for item in project.evidence]

        trust_errors = self.trust_engine.validate_evidence(evidence_dicts)

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

            "eligibility_assessment": eligibility,

            "compliance_checklist": compliance,

            "funder_alignment_analysis": alignment,

            "program_design": program_design,

            "budget_defense": budget_defense,

            "evaluation_plan": evaluation,

            "evidence_register": {

                "classified": {k: [asdict(i) for i in v] for k, v in classified_evidence.items()},

                "missing_count": len(missing_evidence),

                "trust_validation_errors": trust_errors,

            },

            "reviewer_critique": reviewers,

            "readiness_report": readiness,

            "human_review_required": self.trust_engine.requires_human_approval(),

        }



    def can_submit(self, human_approved: bool) -> bool:

        """Submission is impossible unless an authorized human approves it."""

        return human_approved

