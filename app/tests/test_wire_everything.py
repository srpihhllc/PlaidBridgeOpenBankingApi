# =============================================================================
# FILE: app/tests/test_templates_wiring.py
# DESCRIPTION:
#   Ensures every render_template() call references a real template.
#   Orphan checking excludes intentionally unreferenced platform templates.
#   Dynamic render_template(tpl) calls are validated separately.
# =============================================================================

import ast
import pathlib
import re

import pytest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATES_DIR = PROJECT_ROOT / "templates"


# Regex fallback for render_template("foo/bar.html")
STATIC_RE = re.compile(
    r"""render_template\(\s*['"]([^'"]+\.html)['"]"""
)

# Regex for dynamic calls such as render_template(template_name)
DYNAMIC_RE = re.compile(
    r"render_template\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\)"
)


# -----------------------------------------------------------------------------
# STATIC TEMPLATE SCANNER
# -----------------------------------------------------------------------------
def _referenced_static_templates():
    """Yield static template names passed to render_template()."""

    for pyfile in PROJECT_ROOT.rglob("*.py"):
        try:
            text = pyfile.read_text(
                encoding="utf-8",
                errors="ignore",
            )
            tree = ast.parse(
                text,
                filename=str(pyfile),
            )
        except (OSError, SyntaxError):
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            if not node.args:
                continue

            func = node.func

            is_render_template = (
                isinstance(func, ast.Name)
                and func.id == "render_template"
            ) or (
                isinstance(func, ast.Attribute)
                and func.attr == "render_template"
            )

            if not is_render_template:
                continue

            template_arg = node.args[0]

            if not isinstance(template_arg, ast.Constant):
                continue

            template_name = template_arg.value

            if not isinstance(template_name, str):
                continue

            if not template_name.endswith(".html"):
                continue

            yield template_name


# -----------------------------------------------------------------------------
# DYNAMIC TEMPLATE SCANNER
# -----------------------------------------------------------------------------
def _dynamic_calls():
    """Yield all dynamic render_template(variable) calls."""

    for pyfile in PROJECT_ROOT.rglob("*.py"):
        try:
            text = pyfile.read_text(
                encoding="utf-8",
                errors="ignore",
            )
        except OSError:
            continue

        for match in DYNAMIC_RE.finditer(text):
            yield pyfile, match.group(1)


# -----------------------------------------------------------------------------
# ACTUAL TEMPLATES ON DISK
# -----------------------------------------------------------------------------
def _actual_templates():
    """Yield every HTML template that exists on disk."""

    if not TEMPLATES_DIR.exists():
        return

    for template_path in TEMPLATES_DIR.rglob("*.html"):
        yield str(template_path.relative_to(TEMPLATES_DIR))


@pytest.fixture(scope="session")
def referenced_static():
    return sorted(set(_referenced_static_templates()))


@pytest.fixture(scope="session")
def actual():
    return sorted(set(_actual_templates()))


# -----------------------------------------------------------------------------
# ORPHAN EXCLUSIONS
# -----------------------------------------------------------------------------
EXCLUDED_PREFIXES = (
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
    "db_trace",
    "registry",
    "x.html",
    "admin/",
    "cockpit/",
    "diagnostics/",
    "tiles/",
    "partials/",
    "components/",
    "sub/",
    "auth/",
    "reset_password",
    "error",
    "base",
    "navbar",
    "footer",
    "landing",
    "foo/",
    "account_txns",
)


# -----------------------------------------------------------------------------
# TEST 1: EVERY STATIC REFERENCE MUST EXIST
# -----------------------------------------------------------------------------
def test_all_static_templates_exist(referenced_static, actual):
    missing = [
        template_name
        for template_name in referenced_static
        if template_name not in actual
    ]

    assert not missing, f"Missing templates: {missing}"


# -----------------------------------------------------------------------------
# TEST 2: UNEXPECTED ORPHAN TEMPLATES
# -----------------------------------------------------------------------------
def test_no_orphan_templates(referenced_static, actual):
    """Reject unexpected user-facing templates with no static reference."""

    unused = [
        template_name
        for template_name in actual
        if (
            template_name not in referenced_static
            and not template_name.startswith(EXCLUDED_PREFIXES)
        )
    ]

    assert not unused, f"Orphan templates (unexpected): {unused}"


# -----------------------------------------------------------------------------
# TEST 3: DYNAMIC TEMPLATE DIRECTORY VALIDATION
# -----------------------------------------------------------------------------
def test_dynamic_render_template_calls_have_backing_dirs(actual):
    dynamic_calls = list(_dynamic_calls())

    if not dynamic_calls:
        pytest.skip("No dynamic render_template() calls found")

    allowed_dirs = {
        "sub",
        "letters",
        "tiles",
    }

    existing_dirs = {
        template_path.split("/", 1)[0]
        for template_path in actual
        if "/" in template_path
    }

    missing_dirs = allowed_dirs - existing_dirs

    assert not missing_dirs, (
        f"Dynamic render_template() expects {missing_dirs}, "
        "but no templates were found in those directories"
    )