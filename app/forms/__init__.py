# =============================================================================
# FILE: app/forms/__init__.py
# DESCRIPTION: Central export hub for all WTForms used across the app.
# =============================================================================

from .account_forms import AccountUpdateForm
from .auth_forms import LoginForm, RegistrationForm
from .mfa_forms import MFAEnableForm, MFAForm
from .password_forms import ChangePasswordForm, PasswordResetForm, PasswordResetRequestForm
from .pii_forms import PIIRequestForm

__all__ = [
    "LoginForm",
    "RegistrationForm",
    "MFAForm",
    "MFAEnableForm",
    "PasswordResetRequestForm",
    "PasswordResetForm",
    "ChangePasswordForm",
    "AccountUpdateForm",
    "PIIRequestForm",
]
