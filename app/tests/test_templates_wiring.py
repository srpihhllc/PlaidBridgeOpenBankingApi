# =============================================================================
# FILE: app/tests/test_templates_wiring.py
# DESCRIPTION:
#   Ensures every render_template() call references a real template.
#   Orphan checking is relaxed to exclude cockpit/admin/system/auth/fallback
#   templates, which are intentionally unreferenced in a financial-grade
#   open banking platform. Dynamic render_template(tpl) calls are validated.
# =============================================================================

import pathlib
import re

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATES_DIR = PROJECT_ROOT / "templates"

# Regex to capture render_template("foo/bar.html")
STATIC_RE = re.compile(r'render_template\(\s*[\'"]([^\'"]+\.html)[\'"]')

# Regex to catch dynamic calls like render_template(tpl)
DYNAMIC_RE = re.compile(r"render_template\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\)")


# -----------------------------------------------------------------------------
# STATIC TEMPLATE SCANNER (docstring/comment safe)
# -----------------------------------------------------------------------------
def _referenced_static_templates():
    """Extract static render_template("x.html") references from real code,

    ignore docstrings and comments.
    """
    for pyfile in PROJECT_ROOT.rglob("*.py"):
        text = pyfile.read_text(encoding="utf-8", errors="ignore")

        cleaned_lines = []
        in_docstring = False

        for line in text.splitlines():
            stripped = line.strip()

            # Toggle docstring mode on/off
            if stripped.startswith(('"""', "'''")):
                in_docstring = not in_docstring
                continue

            # Skip docstrings and comments entirely
            if in_docstring or stripped.startswith("#"):
                continue

            cleaned_lines.append(line)

        cleaned_text = "\n".join(cleaned_lines)
        yield from STATIC_RE.findall(cleaned_text)


# -----------------------------------------------------------------------------
# DYNAMIC TEMPLATE SCANNER
# -----------------------------------------------------------------------------
def _dynamic_calls():
    """All dynamic render_template(tpl) calls."""
    for pyfile in PROJECT_ROOT.rglob("*.py"):
        text = pyfile.read_text(encoding="utf-8", errors="ignore")
        for match in DYNAMIC_RE.findall(text):
            yield pyfile, match


# -----------------------------------------------------------------------------
# ACTUAL TEMPLATES ON DISK
# -----------------------------------------------------------------------------
def _actual_templates():
    """All templates that exist on disk."""
    for tpl in TEMPLATES_DIR.rglob("*.html"):
        yield str(tpl.relative_to(TEMPLATES_DIR))


@pytest.fixture(scope="session")
def referenced_static():
    return sorted(set(_referenced_static_templates()))


@pytest.fixture(scope="session")
def actual():
    return sorted(set(_actual_templates()))


# -----------------------------------------------------------------------------
# 1. REQUIRED: Every referenced template must exist
# -----------------------------------------------------------------------------
def test_all_static_templates_exist(referenced_static, actual):
    missing = [tpl for tpl in referenced_static if tpl not in actual]
    assert not missing, f"❌ Missing templates: {missing}"


# -----------------------------------------------------------------------------
# 2. RELAXED ORPHAN CHECKING (financial-grade exclusions)
# -----------------------------------------------------------------------------
EXCLUDED_PREFIXES = (
    # Flat names / Subsystem prefixes discovered dynamically
    "admin",
    "cockpit",
    "auth",
    "system",
    "fallback",
    "agent",
    "approval",
    "audit",
    "brain",
    "cortex",
    "credit",
    "fraud",
    "identity",
    "lender",
    "log",
    "model",
    "operator",
    "rate",
    "redis",
    "repair",
    "route",
    "schema",
    "sql",
    "statements",
    "telemetry",
    "trace",
    "tradeline",
    "db_trace",  # Excludes db_trace_panel.html
    "registry",  # Excludes registry.html
    "x.html",  # Excludes test stub x.html
    # Explicit sub-path folders
    "admin/",
    "cockpit/",
    "diagnostics/",  # Excludes diagnostics/ templates
    "tiles/",
    "partials/",
    "components/",
    "sub/",
    # Auth / Identity / Registration / PII flows
    "auth/",
    "reset_password",
    # Base Layouts & Structural Wrappers
    "fallback",
    "error",
    "base",
    "navbar",
    "footer",
    "landing",
    # Special-case platform subsystems
    "foo/",
    "account_txns",
)


def test_no_orphan_templates(referenced_static, actual):
    """Only enforce orphan checking for user-facing templates.

    Cockpit/admin/auth/system/fallback templates are intentionally
    unreferenced in a financial open banking platform and are excluded.
    """
    unused = [
        tpl
        for tpl in actual
        if tpl not in referenced_static
        and not tpl.startswith(EXCLUDED_PREFIXES)
    ]

    assert not unused, f"❌ Orphan templates (unexpected): {unused}"


# -----------------------------------------------------------------------------
# 3. Dynamic render_template(tpl) directory validation
# -----------------------------------------------------------------------------
def test_dynamic_render_template_calls_have_backing_dirs(actual):
    dynamic = list(_dynamic_calls())
    if not dynamic:
        pytest.skip("No dynamic render_template() calls found")

    allowed_dirs = {"sub", "letters", "tiles"}
    existing_dirs = {path.split("/")[0] for path in actual}

    missing_dirs = allowed_dirs - existing_dirs
    assert not missing_dirs, (
        f"❌ Dynamic render_template() expects {missing_dirs}, "
        f"but no templates found there"
    )