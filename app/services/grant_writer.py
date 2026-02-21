# app/services/grant_writer.py


def compose_grant(payload):
    """
    Generate a basic grant response using NOFO metadata.

    Args:
        payload (dict): {
            "grant_type": "emergency_housing",
            "nofo": "Provide safe housing for low-income families..."
        }

    Returns:
        str: Composed grant proposal (text block)
    """
    grant_type = payload.get("grant_type", "general")
    nofo = payload.get("nofo", "No NOFO guidance provided.")

    proposal = f"""
[GRANT TYPE]: {grant_type.upper()}

[OBJECTIVE]
This grant proposal aims to fulfill the requirements defined in the provided NOFO guidance:
\"{nofo}\"

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
"""

    return proposal.strip()
