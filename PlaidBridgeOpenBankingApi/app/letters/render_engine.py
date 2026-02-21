# app/letters/render_engine.py

"""
Renders legal dispute letters by injecting user, bureau, and dispute data into templates.
Supports plaintext .txt and Jinja2-style dynamic tokens.
"""

import os

from jinja2 import Template

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")


def load_template(template_name: str) -> str:
    """Load a raw letter template from the filesystem."""
    path = os.path.join(TEMPLATE_DIR, template_name)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"📭 Template '{template_name}' not found.")
    with open(path, encoding="utf-8") as f:
        return f.read()


def render_letter(template_name: str, user: dict, bureau: dict, metadata: dict = None) -> str:
    """
    Render the selected template using Jinja2 with user + bureau data injected.

    Args:
        template_name: str, e.g., "identity_theft.txt"
        user: dict with fields like name, address, dob, ssn
        bureau: dict from app.letters.bureaus
        metadata: dict with optional dispute-specific values

    Returns:
        Rendered string letter content
    """
    raw = load_template(template_name)
    context = {"user": user, "bureau": bureau, "dispute": metadata or {}}
    return Template(raw).render(**context)
