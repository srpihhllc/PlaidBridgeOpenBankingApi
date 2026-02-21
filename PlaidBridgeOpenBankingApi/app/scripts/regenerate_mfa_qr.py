# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/scripts/regenerate_mfa_qr.py

#!/usr/bin/env python3
"""
Regenerate TOTP secret + QR for a single user and write PNG to /tmp for operator handoff.

Usage (example):
  # If your app exposes create_app():
  FLASK_APP=app:create_app PYTHONPATH=. python scripts/regenerate_mfa_qr.py --user-id 42

  # Or from a flask shell context where create_app is importable:
  python scripts/regenerate_mfa_qr.py --user-id 42
"""

import argparse
import base64
import logging
from pathlib import Path

# Adjust imports to match your app factory location
from app import create_app  # or from yourproject import create_app
from app.extensions import db
from app.models.user import User
from app.services.totp_service import generate_qr_code, generate_totp_secret, get_totp_uri

logger = logging.getLogger("mfa_regen")
logging.basicConfig(level=logging.INFO)

OUT_DIR = Path("/tmp")
OUT_DIR.mkdir(mode=0o700, exist_ok=True)


def write_png_from_base64(b64: str, out_path: Path):
    b = base64.b64decode(b64)
    out_path.write_bytes(b)
    # restrict permissions to operator only
    out_path.chmod(0o600)


def main():
    p = argparse.ArgumentParser(description="Regenerate TOTP secret + QR for a user")
    p.add_argument("--user-id", type=int, required=True, help="User ID to regenerate TOTP for")
    p.add_argument("--force", action="store_true", help="Overwrite existing totp_secret in DB")
    p.add_argument(
        "--outdir",
        default=str(OUT_DIR),
        help="Directory to write QR PNG (default /tmp)",
    )
    args = p.parse_args()

    app = create_app()
    with app.app_context():
        user = User.query.get(args.user_id)
        if not user:
            logger.error("No user found with id=%s", args.user_id)
            raise SystemExit(2)

        # Decide whether to create a new secret
        if getattr(user, "totp_secret", None) and not args.force:
            logger.info(
                "User already has totp_secret; using existing secret (use --force to regenerate)."
            )
            secret = user.totp_secret
            regenerated = False
        else:
            secret = generate_totp_secret()
            user.totp_secret = secret
            try:
                db.session.add(user)
                db.session.commit()
            except Exception as exc:
                db.session.rollback()
                logger.exception("Failed to persist new totp_secret for user %s", user.id)
                raise SystemExit(3) from exc
            regenerated = True
            logger.info("Persisted new totp_secret for user %s", user.id)

        # Build URI and QR
        try:
            uri = get_totp_uri(user, secret)
        except Exception as exc:
            logger.exception("get_totp_uri failed for user %s", user.id)
            raise SystemExit(4) from exc

        try:
            b64 = generate_qr_code(uri)
            if not b64:
                logger.error("generate_qr_code returned empty value for user %s", user.id)
                raise SystemExit(5)
        except Exception as exc:
            logger.exception("generate_qr_code failed for user %s", user.id)
            raise SystemExit(6) from exc

        outdir = Path(args.outdir)
        outdir.mkdir(parents=True, exist_ok=True, mode=0o700)
        outfile = outdir / f"user_{user.id}_mfa_qr.png"
        write_png_from_base64(b64, outfile)

        logger.info(
            "QR written to %s (owner-only perms). Secret persisted: %s",
            outfile,
            regenerated,
        )
        # Print a short operator-friendly summary (no secret)
        print("QR file:", str(outfile))
        print(
            "TOTP provisioning URI (masked):",
            (
                (uri.split("secret=")[0] + "secret=***")
                if "secret=" in uri
                else "masked_uri_unavailable"
            ),
        )
        print("Deliver the QR PNG to the user securely and delete the file after handoff.")

        # Optional: print raw secret only if operator explicitly requested (avoid by default)
        # print("Secret (RAW):", secret)  # avoid printing by default


if __name__ == "__main__":
    main()
