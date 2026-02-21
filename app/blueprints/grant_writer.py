# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/blueprints/grant_writer.py


def compose_grant(grant_type, data):
    org = data.get("org_profile", {})
    project = data.get("project", {})
    mission = org.get("mission", "Our mission is to empower communities.")
    goals = project.get("goals", "N/A")

    if grant_type.lower() == "sbir":
        return f"""
SBIR Grant Proposal Narrative

Organization: {org.get("name")} | Location: {org.get("location")}
Project: {project.get("title")}
Mission Alignment: {mission}
Funding Goal: ${project.get("budget")}
Project Timeline: {project.get("timeline")}

Summary:
This SBIR proposal seeks to fund an early-stage innovation that targets {goals}.
Our team consists of interdisciplinary experts in R&D and social impact.
We believe this aligns with the federal mandate to accelerate commercial readiness
for high-tech entrepreneurs.
"""
    elif grant_type.lower() == "cdbg":
        return "📜 [CDBG] Narrative coming soon..."
    # Add handlers for RBDG, EDA, etc.
    else:
        raise ValueError("Unsupported grant type")
