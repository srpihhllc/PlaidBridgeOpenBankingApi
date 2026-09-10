# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/services/grant_writer.py

"""
grant_writer.py — Core AI-ready utility engine for drafting proposal narratives.
Centralized service for government funding applications and NOFO metadata processing.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

# =============================================================================
# 1. SPECIALIZED GRANT TEMPLATES (From your original blueprint logic)
# =============================================================================


def _compose_sbir(payload: Dict[str, Any]) -> str:
    org = payload.get("org_profile", {})
    project = payload.get("project", {})
    mission = org.get("mission", "Our mission is to empower communities.")
    goals = project.get("goals", "N/A")

    return f"""
[GRANT TYPE]: SBIR PROPOSAL NARRATIVE

Organization: {org.get("name", "Unknown")} | Location: {org.get("location", "Unknown")}
Project: {project.get("title", "Untitled")}
Mission Alignment: {mission}
Funding Goal: ${project.get("budget", "0")}
Project Timeline: {project.get("timeline", "TBD")}

Summary:
This SBIR proposal seeks to fund an early-stage innovation that targets {goals}.
Our team consists of interdisciplinary experts in R&D and social impact.
We believe this aligns with the federal mandate to accelerate commercial readiness
for high-tech entrepreneurs.
""".strip()


def _compose_cdbg(payload: Dict[str, Any]) -> str:
    org_name = payload.get("org_profile", {}).get("name", "Organization")
    return f"📜 [CDBG] Community Development Block Grant Narrative for {org_name} - Pipeline Pending."


def _compose_rbdg(payload: Dict[str, Any]) -> str:
    project_title = payload.get("project", {}).get("title", "Project")
    return f"🌾 [RBDG] Rural Business Development Grant Narrative for {project_title} - Pipeline Pending."


def _compose_eda(payload: Dict[str, Any]) -> str:
    return "📈 [EDA] Economic Development Administration Proposal Narrative - Pipeline Pending."


# =============================================================================
# 2. GENERAL NOFO FALLBACK (From your original service logic)
# =============================================================================


def _compose_general_nofo(payload: Dict[str, Any]) -> str:
    grant_type = payload.get("grant_type", "general")
    nofo = payload.get("nofo", "No NOFO guidance provided.")

    return f"""
[GRANT TYPE]: {grant_type.upper()}

[OBJECTIVE]
This grant proposal aims to fulfill the requirements defined in the provided NOFO guidance:
"{nofo}"

[STRATEGY]
We propose a 3-phase implementation:
1. Assessment of target population needs
2. Allocation of resources based on verified impact zones
3. Weekly reporting to ensure compliance and transparency

[IMPACT]
Our solution targets measurable outcomes in housing stability, applicant throughput,
and cost reduction per capita.

[COMPLIANCE]
All documentation and funding will be tracked via FinBrain's orchestration memory and
published via the org_score logs.
""".strip()


# =============================================================================
# 3. AUTHORITATIVE DISPATCH REGISTRY
# =============================================================================

_GRANT_DISPATCHER = {
    "sbir": _compose_sbir,
    "cdbg": _compose_cdbg,
    "rbdg": _compose_rbdg,
    "eda": _compose_eda,
}


def compose_grant(payload: Dict[str, Any]) -> str:
    """
    Main entry point for SymphonyAI and subscriber services.
    Routes the payload to the correct specialized template, or falls back to the general NOFO format.

    Args:
        payload (dict): Requires a 'grant_type'. Can include 'org_profile', 'project', or 'nofo' strings.
    """
    grant_type = payload.get("grant_type", "general")

    if not grant_type:
        logger.warning(
            "Empty grant_type provided. Defaulting to general NOFO payload."
        )
        grant_type = "general"

    normalized_type = grant_type.strip().lower()

    # Check if we have a specialized template (like SBIR)
    dispatcher = _GRANT_DISPATCHER.get(normalized_type)

    if dispatcher:
        # Use specialized template
        return dispatcher(payload)
    else:
        # Fall back to the generic NOFO logic
        logger.info(
            f"Using generic NOFO template for grant type: {grant_type}"
        )
        return _compose_general_nofo(payload)
