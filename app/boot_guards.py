# app/boot_guards.py

from flask import current_app
from jinja2 import TemplateNotFound

REQUIRED_TEMPLATES = [
    "login.html",
    "login_subscriber.html",
    "register.html",
    "register_subscriber.html",
    "forgot_password.html",
    "reset_password.html",
    "me.html",
]


def verify_templates():
    env = current_app.jinja_env
    missing = []
    for t in REQUIRED_TEMPLATES:
        try:
            env.get_or_select_template(t)
        except TemplateNotFound:
            missing.append(t)
    if missing:
        # Emit cockpit trace so operator sees exactly what's missing
        current_app.logger.error(f"Missing required templates: {missing}")
