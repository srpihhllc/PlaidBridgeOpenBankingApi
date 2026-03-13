from __future__ import annotations

import os
import sys
from configparser import ConfigParser
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine, pool

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.abspath(os.path.join(HERE, ".."))
REPO_ROOT = os.path.abspath(os.path.join(APP_ROOT, ".."))

if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

load_dotenv(os.path.join(APP_ROOT, ".env"))
load_dotenv(os.path.join(REPO_ROOT, ".env"))

config = context.config

if config.config_file_name:
    parser = ConfigParser(interpolation=None)
    parser.read(config.config_file_name)
    config.file_config = parser

if config.config_file_name and os.path.exists(config.config_file_name):
    fileConfig(config.config_file_name)

from app.extensions import db  # noqa: E402
import app.models  # noqa: F401,E402

target_metadata = db.metadata


def _database_url() -> str:
    url = (
        os.environ.get("DATABASE_URL")
        or os.environ.get("SQLALCHEMY_DATABASE_URI")
        or config.get_main_option("sqlalchemy.url")
    )
    if not url:
        raise RuntimeError("DATABASE_URL/SQLALCHEMY_DATABASE_URI is required for Alembic migrations")
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(_database_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
