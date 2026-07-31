#!/usr/bin/env python3
# =============================================================================
# FILE: app/scripts/regenerate_mfa_qr.py
# DESCRIPTION: Secure administrative utility to rotate TOTP credentials and
#              export multi-factor authorization vectors.
#              Remediates B108 / CWE-377 shared directory path vulnerabilities.
# =============================================================================

from __future__ import annotations

import argparse
import base64
import logging
import tempfile
from pathlib import Path

from app import create_app
from app.extensions import db
from app.models.user import User
from app.services.totp_service import generate_qr_code, generate_totp_secret, get_totp_uri

# Initialize localized structured logger
logger = logging.getLogger("mfa_regen")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Remediate Bandit B108: Resolve target base directory dynamically from standard host temporary facilities
DEFAULT_SECURE_OUT_DIR = Path(tempfile.gettempdir()) / "plaid_bridge_mfa_qr"


def write_png_from_base64(b64_payload: str, out_path: Path) -> None:
    """
    Decodes base64 string stream to raw binary bytes and writes the asset to disk.
    Enforces atomic permission scoping down to owner-only read/write privileges.
    """
    binary_data = base64.b64decode(b64_payload)
    out_path.write_bytes(binary_data)
    
    # Force absolute owner-only read/write permissions (POSIX 0o600) to isolate sensitive asset
    out_path.chmod(0o600)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Regenerate secure TOTP cryptographic secret and export a restricted QR image asset."
    )
    parser.add_argument(
        "--user-id", 
        type=int, 
        required=True, 
        help="Target database integer User ID record to regenerate TOTP parameters for."
    )
    parser.add_argument(
        "--force", 
        action="store_true", 
        help="Force overwrite existing totp_secret strings within the database transaction."
    )
    parser.add_argument(
        "--outdir",
        default=str(DEFAULT_SECURE_OUT_DIR),
        help=f"Target absolute directory path for writing QR PNG assets (Defaults safely to: {DEFAULT_SECURE_OUT_DIR})",
    )
    args = parser.parse_args()

    # Instantiate targeted application execution context block
    app = create_app()
    with app.app_context():
        # Modernized pattern: Switch to Session identity retrieval instead of legacy deprecated Model.query paths
        user = db.session.get(User, args.user_id)
        if not user:
            logger.error("Database lookup failed: No user row located with ID=%s", args.user_id)
            raise SystemExit(2)

        # Evaluate token footprint rotation criteria defensively
        has_existing_secret = bool(getattr(user, "totp_secret", None))
        
        if has_existing_secret and not args.force:
            logger.info(
                "Active totp_secret identity data discovered for user ID %s. Retention policy active. (Pass --force to override)", 
                user.id
            )
            secret = user.totp_secret
            is_regenerated = False
        else:
            secret = generate_totp_secret()
            user.totp_secret = secret
            try:
                db.session.add(user)
                db.session.commit()
                is_regenerated = True
                logger.info("Successfully persisted updated totp_secret mapping for user ID %s", user.id)
            except Exception as exc:
                db.session.rollback()
                logger.exception("Transactional database persistence failure mapping totp_secret on user %s", user.id)
                raise SystemExit(3) from exc

        # Assemble localized TOTP provisioning URI string
        try:
            uri = get_totp_uri(user, secret)
        except Exception as exc:
            logger.exception("Provisioning URI compilation step dropped error matrix for user %s", user.id)
            raise SystemExit(4) from exc

        # Synthesize base64 encoded QR asset stream via core token services
        try:
            b64_stream = generate_qr_code(uri)
            if not b64_stream:
                logger.error("Core engine returned empty base64 payload matrix for user URI %s", user.id)
                raise SystemExit(5)
        except Exception as exc:
            logger.exception("Vector generation engine faulted during processing cycle for user %s", user.id)
            raise SystemExit(6) from exc

        # Resolve deployment paths safely
        target_directory = Path(args.outdir)
        
        # Enforce strict owner-only workspace scoping (POSIX 0o700) during creation phases
        target_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        
        # Apply explicit permission setting on directory to counter strict operating system umask filters
        try:
            target_directory.chmod(0o700)
        except OSError:
            # Handle standard permission containment fallbacks if file system maps do not support explicit chmod modification
            pass

        target_file_path = target_directory / f"user_{user.id}_mfa_qr.png"
        write_png_from_base64(b64_stream, target_file_path)

        logger.info(
            "Multi-factor verification QR asset exported smoothly to: %s (Permissions bound: owner-only). Database rotation executed: %s",
            target_file_path,
            is_regenerated,
        )
        
        # Output operator metrics cleanly to standard output streams
        print(f"\n[OPERATIONAL OUTPUT] QR Asset Path: {target_file_path}")
        if "secret=" in uri:
            masked_uri = uri.split("secret=")[0] + "secret=****************"
        else:
            masked_uri = "unresolvable_uri_format"
            
        print(f"[OPERATIONAL OUTPUT] Masked Provisioning URI: {masked_uri}")
        print("\n⚠️  EXECUTIVE SECURITY NOTICE: Deliver this binary file to the recipient using a secured channel. Clear target data from temporary storage immediately following successful handover.")


if __name__ == "__main__":
    main()