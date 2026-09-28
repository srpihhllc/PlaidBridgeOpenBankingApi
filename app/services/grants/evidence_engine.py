"""Evidence classification and citation tracking."""

from __future__ import annotations

from .schemas import EvidenceItem


class EvidenceEngine:
    """Maintains a distinction between facts, claims, assumptions, and gaps."""

    def classify(self, items: list[EvidenceItem]) -> dict[str, list[EvidenceItem]]:
        result = {
            "verified_facts": [],
            "applicant_claims": [],
            "assumptions": [],
            "missing_information": [],
        }

        for item in items:
            key = f"{item.evidence_type}s"
            if key in result:
                result[key].append(item)

        return result

    def missing(self, items: list[EvidenceItem]) -> list[EvidenceItem]:
        return [
            item
            for item in items
            if item.evidence_type == "missing_information"
        ]