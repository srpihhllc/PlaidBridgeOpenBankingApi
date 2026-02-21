# =============================================================================
# FILE: app/services/tradeline_service.py
# DESCRIPTION: Service layer for tradeline operations. Provides retrieval
#              and update helpers for tradeline records. Cockpit‑grade with
#              error handling, logging, and DB safety.
# =============================================================================

import logging
from typing import Any

from app.models import Tradeline, db

logger = logging.getLogger(__name__)


def get_tradeline_details(tradeline_id: int) -> dict[str, Any] | None:
    """
    Retrieve details for a given tradeline.

    Args:
        tradeline_id (int): The ID of the tradeline.

    Returns:
        dict | None: Tradeline details as a dictionary, or None if not found/error.
    """
    try:
        tradeline = Tradeline.query.get(tradeline_id)
        if not tradeline:
            logger.warning(f"[get_tradeline_details] Tradeline {tradeline_id} not found.")
            return None

        return {
            "id": tradeline.id,
            "user_id": tradeline.user_id,
            "account_number": getattr(tradeline, "account_number", None),
            "balance": getattr(tradeline, "balance", 0.0),
            "status": getattr(tradeline, "status", "unknown"),
            "opened_date": (
                tradeline.opened_date.isoformat()
                if getattr(tradeline, "opened_date", None)
                else None
            ),
        }
    except Exception as e:
        logger.error(
            f"[get_tradeline_details] Failed to fetch tradeline {tradeline_id}: {e}",
            exc_info=True,
        )
        return None


def update_tradeline(tradeline_id: int, updates: dict[str, Any]) -> bool:
    """
    Update a tradeline record with provided fields.

    Args:
        tradeline_id (int): The ID of the tradeline to update.
        updates (dict): Dictionary of fields to update.

    Returns:
        bool: True if update succeeded, False otherwise.
    """
    try:
        tradeline = Tradeline.query.get(tradeline_id)
        if not tradeline:
            logger.warning(f"[update_tradeline] Tradeline {tradeline_id} not found for update.")
            return False

        updated_fields = []
        ignored_fields = []

        for field, value in updates.items():
            if hasattr(tradeline, field):
                setattr(tradeline, field, value)
                updated_fields.append(field)
            else:
                ignored_fields.append(field)

        db.session.commit()

        logger.info(
            f"[update_tradeline] Tradeline {tradeline_id} updated successfully. "
            f"Updated fields: {updated_fields or 'none'}. Ignored fields: "
            f"{ignored_fields or 'none'}."
        )
        return True

    except Exception as e:
        db.session.rollback()
        logger.error(
            f"[update_tradeline] Failed to update tradeline {tradeline_id}: {e}",
            exc_info=True,
        )
        return False
