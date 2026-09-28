"""Trust, provenance, and human-oversight utilities."""

from __future__ import annotations

from typing import Any


class TrustEngine:
    """Enforces traceability and prevents unsupported assertions."""

    ALLOWED_EVIDENCE_TYPES = {
        "verified_fact",
        "applicant_claim",
        "assumption",
        "missing_information",
    }

    def validate_evidence(self, evidence: list[dict[str, Any]]) -> list[str]:
        errors = []

        for index, item in enumerate(evidence):
            evidence_type = item.get("evidence_type")
            if evidence_type not in self.ALLOWED_EVIDENCE_TYPES:
                errors.append(
                    f"Evidence item {index} has an invalid evidence type."
                )

            if evidence_type == "verified_fact" and not item.get("source"):
                errors.append(
                    f"Evidence item {index} requires a source."
                )

        return errors

    @staticmethod
    def requires_human_approval() -> bool:
        return True