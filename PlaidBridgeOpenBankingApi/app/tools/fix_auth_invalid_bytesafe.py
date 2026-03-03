#!/usr/bin/env python3
# Byte-safe patch for auth_routes.py: replace 'return redirect(url_for("auth.login"))'
# with 'return render_template("auth/login.html")' in the invalid-credentials branch.
from pathlib import Path
p = Path("PlaidBridgeOpenBankingApi/app/blueprints/auth_routes.py")
if not p.exists():
    print("ERROR: file not found:", p)
    raise SystemExit(1)

# Backup (preserve original bytes/encoding)
bak = p.with_suffix(p.suffix + ".bak")
if not bak.exists():
    bak.write_bytes(p.read_bytes())
    print("Backup written to:", bak)

b = p.read_bytes()

# Byte patterns to search/replace
old_bytes = (
    b'flash("Invalid email or password.", "danger")\r\n        return redirect(url_for("auth.login"))'
)
old_bytes_nolf = (
    b'flash("Invalid email or password.", "danger")\n        return redirect(url_for("auth.login"))'
)
new_bytes = (
    b'flash("Invalid email or password.", "danger")\r\n        # Re-render login form (status 200)\r\n        return render_template("auth/login.html")'
)
new_bytes_nolf = (
    b'flash("Invalid email or password.", "danger")\n        # Re-render login form (status 200)\n        return render_template("auth/login.html")'
)

if old_bytes in b:
    b2 = b.replace(old_bytes, new_bytes, 1)
    p.write_bytes(b2)
    print("Patch applied (CRLF variant).")
elif old_bytes_nolf in b:
    b2 = b.replace(old_bytes_nolf, new_bytes_nolf, 1)
    p.write_bytes(b2)
    print("Patch applied (LF variant).")
else:
    # Not found — do a conservative fallback replace of just the redirect line only
    redirect_old_crlf = b'\r\n        return redirect(url_for("auth.login"))'
    redirect_old_nolf = b'\n        return redirect(url_for("auth.login"))'
    redirect_new_crlf = b'\r\n        # Re-render login form (status 200)\r\n        return render_template("auth/login.html")'
    redirect_new_nolf = b'\n        # Re-render login form (status 200)\n        return render_template("auth/login.html")'
    if redirect_old_crlf in b:
        b2 = b.replace(redirect_old_crlf, redirect_new_crlf, 1)
        p.write_bytes(b2)
        print("Patch applied (redirect-only CRLF fallback).")
    elif redirect_old_nolf in b:
        b2 = b.replace(redirect_old_nolf, redirect_new_nolf, 1)
        p.write_bytes(b2)
        print("Patch applied (redirect-only LF fallback).")
    else:
        print("Pattern not found. File may differ from expected. Open the file and apply the following block manually just after the flash():")
        print()
        print('    # Re-render the login form (status 200).')
        print('    return render_template("auth/login.html")')
        raise SystemExit(2)
