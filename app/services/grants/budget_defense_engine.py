"""Budget defensibility analysis."""

from __future__ import annotations

from .schemas import GrantProject


class BudgetDefenseEngine:
    """Tests whether costs are connected to activities and outcomes."""

    REQUIRED_FIELDS = (
        "amount",
        "justification",
        "budget_period",
        "activity",
        "outcome",
        "removal_risk",
    )

    def assess(self, project: GrantProject) -> dict:
        findings = []

        for item in project.budget:
            missing = [
                field for field in self.REQUIRED_FIELDS if not item.get(field)
            ]
            findings.append(
                {
                    "item": item.get("name", "Unnamed budget item"),
                    "missing_fields": missing,
                    "defensible": not missing,
                }
            )

        return {
            "items": findings,
            "complete": all(item["defensible"] for item in findings),
        }