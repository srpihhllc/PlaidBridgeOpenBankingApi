# =============================================================================
# FILE: app/services/letter_renderer.py
# DESCRIPTION: Core template engine for letters. Handles Jinja2 environment,
# caching, and raw text rendering.
# =============================================================================

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Jinja2 Environment Configuration
# -----------------------------------------------------------------------------
# Using Environment with FileSystemLoader caches templates in memory 
# instead of reading from disk on every render call.
TEMPLATE_DIR = Path("app/templates/letters")
letter_env = Environment(
    loader=FileSystemLoader(searchpath=str(TEMPLATE_DIR)),
    autoescape=True,
    trim_blocks=True,   # Removes the first newline after a block
    lstrip_blocks=True  # Strips tabs and spaces from the beginning of a line to a block
)


def render_letter(template_name: str, context: dict[str, Any]) -> str:
    """
    Renders a Jinja2 template with the provided context dictionary.
    
    :param template_name: The filename of the template (e.g., 'dispute_confirmation_l3.txt')
    :param context: Dictionary of dynamic values to inject into the template
    :return: Rendered string
    :raises FileNotFoundError: If the template file does not exist in the template directory
    """
    try:
        template = letter_env.get_template(template_name)
        return template.render(context)
        
    except TemplateNotFound as e:
        logger.error(f"Template not found in {TEMPLATE_DIR}: {template_name}")
        raise FileNotFoundError(f"Template {template_name} not found") from e
        
    except Exception as e:
        logger.error(f"Error rendering template {template_name}: {e}", exc_info=True)
        raise