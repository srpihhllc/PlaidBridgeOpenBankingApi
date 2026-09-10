# =============================================================================
# FILE: app/utils/template_audit.py -> app/services/registry.py
# DESCRIPTION: Dynamic service discovery and metadata compiler for backend
#              modules and external application integration targets.
# =============================================================================

import os
from dataclasses import dataclass

SERVICES_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SERVICES_DIR, "..", ".."))


@dataclass
class ServiceEntry:
    name: str
    module: str
    description: str
    icon: str
    category: str  # e.g. "fraud", "pdf", "ai", "security", "core", "mobile", "analytics"


# Comprehensive mapping from filename to structural cockpit assets
_SERVICE_META = {
    "balance.py": ("Balance Engine", "fa-wallet", "core"),
    "bank_statement_generator.py": (
        "Bank Statements",
        "fa-file-invoice-dollar",
        "core",
    ),
    "bank_transaction_generator.py": (
        "Transaction Generator",
        "fa-random",
        "core",
    ),
    "card_manager.py": ("Card Manager", "fa-credit-card", "core"),
    "category_analytics.py": (
        "Category Analytics",
        "fa-chart-pie",
        "analytics",
    ),
    "fraud.py": ("Fraud Core Detection", "fa-user-shield", "fraud"),
    "fraud_analytics.py": ("Fraud Analytics", "fa-shield-alt", "fraud"),
    "timeline_analytics.py": (
        "Timeline Analytics",
        "fa-chart-line",
        "analytics",
    ),
    "transaction_analysis.py": (
        "Transaction Analysis",
        "fa-chart-bar",
        "analytics",
    ),
    "transaction_ingestion.py": (
        "Transaction Ingestion",
        "fa-cloud-download-alt",
        "core",
    ),
    "merchant_generator.py": ("Merchant Engine", "fa-store", "core"),
    "pdf_generator.py": ("PDF Generator", "fa-file-pdf", "pdf"),
    "pdf_template_engine.py": ("PDF Template Engine", "fa-layer-group", "pdf"),
    "pdf_parser.py": ("PDF Parser", "fa-file-alt", "pdf"),
    "csv_utils.py": ("CSV Tools", "fa-file-csv", "core"),
    "mfa_service.py": ("MFA Service", "fa-lock", "security"),
    "totp_service.py": ("TOTP Service", "fa-key", "security"),
    "sms.py": ("SMS Service", "fa-sms", "security"),
    "pii_manager.py": ("PII Manager", "fa-user-secret", "security"),
    "rate_limiter.py": ("Rate Limiter", "fa-tachometer-alt", "security"),
    "oauth.py": ("OAuth Core Bridge", "fa-shield-alt", "security"),
    "discrepancy.py": (
        "Discrepancy Engine",
        "fa-exclamation-circle",
        "compliance",
    ),
    "payment_auditor.py": (
        "Payment Auditor",
        "fa-search-dollar",
        "compliance",
    ),
    "lender_verifier.py": ("Lender Verifier", "fa-user-check", "compliance"),
    "tradeline_service.py": (
        "Tradeline Service",
        "fa-balance-scale",
        "compliance",
    ),
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
    "vault_analytics.py": ("Vault Analytics", "fa-archive", "analytics"),
}


def _infer_display_name(module_name: str) -> str:
    """Fallback generator for unmapped raw service assets."""
    return module_name.replace("_", " ").replace(".py", "").title()


def get_service_registry() -> list[ServiceEntry]:
    """
    Scans filesystem modules and builds the fully hydrated array
    of ServiceEntry elements to expose downstream to the cockpit interface.
    """
    entries: list[ServiceEntry] = []

    # 1. Evaluate and append backend module layers
    if os.path.exists(SERVICES_DIR):
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
                    description=f"{display_name} service engine ({module})",
                    icon=icon,
                    category=category,
                )
            )

    # 2. Evaluate and integrate the mobile application framework layout
    mobile_app_path = os.path.join(PROJECT_ROOT, "mobile-app")
    if os.path.exists(mobile_app_path) and os.path.isdir(mobile_app_path):
        entries.append(
            ServiceEntry(
                name="Mobile Application Suite",
                module="mobile-app",
                description="Subscriber workspace layout featuring Expo routing, biometric security, and local Drizzle caching engines.",
                icon="fa-mobile-alt",
                category="mobile",
            )
        )

    # Sort outputs alphabetically within structural groupings
    entries.sort(key=lambda e: (e.category, e.name))
    return entries
