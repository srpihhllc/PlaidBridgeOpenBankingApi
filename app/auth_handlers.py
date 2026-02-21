# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/auth_handlers.py

from flask import current_app

from app.extensions import login_manager
from app.models import User


# -------------------------------------------------------------------
# 🔑 1. user_loader: For Session/Cookie Authentication (UI only)
# -------------------------------------------------------------------
@login_manager.user_loader
def load_user(user_id: str):
    """
    Load a User object based on the user ID stored in the session cookie.
    Used exclusively for UI authentication (Flask-Login).
    """
    try:
        return User.query.get(int(user_id))
    except Exception as e:
        current_app.logger.debug(f"Could not load session user ID {user_id}. Error: {e}")
        return None


# -------------------------------------------------------------------
# ❌ Removed request_loader
# API authentication is handled by Flask-JWT-Extended, not Flask-Login.
# -------------------------------------------------------------------
