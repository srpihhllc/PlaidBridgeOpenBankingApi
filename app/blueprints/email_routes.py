# app/blueprints/email_routes.py

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_mail import Message

from app.extensions import mail


email_bp = Blueprint("email", __name__)


@email_bp.route("/send-test-email")
def send_test_email():
    """Send a test email and redirect to the test-email page."""
    try:
        message = Message(
            subject="Hello from Flask!",
            recipients=["srpollardsihhllc@gmail.com"],
            body="This is a test email sent from your Flask application.",
        )

        mail.send(message)
        flash("Test email sent successfully!", "success")
    except Exception as exc:
        flash(f"Failed to send email: {exc}", "error")

    return redirect(url_for("email.test_email_page"))


@email_bp.route("/test-email-page")
def test_email_page():
    """Render the test-email page."""
    return render_template("test_email.html")