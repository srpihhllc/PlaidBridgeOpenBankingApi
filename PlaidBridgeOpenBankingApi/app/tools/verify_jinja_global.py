# Verification helper: quick script to ensure create_app exposes jinja 'app' global.
# Usage (from repo root):
#   PYTHONPATH=PlaidBridgeOpenBankingApi python tools/verify_jinja_global.py

from importlib import import_module, reload
import sys
sys.path.insert(0, "PlaidBridgeOpenBankingApi")

from app import create_app

app = create_app("development")
print("Has jinja_env 'app' global?:", "app" in app.jinja_env.globals)
print("Sample endpoints count:", len(list(app.url_map.iter_rules())))
