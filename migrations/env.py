# /home/srpihhllc/PlaidBridgeOpenBankingApi/migrations/env.py

"""
Alembic env.py - canonical import of Flask app and models.

Goals:
- Use a single canonical import root (PROJECT_ROOT) in all environments (local, CI, prod).
- Resolve the Flask app factory from a small, explicit set of module candidates.
- Register models exactly once via app.app_context(), using app.extensions.db as the source of truth.
- Avoid duplicate module imports (e.g., "app.models.user" vs "PlaidBridgeOpenBankingApi.app.models.user").
- Disable database reflection during migrations to avoid MySQL metadata bugs and ensure model-driven schema.
"""

from __future__ import annotations

import importlib
import os
import sys
from configparser import ConfigParser
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine, pool

# ---------------------------------------------------------------------------
# Guard for pytest / non-Alembic contexts
# ---------------------------------------------------------------------------

_IS_PYTEST = "PYTEST_CURRENT_TEST" in os.environ or "pytest" in sys.modules
_CONTEXT_OK = hasattr(context, "config") and hasattr(context, "is_offline_mode")

if _IS_PYTEST or not _CONTEXT_OK:
    print("NOTE: Skipping Alembic env bootstrap (pytest or invalid Alembic context).")
    _SKIP_ALEMBIC = True
else:
    _SKIP_ALEMBIC = False

# ---------------------------------------------------------------------------
# Path / environment bootstrapping
# ---------------------------------------------------------------------------

if not _SKIP_ALEMBIC:
    HERE = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.abspath(os.path.join(HERE, ".."))

    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)

    # Load .env from project root if present (no secrets printed)
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

    print(f"[alembic.env] PROJECT_ROOT={PROJECT_ROOT}")
    print(f"[alembic.env] sys.path[0:4]={sys.path[:4]}")

    # -----------------------------------------------------------------------
    # Resolve create_app from a small, explicit set of candidates
    # -----------------------------------------------------------------------
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
                print(f"[alembic.env] candidate {modname} import failed: {type(exc).__name__}")
                continue

        # Last-resort: app.create_app
        try:
            mod = __import__("app", fromlist=["create_app"])
            create_app = getattr(mod, "create_app", None)
            if callable(create_app):
                print("[alembic.env] using create_app from app.create_app")
                return create_app
        except Exception as exc:
            print(f"[alembic.env] fallback app.create_app import failed: {type(exc).__name__}")

        raise ImportError(
            "Could not find create_app callable. Tried: "
            "PlaidBridgeOpenBankingApi.app, PlaidBridgeOpenBankingApi.flask_app, "
            "flask_app, app.flask_app, and app.create_app."
        )

    create_app = _import_create_app()
    create_app_module = create_app.__module__
    app_package = create_app_module.rsplit(".", 1)[0]

    # -----------------------------------------------------------------------
    # Canonical aliasing: ensure 'app' points to the same package everywhere
    # -----------------------------------------------------------------------
    try:
        canonical_app_pkg = importlib.import_module(app_package)
        sys.modules["app"] = canonical_app_pkg

        # Pre-alias common submodules so "from app.X import Y" is stable
        submodules_to_alias = [
            "extensions",
            "models",
            "utils",
            "config",
            "services",
            "cli",
            "blueprints",
            "routes",
            "api",
            "forms",
            "views",
        ]
        for submod in submodules_to_alias:
            try:
                full_name = f"{app_package}.{submod}"
                alias_name = f"app.{submod}"
                mod = importlib.import_module(full_name)
                sys.modules[alias_name] = mod
                print(f"[alembic.env] aliased {alias_name} -> {full_name}")
            except ImportError:
                # Not all submodules are mandatory; skip quietly
                pass

        print(f"[alembic.env] canonical package: {app_package}, aliased as 'app'")
    except Exception as exc:
        print(f"[alembic.env] canonical app alias setup failed: {type(exc).__name__}: {exc}")
        raise

    # -----------------------------------------------------------------------
    # Create the Flask app and bind db/metadata
    # -----------------------------------------------------------------------
    FLASK_ENV = os.environ.get("FLASK_ENV", "testing")

    try:
        if "env_name" in create_app.__code__.co_varnames:
            app = create_app(env_name=FLASK_ENV)
        else:
            app = create_app()
    except Exception as exc:
        print(f"[alembic.env] create_app() raised: {type(exc).__name__}: {exc}")
        raise

    with app.app_context():
        # Prefer db from the same package root as create_app
        try:
            extensions_mod = importlib.import_module(f"{app_package}.extensions")
            db = getattr(extensions_mod, "db")
            print(f"[alembic.env] using db from {app_package}.extensions")
        except Exception as exc:
            print(
                f"[alembic.env] import {app_package}.extensions.db failed: {type(exc).__name__}; "
                "trying app.db fallback"
            )
            from app import db  # type: ignore  # noqa: E402

        # Import models once to register all mappers
        try:
            models_mod = importlib.import_module(f"{app_package}.models")
            print(f"[alembic.env] imported models from {app_package}.models")

            # Alias individual model submodules under app.models.*
            model_prefix = f"{app_package}.models."
            for mod_name in list(sys.modules.keys()):
                if mod_name.startswith(model_prefix):
                    submodule_name = mod_name[len(model_prefix) :]
                    alias_name = f"app.models.{submodule_name}"
                    if alias_name not in sys.modules:
                        sys.modules[alias_name] = sys.modules[mod_name]

            aliased_count = len([k for k in sys.modules if k.startswith("app.models.")])
            print(f"[alembic.env] aliased {aliased_count} model submodules")
        except Exception as exc:
            print(f"[alembic.env] importing {app_package}.models failed: {type(exc).__name__}")
            raise

        target_metadata = db.metadata
else:
    # When skipping Alembic (pytest, etc.), these are dummies to keep type checkers happy
    app = None
    db = None
    target_metadata = None

# ---------------------------------------------------------------------------
# Alembic config / logging
# ---------------------------------------------------------------------------

config = context.config

if config.config_file_name:
    parser = ConfigParser(interpolation=None)
    parser.read(config.config_file_name)
    config.file_config = parser

if config.config_file_name and os.path.exists(config.config_file_name):
    fileConfig(config.config_file_name)


# ---------------------------------------------------------------------------
# Common configure kwargs: NO DB REFLECTION
# ---------------------------------------------------------------------------

def _configure_kwargs_offline(url: str) -> dict:
    """
    Configuration for offline migrations (SQL script generation).
    Reflection is disabled; schema is driven purely from target_metadata.
    """
    return dict(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
        include_schemas=False,
        # Critical: do NOT include reflected DB objects; rely only on models.
        include_object=lambda obj, name, type_, reflected, compare_to: not reflected,
    )


def _configure_kwargs_online(connection) -> dict:
    """
    Configuration for online migrations (direct DB apply).
    Reflection is disabled; schema is driven purely from target_metadata.
    """
    return dict(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_schemas=False,
        # Critical: do NOT include reflected DB objects; rely only on models.
        include_object=lambda obj, name, type_, reflected, compare_to: not reflected,
    )


# ---------------------------------------------------------------------------
# Migration routines
# ---------------------------------------------------------------------------

def run_migrations_offline() -> None:
    if _SKIP_ALEMBIC:
        return

    url = config.get_main_option("sqlalchemy.url")
    if not url and app is not None:
        url = app.config.get("SQLALCHEMY_DATABASE_URI") or os.environ.get("DATABASE_URL")

    if not url:
        raise RuntimeError("No database URL configured for offline migrations.")

    context.configure(**_configure_kwargs_offline(url))

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    if _SKIP_ALEMBIC:
        return

    # Prefer engine from the app's db extension
    try:
        connectable = db.engine  # type: ignore[union-attr]
    except Exception:
        url = (
            config.get_main_option("sqlalchemy.url")
            or (app.config.get("SQLALCHEMY_DATABASE_URI") if app is not None else None)
            or os.environ.get("DATABASE_URL")
        )
        if not url:
            raise RuntimeError("No database URL configured for online migrations.")
        print(f"[alembic.env] using URL: {url}")
        connectable = create_engine(url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(**_configure_kwargs_online(connection))

        with context.begin_transaction():
            context.run_migrations()


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if not _SKIP_ALEMBIC:
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        run_migrations_online()
