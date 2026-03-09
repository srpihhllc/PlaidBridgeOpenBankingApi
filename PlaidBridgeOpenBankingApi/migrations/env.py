# /home/srpihhllc/PlaidBridgeOpenBankingApi/migrations/env.py

import os
import sys
from configparser import ConfigParser
from logging.config import fileConfig
from urllib.parse import urlparse, urlunparse

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine, pool

# ---------------------------------------------------------------------------
# 0. Quick guard: if we're running under pytest (or alembic.context is not the
#    normal Alembic runtime object), avoid running the Alembic env logic which
#    expects the alembic CLI context. This prevents import-time AttributeError
#    when tests collect this file.
# ---------------------------------------------------------------------------
_IS_PYTEST = "PYTEST_CURRENT_TEST" in os.environ or "pytest" in sys.modules

# Additionally, if the imported `context` object doesn't appear to be the
# expected alembic.context (i.e., it lacks `config` or `is_offline_mode`), skip.
if not _IS_PYTEST:
    _CONTEXT_HAS_EXPECTED = hasattr(context, "config") and hasattr(context, "is_offline_mode")
else:
    _CONTEXT_HAS_EXPECTED = False

if not _CONTEXT_HAS_EXPECTED:
    # No-op: skip Alembic env bootstrap when running tests or when alembic.context
    # does not expose the expected runtime API.
    print("NOTE: Skipping Alembic env bootstrap (running under test or missing alembic context).")
    _SKIP_ALEMBIC = True
else:
    _SKIP_ALEMBIC = False

# ---------------------------------------------------------------------------
# 1. Load Flask application environment (only if not skipping)
# ---------------------------------------------------------------------------
if not _SKIP_ALEMBIC:
    # Set up paths so imports consistently resolve to the package-local app module.
    PROJECT_HOME = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    APP_HOME = os.path.join(PROJECT_HOME, "PlaidBridgeOpenBankingApi")

    if APP_HOME not in sys.path:
        sys.path.insert(0, APP_HOME)
    if PROJECT_HOME not in sys.path:
        sys.path.insert(0, PROJECT_HOME)

    # BOOTSTRAP: Load .env before Flask app factory runs
    load_dotenv(os.path.join(PROJECT_HOME, ".env"))

    def get_flask_app():
        # Import from the canonical module path used by this codebase.
        from app import create_app
        return create_app()

    flask_app = get_flask_app()

    # ---------------------------------------------------------------------------
    # 2. Alembic Configuration
    # ---------------------------------------------------------------------------

    config = context.config

    # Disable interpolation (%) so passwords with special chars don't break
    if config.config_file_name:
        parser = ConfigParser(interpolation=None)
        parser.read(config.config_file_name)
        config.file_config = parser

    # Standard Logging Setup
    if config.config_file_name and os.path.exists(config.config_file_name):
        fileConfig(config.config_file_name)

    # Link to models via the established Flask extension
    target_metadata = flask_app.extensions["migrate"].db.metadata

    # ---------------------------------------------------------------------------
    # 3. Migration Modes
    # ---------------------------------------------------------------------------

    def run_migrations_offline():
        """Run migrations in 'offline' mode."""
        url = flask_app.config["SQLALCHEMY_DATABASE_URI"]
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
        """Run migrations in 'online' mode with aggressive debugging."""
        # 1. Grab the URI from Flask config
        raw_url = flask_app.config.get("SQLALCHEMY_DATABASE_URI", "")

        # 2. DEBUG PRINT: Check what is being inherited
        print(f"\n[DEBUG] Raw URI from Flask: {raw_url}")

        target_host = "srpihhllc.mysql.pythonanywhere-services.com"
        final_url = raw_url

        # 3. BRUTE FORCE HOST CORRECTION
        # PythonAnywhere specific: localhost/127.0.0.1 resolves to 10.0.5.36 (wrong node)
        if "localhost" in raw_url or "127.0.0.1" in raw_url:
            print(f"⚠️  DETECTION: Localhost found in URI. Forcing {target_host}")
            final_url = raw_url.replace("localhost", target_host).replace("127.0.0.1", target_host)

        # Final validation of the parsed hostname
        parsed = urlparse(final_url)
        if parsed.hostname != target_host:
            # Short, single f-string to satisfy line-length limits
            print(f"🛑 CRITICAL: host is {parsed.hostname}; starting manual reconstruction...")
            # Re-build netloc to ensure user:pass@target_host:port
            auth_part = parsed.netloc.split("@")[0] if "@" in parsed.netloc else ""
            port_part = f":{parsed.port}" if parsed.port else ""

            if auth_part:
                new_netloc = f"{auth_part}@{target_host}{port_part}"
            else:
                new_netloc = f"{target_host}{port_part}"

            final_url = urlunparse(parsed._replace(netloc=new_netloc))

        print(f"🚀 FINAL URI HOST: {urlparse(final_url).hostname}")
        print(f"🚀 FINAL URI DATABASE: {urlparse(final_url).path}\n")

        # 4. Create engine (using NullPool as required for many serverless/restricted environments)
        connectable = create_engine(final_url, poolclass=pool.NullPool)

        try:
            with connectable.connect() as connection:
                context.configure(
                    connection=connection,
                    target_metadata=target_metadata,
                    compare_type=True,
                    compare_server_default=True,
                )

                with context.begin_transaction():
                    context.run_migrations()
        except Exception as e:
            print(f"❌ CONNECTION FAILED: {e}")
            # Re-raise to let Alembic handle the exit
            raise

# ---------------------------------------------------------------------------
# 4. Execution Entrypoint (guarded)
# ---------------------------------------------------------------------------
if not _SKIP_ALEMBIC:
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        run_migrations_online()
