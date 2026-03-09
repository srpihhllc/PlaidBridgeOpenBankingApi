# FILE: app/security/isolation.py

from flask_jwt_extended import get_jwt_identity

from app.models.user import User


class IsolationError(Exception):
    pass


def assert_lender_context() -> User:
    """
    Ensures the current JWT belongs to a lender-type user,
    not a subscriber. Raises IsolationError if violated.
    """
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if not user:
        raise IsolationError("No user found for current token.")

    # You can refine this to check a dedicated lender flag/role
    if getattr(user, "role", None) == "subscriber":
        raise IsolationError("Subscriber context may not access lender sandbox APIs.")

    return user
