# app/letters/dispatcher.py

"""
Handles the delivery of rendered dispute letters to their respective bureaus.
Supports local storage and optional email dispatch via SendGrid.
"""

import os
from datetime import datetime

import sendgrid
from sendgrid.helpers.mail import Mail


def dispatch_letter(
    rendered_letter: str,
    bureau: dict,
    user: dict | None = None,
) -> str:
    """
    Dispatch the rendered letter to the target bureau by saving to disk and emailing if configured.
    """

    # Normalize user so mypy never sees None later
    user = user or {}

    delivery_method = bureau.get("delivery_method", "print")
    slug = bureau["name"].lower().replace(" ", "_")
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    # 📁 Save a local copy
    save_dir = os.path.join("generated_letters", slug)
    os.makedirs(save_dir, exist_ok=True)
    filename = f"{timestamp}_{slug}_dispute.txt"
    full_path = os.path.join(save_dir, filename)

    with open(full_path, "w", encoding="utf-8") as f:
        f.write(rendered_letter)

    # 📨 Attempt email delivery via SendGrid
    if delivery_method == "email" and bureau.get("contact_email"):
        sg = sendgrid.SendGridAPIClient(api_key=os.getenv("SENDGRID_API_KEY"))
        message = Mail(
            from_email="disputes@yourdomain.com",
            to_emails=bureau["contact_email"],
            subject=f"Formal Dispute from {user.get('name', 'Consumer')}",
            plain_text_content=rendered_letter,
        )
        try:
            sg.send(message)
            return "email"
        except Exception as e:
            print(f"[SENDGRID ERROR] Failed to deliver to {bureau['name']}: {e}")
            return "email_failed"

    return "print"
