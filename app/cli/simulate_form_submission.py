# app/cli/simulate_form_submission.py
from your_app import db

from app.models.form_submission import FormSubmission


def run():
    test_submission = FormSubmission(
        name="Synthetic Operator",
        email="synthetic@cockpit.ai",
        message="Test insert via CLI simulation",
    )
    db.session.add(test_submission)
    db.session.commit()
    print("[✔] Synthetic form submission saved.")
