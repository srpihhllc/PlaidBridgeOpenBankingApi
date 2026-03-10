#!/usr/bin/env python3
"""
Byte-safe patch for auth_routes.py.

Replaces the redirect on invalid login:
    return redirect(url_for("auth.login"))
with a re-render:
    return render_template("auth/login.html")

This script writes a .bak backup the first time it runs.
It searches for CRLF and LF variants and applies a conservative
byte-level replacement (so encoding/newline differences are handled).
"""

from pathlib import Path
import sys

# Target file (relative to repository root)
TARGET = Path("PlaidBridgeOpenBankingApi") / "app" / "blueprints" / "auth_routes.py"


def main() -> int:
    if not TARGET.exists():
        print("ERROR: file not found:", TARGET)
        return 1

    # Backup (preserve original bytes/encoding)
    bak = TARGET.with_suffix(TARGET.suffix + ".bak")
    if not bak.exists():
        bak.write_bytes(TARGET.read_bytes())
        print("Backup written to:", bak)

    b = TARGET.read_bytes()

    # Byte patterns to search/replace (kept line-length friendly)
    old_bytes = (
        b'flash("Invalid email or password.", "danger")\r\n'
        b'        return redirect(url_for("auth.login"))'
    )
    old_bytes_nolf = (
        b'flash("Invalid email or password.", "danger")\n'
        b'        return redirect(url_for("auth.login"))'
    )

    new_bytes = (
        b'flash("Invalid email or password.", "danger")\r\n'
        b'        # Re-render login form (status 200)\r\n'
        b'        return render_template("auth/login.html")'
    )
    new_bytes_nolf = (
        b'flash("Invalid email or password.", "danger")\n'
        b'        # Re-render login form (status 200)\n'
        b'        return render_template("auth/login.html")'
    )

    # Fallback patterns that replace only the redirect line
    redirect_old_crlf = b'\r\n        return redirect(url_for("auth.login"))'
    redirect_old_nolf = b'\n        return redirect(url_for("auth.login"))'
    redirect_new_crlf = (
        b'\r\n        # Re-render login form (status 200)\r\n'
        b'        return render_template("auth/login.html")'
    )
    redirect_new_nolf = (
        b'\n        # Re-render login form (status 200)\n'
        b'        return render_template("auth/login.html")'
    )

    # Apply replacements with a clear, single-pass priority
    if old_bytes in b:
        b2 = b.replace(old_bytes, new_bytes, 1)
        TARGET.write_bytes(b2)
        print("Patch applied (CRLF variant).")
        return 0

    if old_bytes_nolf in b:
        b2 = b.replace(old_bytes_nolf, new_bytes_nolf, 1)
        TARGET.write_bytes(b2)
        print("Patch applied (LF variant).")
        return 0

    # Conservative fallback: replace only the redirect line if present
    if redirect_old_crlf in b:
        b2 = b.replace(redirect_old_crlf, redirect_new_crlf, 1)
        TARGET.write_bytes(b2)
        print("Patch applied (redirect-only CRLF fallback).")
        return 0

    if redirect_old_nolf in b:
        b2 = b.replace(redirect_old_nolf, redirect_new_nolf, 1)
        TARGET.write_bytes(b2)
        print("Patch applied (redirect-only LF fallback).")
        return 0

    # If nothing matched, print a concise manual instruction and fail.
    print("Pattern not found. File may differ from expected.")
    print()
    print("Open the file and apply the following block immediately after the flash():")
    print()
    print("    # Re-render the login form (status 200).")
    print("    return render_template(\"auth/login.html\")")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
