# =============================================================================
# FILE: app/services/letter_writer.py
# DESCRIPTION: Service layer for generating and bundling correspondence letters.
# - Uses the correct `Lender` model instead of the deprecated `LenderVerification`.
# - Provides helpers for rendering letters to text and bundling outputs.
# =============================================================================

import logging
from datetime import datetime

from jinja2 import Environment, FileSystemLoader

from app.models import User
from app.models.lender import Lender

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Jinja2 Environment for Letter Templates
# -----------------------------------------------------------------------------
letter_env = Environment(loader=FileSystemLoader("app/templates/letters"), autoescape=True)


# -----------------------------------------------------------------------------
# Internal Helper
# -----------------------------------------------------------------------------
def _generate_document(template_name, context):
    """Helper to render Jinja template and simulate PDF bundling."""
    try:
        template = letter_env.get_template(template_name)
        content = template.render(context)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        doc_id = (
            f"letter_{template_name.replace('.txt', '').replace('.html', '')}_"
            f"{context.get('log_id', 'NOLID')}_{timestamp}"
        )

        return content, doc_id
    except Exception as e:
        logger.error(f"Failed to generate document {template_name}: {e}", exc_info=True)
        return None, None


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------
def generate_letter_3(log_id):
    """
    Generates a dispute confirmation letter (Letter 3) using data from the Lender model.
    :param log_id: The ID of the Lender record to base the letter on.
    :return: A tuple of (letter_content_string, document_id_string)
    """
    lender_record = Lender.query.get(log_id)
    if not lender_record:
        logger.warning(f"Lender record ID {log_id} not found.")
        return None, None

    user = User.query.get(lender_record.user_id)
    if not user:
        logger.error(
            f"User ID {lender_record.user_id} associated with Lender ID {log_id} not found."
        )
        return None, None

    context = {
        "log_id": lender_record.id,
        "user_name": getattr(user, "full_name", "Unknown User"),
        "user_address": getattr(user, "address", "Unknown Address"),
        "date": datetime.now().strftime("%B %d, %Y"),
        "lender_name": getattr(lender_record, "institution_name", "Unknown Lender"),
        "lender_address": getattr(lender_record, "mailing_address", "Unknown Address"),
        "dispute_details": getattr(lender_record, "dispute_reason", "No specific reason provided."),
        "account_number": getattr(lender_record, "account_number", "N/A"),
    }

    return _generate_document("dispute_confirmation_l3.txt", context)


def bundle_all_letters(log_id, document_type=None):
    """
    General function to bundle a document based on log ID and type.
    """
    doc_type = document_type or "L3_DISPUTE"
    if doc_type == "L3_DISPUTE":
        return generate_letter_3(log_id)

    logger.info(f"Document type '{document_type}' not supported for log ID {log_id}.")
    return "Document type not supported", None


def render_letter_to_text(letter_obj):
    """
    Converts a letter object, dict, or raw string into plain text for preview/export.
    Defensive against bad input.
    """
    try:
        if letter_obj is None:
            return "[No letter content]"

        if isinstance(letter_obj, str):
            return letter_obj

        if isinstance(letter_obj, dict):
            lines = [f"{k}: {v}" for k, v in letter_obj.items()]
            return "\n".join(lines)

        # Fallback: string conversion
        return str(letter_obj)
    except Exception as e:
        logger.error(f"Failed to render letter to text: {e}", exc_info=True)
        return f"[Error rendering letter: {e}]"


# -----------------------------------------------------------------------------
# Explicit Exports
# -----------------------------------------------------------------------------
__all__ = [
    "generate_letter_3",
    "bundle_all_letters",
    "render_letter_to_text",
]
