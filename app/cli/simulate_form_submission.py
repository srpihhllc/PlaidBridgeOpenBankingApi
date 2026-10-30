# =============================================================================
# FILE: app/cli/simulate_form_submission.py
# DESCRIPTION: CLI command to simulate a multi-tenant synthetic form submission.
# =============================================================================

from importlib import import_module
from typing import Any

import click
from flask.cli import with_appcontext

from app.extensions import db


def _load_form_submission_model() -> Any | None:
    """Load FormSubmission from supported model locations, if available."""
    for module_name in ("app.models.form_submission", "app.models"):
        try:
            module = import_module(module_name)
        except ImportError:
            continue

        model = getattr(module, "FormSubmission", None)
        if model is not None:
            return model

    return None


FormSubmission = _load_form_submission_model()


@click.command("simulate_form_submission")
@with_appcontext
def simulate_form_submission_command() -> None:
    """Run a synthetic form submission save simulation."""
    if FormSubmission is None:
        click.secho(
            "FormSubmission model not found on this branch. "
            "Skipping simulation.",
            fg="yellow",
        )
        return

    try:
        test_submission = FormSubmission(
            name="Synthetic Operator",
            email="synthetic@cockpit.ai",
            message="Test insert via CLI simulation",
        )
        db.session.add(test_submission)
        db.session.commit()
        click.secho("[✔] Synthetic form submission saved.", fg="green")
    except Exception as e:
        db.session.rollback()
        click.secho(f"Execution failed: {e}", fg="red", err=True)