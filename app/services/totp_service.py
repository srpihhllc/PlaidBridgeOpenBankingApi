# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/services/totp_service.py

import base64
import io

import pyotp
import qrcode
from flask import current_app


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def get_totp_uri(user, secret) -> str:
    """
    Build the otpauth URI for QR provisioning.
    Issuer name is configurable via Flask config: TOTP_ISSUER_NAME.
    """
    issuer = current_app.config.get("TOTP_ISSUER_NAME", "PlaidBridgeCockpit")
    return pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name=issuer)


def generate_qr_code(uri: str) -> str:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H)
    qr.add_data(uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def verify_totp_code(secret: str, submitted_code: str) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(submitted_code, valid_window=1)  # allow ±30s drift
