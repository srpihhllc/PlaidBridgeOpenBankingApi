# /home/srpihhllc/PlaidBridgeOpenBankingApi/migrations/env.py

"""
Alembic env.py - canonical import of Flask app and models.

Goals:
- Ensure a single canonical import root (repo root) is used in CI.
- Find/create the Flask app via a small set of likely module paths.
- Import app.models exactly once inside app.app_context() so SQLAlchemy
  registers mapped classes only once.
- Use db from app.extensions as the canonical SQLAlchemy extension object.
"""

from __future__ import annotations
import importlib
import os
import sys
from configparser import ConfigParser
from logging.config import fileConfig
from urllib.parse import urlparse, urlunparse

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine, pool

# -------------------------
# Guard for pytest / non-alembic contexts (keeps tests from importing this)
# -------------------------
_IS_PYTEST = "PYTEST_CURRENT_TEST" in os.environ or "pytest" in sys.modules
_CONTEXT_OK = hasattr(context, "config") and hasattr(context, "is_offline_mode")
if _IS_PYTEST or not _CONTEXT_OK:
    print("NOTE: Skipping Alembic env bootstrap (pytest or invalid alembic context).")
    _SKIP_ALEMBIC = True
else:
    _SKIP_ALEMBIC = False

# -------------------------
# Path / env bootstrapping (only when not skipping)
# -------------------------
if not _SKIP_ALEMBIC:
    HERE = os.path.dirname(os.path.abspath(__file__))
    # migrations/ sits at PROJECT_ROOT/migrations — canonical repo root:
    PROJECT_ROOT = os.path.abspath(os.path.join(HERE, ".."))
    # ensure canonical project root is first on sys.path
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

    # Load .env if present
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

    # Debug: print simplest path info to help CI traces (won't expose secrets)
    print(f"[alembic.env] PROJECT_ROOT={PROJECT_ROOT}")
    print(f"[alembic.env] sys.path[0:4]={sys.path[:4]}")

    # -----------------------------------------------------------------
    # Import the Flask app factory from a small set of canonical locations.
    # This avoids importing the package under multiple names in CI.
    # -----------------------------------------------------------------
    def _import_create_app():
        candidates = [
            ("PlaidBridgeOpenBankingApi.app", "create_app"),
            ("PlaidBridgeOpenBankingApi.flask_app", "create_app"),
            ("flask_app", "create_app"),
            ("app.flask_app", "create_app"),
        ]
        for modname, attr in candidates:
            try:
                mod = __import__(modname, fromlist=[attr])
                create_app = getattr(mod, attr, None)
                if callable(create_app):
                    print(f"[alembic.env] using create_app from {modname}.{attr}")
                    return create_app
            except Exception as exc:
                # Not fatal; try next
                print(f"[alembic.env] candidate {modname} import failed: {type(exc).__name__}")
                continue
        # last-resort: app.create_app
        try:
            mod = __import__("app", fromlist=["create_app"])
            create_app = getattr(mod, "create_app", None)
            if callable(create_app):
                print("[alembic.env] using create_app from app.create_app")
                return create_app
        except Exception as exc:
            print(f"[alembic.env] fallback app.create_app import failed: {type(exc).__name__}")
        raise ImportError(
            "Could not find create_app callable. Tried flask_app, app.flask_app, "
            "PlaidBridgeOpenBankingApi.flask_app, and app.create_app."
        )

    create_app = _import_create_app()
    create_app_module = create_app.__module__
    app_package = create_app_module.rsplit(".", 1)[0]

    # CRITICAL: Alias "app" and all submodules to the canonical package root.
    # This prevents SQLAlchemy from seeing "app.models.user" and "PlaidBridgeOpenBankingApi.app.models.user"
    # as different modules, which would cause duplicate table registration.
    try:
        canonical_app_pkg = importlib.import_module(app_package)
        sys.modules["app"] = canonical_app_pkg
        
        # Pre-import and alias critical submodules before app creation
        # This ensures any subsequent "from app.models import X" will use the already-loaded module
        submodules_to_alias = [
            "extensions", "models", "utils", "config", "services", 
            "cli", "blueprints", "routes", "api", "forms", "views"
        ]
        for submod in submodules_to_alias:
            try:
                full_name = f"{app_package}.{submod}"
                alias_name = f"app.{submod}"
                mod = importlib.import_module(full_name)
                sys.modules[alias_name] = mod
                print(f"[alembic.env] aliased {alias_name} -> {full_name}")
            except ImportError:
                pass  # submodule might not exist
        
        print(f"[alembic.env] canonical package: {app_package}, aliased as 'app'")
    except Exception as exc:
        print(f"[alembic.env] canonical app alias setup failed: {type(exc).__name__}: {exc}")
        raise

    FLASK_ENV = os.environ.get("FLASK_ENV", "testing")
    # support factory signature create_app(env_name=...) or simple create_app()
    try:
        app = create_app(env_name=FLASK_ENV) if "env_name" in create_app.__code__.co_varnames else create_app()
    except Exception as exc:
        print(f"[alembic.env] create_app() raised: {type(exc).__name__}: {exc}")
        raise

    # Use the app context to import extensions and register models exactly once.
    with app.app_context():
        # Import db and models from the same package root as create_app.
        try:
            extensions_mod = importlib.import_module(f"{app_package}.extensions")
            db = getattr(extensions_mod, "db")
            print(f"[alembic.env] using db from {app_package}.extensions")
        except Exception as exc:
            print(
                f"[alembic.env] import {app_package}.extensions.db failed: {type(exc).__name__}; trying app.db fallback"
            )
            try:
                from app import db  # noqa: E402
            except Exception:
                raise

        # Import canonical models package once for mapper registration.
        try:
            models_mod = importlib.import_module(f"{app_package}.models")
            print(f"[alembic.env] imported models from {app_package}.models")
            
            # Alias all individual model modules that were loaded
            # (e.g., PlaidBridgeOpenBankingApi.app.models.user -> app.models.user)
            model_prefix = f"{app_package}.models."
            for mod_name in list(sys.modules.keys()):
                if mod_name.startswith(model_prefix):
                    submodule_name = mod_name[len(f"{app_package}.models."):]
                    alias_name = f"app.models.{submodule_name}"
                    if alias_name not in sys.modules:
                        sys.modules[alias_name] = sys.modules[mod_name]
                        
            print(f"[alembic.env] aliased {len([k for k in sys.modules if k.startswith('app.models.')])} model submodules")
        except Exception as exc:
            print(f"[alembic.env] importing {app_package}.models failed: {type(exc).__name__}")
            raise

        target_metadata = db.metadata

# -------------------------
# Configure Alembic (logging)
# -------------------------
config = context.config
if config.config_file_name:
    # Disable interpolation to avoid issues with passwords that contain '%' characters
    parser = ConfigParser(interpolation=None)
    parser.read(config.config_file_name)
    config.file_config = parser

if config.config_file_name and os.path.exists(config.config_file_name):
    fileConfig(config.config_file_name)

# -------------------------
# Migration routines
# -------------------------
def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        url = app.config.get("SQLALCHEMY_DATABASE_URI") or os.environ.get("DATABASE_URL")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    # Prefer engine from the app's db extension
    try:
        connectable = db.engine
    except Exception:
        url = config.get_main_option("sqlalchemy.url") or app.config.get("SQLALCHEMY_DATABASE_URI") or os.environ.get("DATABASE_URL")
        # debug
        print(f"[alembic.env] using URL: {url}")
        connectable = create_engine(url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


# -------------------------
# Entrypoint
# -------------------------
if not _SKIP_ALEMBIC:
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        run_migrations_online()
