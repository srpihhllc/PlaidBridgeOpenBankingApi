"""Funder-alignment analysis."""

from __future__ import annotations

from .schemas import GrantProject


class FunderAlignmentEngine:
    """Maps project content to stated funder priorities."""

    def analyze(self, project: GrantProject) -> dict:
        priorities = project.funding_opportunity.get("priorities", [])
        narrative = project.proposal_sections.get("program_narrative", "")

        return {
            "priorities": priorities,
            "matched_priorities": [
                priority
                for priority in priorities
                if priority.lower() in str(narrative).lower()
            ],
            "unmatched_priorities": [
                priority
                for priority in priorities
                if priority.lower() not in str(narrative).lower()
            ],
        }