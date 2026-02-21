#  /home/srpihhllc/PlaidBridgeOpenBankingApi/app/services/registry.py


import os
from dataclasses import dataclass

SERVICES_DIR = os.path.join(os.path.dirname(__file__))


@dataclass
class ServiceEntry:
    name: str
    module: str
    description: str
    icon: str
    category: str  # e.g. "fraud", "pdf", "ai", "security", "core"


# Simple mapping from filename to human metadata
_SERVICE_META = {
    "balance.py": ("Balance Engine", "fa-wallet", "core"),
    "bank_statement_generator.py": (
        "Bank Statements",
        "fa-file-invoice-dollar",
        "core",
    ),
    "card_manager.py": ("Card Manager", "fa-credit-card", "core"),
    "category_analytics.py": ("Category Analytics", "fa-chart-pie", "analytics"),
    "fraud_analytics.py": ("Fraud Analytics", "fa-shield-alt", "fraud"),
    "timeline_analytics.py": ("Timeline Analytics", "fa-chart-line", "analytics"),
    "transaction_analysis.py": ("Transaction Analysis", "fa-chart-bar", "analytics"),
    "transaction_ingestion.py": (
        "Transaction Ingestion",
        "fa-cloud-download-alt",
        "core",
    ),
    "pdf_generator.py": ("PDF Generator", "fa-file-pdf", "pdf"),
    "pdf_template_engine.py": ("PDF Template Engine", "fa-layer-group", "pdf"),
    "pdf_parser.py": ("PDF Parser", "fa-file-alt", "pdf"),
    "csv_utils.py": ("CSV Tools", "fa-file-csv", "core"),
    "mfa_service.py": ("MFA Service", "fa-lock", "security"),
    "totp_service.py": ("TOTP Service", "fa-key", "security"),
    "sms.py": ("SMS Service", "fa-sms", "security"),
    "pii_manager.py": ("PII Manager", "fa-user-secret", "security"),
    "rate_limiter.py": ("Rate Limiter", "fa-tachometer-alt", "security"),
    "discrepancy.py": ("Discrepancy Engine", "fa-exclamation-circle", "compliance"),
    "payment_auditor.py": ("Payment Auditor", "fa-search-dollar", "compliance"),
    "lender_verifier.py": ("Lender Verifier", "fa-user-check", "compliance"),
    "tradeline_service.py": ("Tradeline Service", "fa-balance-scale", "compliance"),
    "mock_data_service.py": ("Mock Data Service", "fa-database", "core"),
    "statement_service.py": ("Statement Service", "fa-file-contract", "core"),
    "plaid_api.py": ("Plaid API", "fa-link", "core"),
    "fintech_api.py": ("Fintech API", "fa-plug", "core"),
    "grant_writer.py": ("Grant Writer", "fa-file-signature", "ai"),
    "letter_writer.py": ("Letter Writer", "fa-envelope-open-text", "core"),
    "letter_renderer.py": ("Letter Renderer", "fa-envelope", "core"),
    "symphony_ai.py": ("Symphony AI", "fa-robot", "ai"),
    "lending_cognition.py": ("Lending Cognition", "fa-brain", "ai"),
    "audit_service.py": ("Audit Service", "fa-clipboard-check", "core"),
}


def _infer_display_name(module_name: str) -> str:
    # Fallback if not in _SERVICE_META
    base = module_name.replace("_", " ").replace(".py", "").title()
    return base


def get_service_registry() -> list[ServiceEntry]:
    entries: list[ServiceEntry] = []

    for fname in os.listdir(SERVICES_DIR):
        if not fname.endswith(".py") or fname == "__init__.py":
            continue

        module = fname
        meta = _SERVICE_META.get(fname)
        if meta:
            display_name, icon, category = meta
        else:
            display_name = _infer_display_name(fname)
            icon = "fa-cube"
            category = "misc"

        entries.append(
            ServiceEntry(
                name=display_name,
                module=module,
                description=f"{display_name} service module ({module})",
                icon=icon,
                category=category,
            )
        )

    # Optional sort by category then name
    entries.sort(key=lambda e: (e.category, e.name))
    return entries
