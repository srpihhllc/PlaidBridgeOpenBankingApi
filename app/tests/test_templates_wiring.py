# =============================================================================
# FILE: app/tests/test_templates_wiring.py
# DESCRIPTION: Ensures every render_template() call references a real template
#              and that no orphan templates exist. Handles dynamic calls too.
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


def _referenced_static_templates():
    for pyfile in PROJECT_ROOT.rglob("*.py"):
        text = pyfile.read_text(encoding="utf-8", errors="ignore")
        yield from STATIC_RE.findall(text)


def _dynamic_calls():
    for pyfile in PROJECT_ROOT.rglob("*.py"):
        text = pyfile.read_text(encoding="utf-8", errors="ignore")
        for match in DYNAMIC_RE.findall(text):
            yield pyfile, match


def _actual_templates():
    for tpl in TEMPLATES_DIR.rglob("*.html"):
        yield str(tpl.relative_to(TEMPLATES_DIR))


@pytest.fixture(scope="session")
def referenced_static():
    return sorted(set(_referenced_static_templates()))


@pytest.fixture(scope="session")
def actual():
    return sorted(set(_actual_templates()))


def test_all_static_templates_exist(referenced_static, actual):
    """Every template referenced in render_template() must exist on disk."""
    missing = [tpl for tpl in referenced_static if tpl not in actual]
    assert not missing, f"❌ Missing templates: {missing}"


def test_no_orphan_templates(referenced_static, actual):
    """Every template on disk must be referenced somewhere (strict mode)."""
    unused = [tpl for tpl in actual if tpl not in referenced_static]
    assert not unused, f"❌ Orphan templates (exist but not referenced): {unused}"


def test_dynamic_render_template_calls_have_backing_dirs(actual):
    """
    For dynamic render_template(tpl) calls, assert that the directories
    they are expected to pull from actually contain templates.
    """
    dynamic = list(_dynamic_calls())
    if not dynamic:
        pytest.skip("No dynamic render_template() calls found")

    # Define directories we expect dynamic calls to use
    allowed_dirs = {"sub", "letters", "tiles"}
    existing_dirs = {path.split("/")[0] for path in actual}

    missing_dirs = allowed_dirs - existing_dirs
    assert not missing_dirs, (
        f"❌ Dynamic render_template() expects {missing_dirs}, " f"but no templates found there"
    )
