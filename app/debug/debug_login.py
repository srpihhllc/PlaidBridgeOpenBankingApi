# debug/app/debug/debug_login.py
#!/usr/bin/env python3
"""
Debug helper to check which config is used and to POST to login endpoints.
Put this at app/debug/debug_login.py and run from the repo root:
  python app/debug/debug_login.py | tee /tmp/debug_login.out
"""

import os
import sys

# Ensure tests/config selection picks testing by default
os.environ.setdefault("FLASK_ENV", "testing")

# Make repo root and common subpackage paths importable
repo_root = os.getcwd()
candidates = [
    repo_root,
    os.path.join(repo_root, "PlaidBridgeOpenBankingApi"),
    os.path.join(repo_root),
]
# Prepend candidates to sys.path if not already present
for p in candidates:
    if p and p not in sys.path:
        sys.path.insert(0, p)

create_app = None
tried = []
for mod in ("flask_app", "app", "PlaidBridgeOpenBankingApi"):
    try:
        m = __import__(mod, fromlist=["create_app"])
        create_app = getattr(m, "create_app")
        tried.append(mod)
        break
    except Exception as e:
        tried.append(f"{mod} (err: {e!r})")

if create_app is None:
    print("ERROR: couldn't import create_app. Tried:", tried, file=sys.stderr)
    print("sys.path (first 10):", sys.path[:10], file=sys.stderr)
    sys.exit(2)

# Instantiate the app using the typical signature if available
try:
    app = create_app()
except TypeError:
    # If the factory requires an argument, pass None
    app = create_app(None)

print("APP FACTORY IMPORT OK")
print("Tried imports:", tried)
print("App config summary:")
print("  TESTING =", app.config.get("TESTING"))
print("  WTF_CSRF_ENABLED =", app.config.get("WTF_CSRF_ENABLED"))
print("  REDIS_URL =", app.config.get("REDIS_URL"))
print("  RATELIMIT_ENABLED =", app.config.get("RATELIMIT_ENABLED"))
print()

client = app.test_client()

tests = [
    ("/auth/login", {"email": "bad@x.com", "password": "wrong"}),
    ("/login", {"email": "bad@x.com", "password": "wrong"}),
]

for path, data in tests:
    print("---- POST", path, "----")
    resp = client.post(path, data=data, follow_redirects=False)
    print("status:", resp.status_code)
    print("location header:", resp.headers.get("Location"))
    # safe body excerpt
    try:
        body = resp.get_data(as_text=True)
    except Exception:
        body = repr(resp.get_data())
    excerpt = body[:800].replace("\n", "\\n")
    print("body excerpt (first 800 chars):")
    print(excerpt)
    print()
