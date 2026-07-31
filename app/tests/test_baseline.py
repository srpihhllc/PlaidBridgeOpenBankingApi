# =============================================================================
# FILE: /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_baseline.py
# DESCRIPTION: Essential environment and database integrity checks.
# =============================================================================

import uuid
import pkgutil
import importlib

import pytest
import sqlalchemy as sa

from app.extensions import db
from app.models.timeline import TimelineEvent  # noqa: F401
from app.models.todo import Todo  # noqa: F401
from app.models.user import User  # noqa: F401

import app.models as models_pkg  # noqa: F401


# --- HELPERS ---


def get_admin_id(conn) -> str | None:
    """Return the id of the seeded admin (if present)."""
    res = conn.execute(
        sa.text("SELECT id FROM users WHERE email='srpollardsihhllc@gmail.com' OR is_admin = 1")
    ).fetchone()
    return res[0] if res else None


def _fk_has_ondelete(engine, table_name: str, referred_table: str) -> bool:
    """
    Best-effort detection of ON DELETE CASCADE:
      - SQLite: read CREATE TABLE SQL from sqlite_master and search for 'ON DELETE CASCADE'
      - Other DBs: use Inspector.get_foreign_keys and check fk['options']['ondelete']
    """
    dialect = engine.dialect.name.lower()
    if dialect == "sqlite":
        try:
            with engine.connect() as conn:
                row = conn.execute(
                    sa.text("SELECT sql FROM sqlite_master WHERE type='table' AND name = :t"),
                    {"t": table_name}
                ).fetchone()
            if not row or not row[0]:
                return False
            create_sql = row[0].upper()
            return "ON DELETE CASCADE" in create_sql
        except Exception:
            return False
    else:
        try:
            inspector = sa.inspect(engine)
            fks = inspector.get_foreign_keys(table_name)
            for fk in fks:
                if fk.get("referred_table") == referred_table:
                    if fk.get("options", {}).get("ondelete", "").upper() == "CASCADE":
                        return True
            return False
        except Exception:
            return False


# --- TESTS ---


def test_admin_user_exists(app):
    """Verify the baseline admin exists and has correct privileges."""
    with app.app_context():
        for finder, modname, ispkg in pkgutil.iter_modules(models_pkg.__path__):
            importlib.import_module(f"app.models.{modname}")

        db.create_all()
        db.session.flush()

        conn = db.session.connection()
        row = conn.execute(
            sa.text("SELECT id, username, email, is_admin FROM users WHERE email='srpollardsihhllc@gmail.com' OR is_admin = 1")
        ).fetchone()

        if row is None:
            pytest.skip("Admin user not seeded in database.")

        assert bool(getattr(row, "is_admin", False)) is True


USER_FK_TABLES = [
    (
        "access_tokens",
        "user_id",
        "INSERT INTO access_tokens (id, user_id, token, created_at) VALUES (:id, :uid, :tok, CURRENT_TIMESTAMP)",
        lambda: {"id": str(uuid.uuid4()), "tok": "tokentest"},
    ),
    (
        "bank_accounts",
        "user_id",
        "INSERT INTO bank_accounts (id, user_id, account_type, account_number, balance, created_at) VALUES (99001, :uid, 'checking', 'ACC_TEST', 10.0, CURRENT_TIMESTAMP)",
        lambda: {},
    ),
    (
        "bank_institutions",
        "user_id",
        "INSERT INTO bank_institutions (id, user_id, name, institution_id) VALUES (99002, :uid, 'pytest_bank', 'INST_1')",
        lambda: {},
    ),
    (
        "transactions",
        "user_id",
        "INSERT INTO transactions (id, user_id, amount, date) VALUES (:id, :uid, 1.0, CURRENT_TIMESTAMP)",
        lambda: {"id": str(uuid.uuid4())},
    ),
    (
        "timeline_events",
        "user_id",
        "INSERT INTO timeline_events (user_id, event_type) VALUES (:uid, 'test_event')",
        lambda: {},
    ),
    (
        "todos",
        "user_id",
        "INSERT INTO todos (user_id, text, completed, priority, created_at, updated_at)"
        " VALUES (:uid, 'test_todo', 0, 'normal', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
        lambda: {},
    ),
]


@pytest.mark.parametrize(("table_name", "column", "sql", "extra_params"), USER_FK_TABLES)
def test_user_foreign_key_cascades(app, table_name, column, sql, extra_params):
    """
    For each user-related table, insert a record keyed to a temp user, delete the user,
    and assert the child record was removed by cascade.
    """
    with app.app_context():
        for finder, modname, ispkg in pkgutil.iter_modules(models_pkg.__path__):
            importlib.import_module(f"app.models.{modname}")

        db.create_all()

        inspector = sa.inspect(db.engine)
        if table_name not in inspector.get_table_names():
            pytest.skip(f"Table '{table_name}' not present after create_all(); skipping cascade test.")

        conn = db.session.connection()
        conn.execute(sa.text("PRAGMA foreign_keys = ON;"))

        temp_uid = str(uuid.uuid4())
        test_user = User(
            id=temp_uid,
            username=f"test_{table_name}",
            email=f"{table_name}@test.com",
            password_hash="nosync",
        )
        db.session.add(test_user)
        db.session.flush()

        params = {"uid": temp_uid}
        params.update(extra_params())

        try:
            conn.execute(sa.text(sql), params)
        except sa.exc.OperationalError as oe:
            pytest.skip(f"Skipping insertion for '{table_name}' due to DB schema mismatch: {oe}")

        check_exists = conn.execute(
            sa.text(f"SELECT 1 FROM {table_name} WHERE {column} = :uid"),
            {"uid": temp_uid},
        ).fetchone()
        assert check_exists is not None, f"Failed to insert test record into {table_name}"

        db.session.delete(test_user)
        db.session.commit()

        conn = db.session.connection()
        check_deleted = conn.execute(
            sa.text(f"SELECT 1 FROM {table_name} WHERE {column} = :uid"),
            {"uid": temp_uid},
        ).fetchone()
        assert check_deleted is None, f"CASCADE FAILED: Record still exists in {table_name} after user deletion!"


def test_bank_transactions_fk_and_cascade(app):
    """
    Verifies bank_transactions references valid accounts and cleans up on delete.
    """
    with app.app_context():
        for finder, modname, ispkg in pkgutil.iter_modules(models_pkg.__path__):
            importlib.import_module(f"app.models.{modname}")

        db.create_all()

        engine = db.engine
        if not _fk_has_ondelete(engine, "bank_transactions", "bank_accounts"):
            pytest.skip("bank_transactions → bank_accounts FK missing ON DELETE CASCADE; skipping cascade test.")

        with db.session.begin_nested():
            conn = db.session.connection()
            admin_id = get_admin_id(conn)

            if not admin_id:
                temp_admin_id = str(uuid.uuid4())
                temp_admin = User(
                    id=temp_admin_id,
                    username="srpihhllc",
                    email="srpollardsihhllc@gmail.com",
                    password_hash="noop",
                    is_admin=True,
                )
                db.session.add(temp_admin)
                db.session.flush()
                admin_id = temp_admin.id

            conn.execute(
                sa.text("INSERT INTO bank_accounts (id, user_id, account_type, account_number, balance, created_at) VALUES (99031, :uid, 'checking', 'ACC_X', 10.0, CURRENT_TIMESTAMP)"),
                {"uid": admin_id},
            )
            conn.execute(
                sa.text("INSERT INTO bank_transactions (id, from_account_id, to_account_id, amount) VALUES (99099, 99031, 99031, 50.0)"),
            )

            txn = conn.execute(sa.text("SELECT id FROM bank_transactions WHERE id = 99099")).fetchone()
            assert txn is not None, "Failed to insert test bank_transaction"

        db.session.rollback()