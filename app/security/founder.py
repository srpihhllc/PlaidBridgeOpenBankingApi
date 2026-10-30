# app/security/founder.py

import os
from typing import Any


def is_founder(user: Any) -> bool:
    """
    Single source of truth for founder/root authority.
    """

    if not user:
        return False

    role = str(
        getattr(user, "role", "") or ""
    ).strip().lower()

    founder_roles = {
        "founder",
        "creator",
        "owner",
        "super_admin",
    }

    if role in founder_roles:
        return True

    creator_email = (
        os.getenv("CREATOR_EMAIL", "")
        .strip()
        .lower()
    )

    creator_username = (
        os.getenv("CREATOR_USERNAME", "")
        .strip()
        .lower()
    )

    user_email = (
        str(
            getattr(user, "email", "") or ""
        )
        .strip()
        .lower()
    )

    user_username = (
        str(
            getattr(user, "username", "") or ""
        )
        .strip()
        .lower()
    )

    if creator_email and user_email == creator_email:
        return True

    if creator_username and user_username == creator_username:
        return True

    return False


def is_creator(user: Any) -> bool:
    return is_founder(user)


def is_owner(user: Any) -> bool:
    return is_founder(user)


def is_platform_owner(user: Any) -> bool:
    return is_founder(user)