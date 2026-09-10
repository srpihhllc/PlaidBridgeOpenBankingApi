# =============================================================================
# FILE: app/cli/simulate_form_submission.py
# DESCRIPTION: CLI command to simulate a multi-tenant synthetic form submission.
# =============================================================================

import click
from flask.cli import with_appcontext

from app.extensions import db

# Dynamic import fallback to accommodate active branch structures
try:
    from app.models.form_submission import FormSubmission
except ImportError:
    try:
        from app.models import FormSubmission
    except ImportError:
        FormSubmission = None


@click.command("simulate_form_submission")
@with_appcontext
def simulate_form_submission_command():
    """Run a synthetic form submission save simulation."""
    if FormSubmission is None:
        click.secho(
            "⚠️ FormSubmission model not found on this branch. Skipping simulation.",
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
        click.secho(f"❌ Execution failed: {str(e)}", fg="red", err=True)
