# =============================================================================
# FILE: app/services/statement_service.py
# DESCRIPTION: Service layer for bank statement operations. Provides helpers
#              to fetch last statement data and generate statement PDFs.
#              Currently stubs; replace with real DB + PDF logic.
# =============================================================================

import logging
from datetime import datetime
from typing import Any

from app.models import BankStatement

logger = logging.getLogger(__name__)


def get_last_statement_data(user_id: int) -> dict[str, Any] | None:
    """
    Retrieve the most recent bank statement for a given user.

    Args:
        user_id (int): The ID of the user.

    Returns:
        dict | None: Statement details or None if not found.
    """
    try:
        stmt = (
            BankStatement.query.filter_by(user_id=user_id)
            .order_by(BankStatement.generated_at.desc())
            .first()
        )
        if not stmt:
            logger.warning(f"[get_last_statement_data] No statements found for user_id={user_id}")
            return None

        return {
            "id": stmt.id,
            "user_id": stmt.user_id,
            "period_start": (stmt.period_start.isoformat() if stmt.period_start else None),
            "period_end": stmt.period_end.isoformat() if stmt.period_end else None,
            "balance": stmt.balance,
            "generated_at": (stmt.generated_at.isoformat() if stmt.generated_at else None),
        }
    except Exception as e:
        logger.error(
            f"[get_last_statement_data] Failed for user_id={user_id}: {e}",
            exc_info=True,
        )
        return None


def generate_statement_pdf(user_id: int) -> bytes:
    """
    Generate a PDF bank statement for a given user.
    Currently returns a stubbed PDF payload.

    Args:
        user_id (int): The ID of the user.

    Returns:
        bytes: PDF binary content.
    """
    try:
        # TODO: Replace with real PDF generation (e.g., ReportLab, WeasyPrint)
        logger.info(f"[generate_statement_pdf] Generating stub PDF for user_id={user_id}")
        pdf_content = (
            f"Bank Statement for user {user_id}\n"
            f"Generated at {datetime.utcnow().isoformat()}\n"
            f"(Stub content — replace with real statement data)"
        )
        return pdf_content.encode("utf-8")
    except Exception as e:
        logger.error(f"[generate_statement_pdf] Failed for user_id={user_id}: {e}", exc_info=True)
        return b""
