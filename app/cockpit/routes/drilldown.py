# =============================================================================
# FILE: app/cockpit/routes/drilldown.py
# DESCRIPTION: Cockpit-grade drilldown route for safe file inspection.
#              Provides default fallback for audits, prevents traversal attacks,
#              and renders syntax-highlighted code with friendly error handling.
# =============================================================================

import os

from flask import Blueprint, render_template, request
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import PythonLexer

# Define the blueprint with a URL prefix to avoid collisions
drilldown_bp = Blueprint("drilldown", __name__, url_prefix="/cockpit")

# Base repository path for safe file resolution.
REPO_BASE_PATH = "/home/srpihhllc/PlaidBridgeOpenBankingApi"

# Default file used when no ?file= param is provided (for audits/tracer runs)
DEFAULT_FILE = "docs/README.md"


@drilldown_bp.route("/drilldown")
def drilldown_view():
    """
    Renders a view for drilling down into a specific file.

    - Safely resolves a file path provided in the query string.
    - Falls back to DEFAULT_FILE if no param is given (audit-friendly).
    - Prevents directory traversal attacks.
    - Reads the file content and renders syntax-highlighted code.
    - Provides friendly error messages inside the template instead of raw aborts.
    """
    rel_path = request.args.get("file") or DEFAULT_FILE

    safe_path = os.path.normpath(os.path.join(REPO_BASE_PATH, rel_path))
    if not safe_path.startswith(REPO_BASE_PATH):
        return render_template(
            "cockpit/drilldown.html",
            file_path=rel_path,
            highlighted_code="<p style='color:red;'>❌ Invalid file path</p>",
            pygments_css="",
        )

    if not os.path.exists(safe_path):
        return render_template(
            "cockpit/drilldown.html",
            file_path=rel_path,
            highlighted_code=f"<p style='color:red;'>❌ File not found: {rel_path}</p>",
            pygments_css="",
        )

    try:
        with open(safe_path, encoding="utf-8") as f:
            code = f.read()
    except Exception as read_err:
        return render_template(
            "cockpit/drilldown.html",
            file_path=rel_path,
            highlighted_code=f"<p style='color:red;'>⚠️ Could not read file: {read_err}</p>",
            pygments_css="",
        )

    formatter = HtmlFormatter(
        linenos=True, anchorlinenos=True, full=False, cssclass="codehilite"
    )
    highlighted_code = highlight(code, PythonLexer(), formatter)

    return render_template(
        "cockpit/drilldown.html",
        file_path=rel_path,
        highlighted_code=highlighted_code,
        pygments_css=formatter.get_style_defs(".codehilite"),
    )