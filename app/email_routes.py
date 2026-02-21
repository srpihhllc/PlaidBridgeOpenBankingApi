# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/email_routes.py

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_mail import Message

from app.extensions import mail

# Create a new blueprint for email-related routes
email_bp = Blueprint("email", __name__)


@email_bp.route("/send-test-email")
def send_test_email():
    """
    Route to send a test email.
    This demonstrates the basic usage of the Flask-Mail extension.
    """
    try:
        # Create the email message
        msg = Message(
            subject="Hello from Flask!",
            recipients=["your_email@example.com"],  # Replace with the recipient's email address
            body="This is a test email sent from your Flask application.",
        )

        # Send the email
        mail.send(msg)

        flash("Test email sent successfully!", "success")
    except Exception as e:
        flash(f"Failed to send email: {e}", "error")

    # Redirect to a page after sending the email.
    # You might want to create a dedicated page for this.
    return redirect(url_for("main.index"))


# Example of a page to trigger the email (optional, for testing)
@email_bp.route("/test-email-page")
def test_email_page():
    """
    A simple page with a button to trigger the test email.
    """
    return render_template("test_email.html")
