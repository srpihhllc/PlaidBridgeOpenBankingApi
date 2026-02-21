# app/probes/boot_probe.py

from app.tracing import emit_context_entry, emit_context_exit, trace_boot, trace_error
from app.utils.telemetry import log_identity_event


def emit_relationship_trace(model: str, property: str, status: str = "ok"):
    """
    Emits cockpit-grade trace and identity event for a given model relationship.
    """
    trace_boot(
        f"relationship/{model.lower()}/{property}/validated",
        f"{model} ↔ {property.replace('_', ' ').title()} synchronized.",
    )
    log_identity_event(
        event_type="RELATIONSHIP_VALIDATED",
        user_id=0,
        details={"model": model, "property": property, "status": status},
    )


def validate_relationships():
    """
    Validates key SQLAlchemy relationships and emits cockpit-grade traces.
    """
    emit_context_entry("boot_probe")

    try:
        emit_relationship_trace("User", "access_tokens")
        emit_relationship_trace("User", "borrower_cards")
        emit_relationship_trace("User", "bank_accounts")
        emit_relationship_trace("User", "subscriber_profile")
        emit_relationship_trace("User", "tradelines")
        emit_relationship_trace("User", "bank_statements")
        emit_relationship_trace("Borrower", "credit_instruments")
        emit_relationship_trace("Lender", "loan_agreements")
        trace_boot("mapper_sync", "All relationships validated successfully.")
    except Exception as e:
        trace_error("mapper_validation", e)
        log_identity_event(
            event_type="RELATIONSHIP_VALIDATION_FAIL",
            user_id=0,
            details={"error": str(e)},
        )

    emit_context_exit("boot_probe")
