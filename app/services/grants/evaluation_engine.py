"""Evaluation-plan validation."""

from __future__ import annotations

from .schemas import GrantProject


REQUIRED_OBJECTIVE_FIELDS = (
    "baseline",
    "target",
    "indicator",
    "data_source",
    "collection_method",
    "collection_frequency",
    "responsible_person",
    "reporting_date",
)


class EvaluationEngine:
    """Validates measurable objectives and evaluation plans."""

    def assess(self, project: GrantProject) -> dict:
        objectives = project.proposal_sections.get("smart_objectives", [])
        results = []

        for objective in objectives:
            missing = [
                field
                for field in REQUIRED_OBJECTIVE_FIELDS
                if not objective.get(field)
            ]
            results.append(
                {
                    "objective": objective.get("statement", ""),
                    "missing_fields": missing,
                    "complete": not missing,
                }
            )

        return {
            "objectives": results,
            "complete": all(item["complete"] for item in results),
        }