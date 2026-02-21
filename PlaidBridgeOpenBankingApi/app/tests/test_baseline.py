# =============================================================================
# FILE: /home/srpihhllc/PlaidBridgeOpenBankingApi/app/tests/test_baseline.py
# DESCRIPTION: Essential environment and database integrity checks.
# Ensures the admin exists and verifies 31 Foreign Key relationships.
# Verifies ON DELETE CASCADE logic and uses Savepoints for auto-cleanup.
# =============================================================================

import uuid

import pytest
import sqlalchemy as sa

from app.extensions import db
from app.models.audit import AuditLog, FinancialAuditLog  # noqa: F401
from app.models.timeline import TimelineEvent  # noqa: F401
from app.models.todo import Todo  # noqa: F401
from app.models.user import User  # noqa: F401

# --- HELPERS ---


def get_admin_id(conn) -> int:
    """Finds the actual super-admin (your account)."""
    res = conn.execute(
        sa.text("SELECT id FROM users WHERE email='srpollardsihhllc@gmail.com'")
    ).fetchone()
    # Safely return the ID if the row exists
    return res[0] if res else None


# --- BASE INTEGRITY TESTS ---


def test_admin_user_exists(app):
    """Verify the baseline admin exists and has correct privileges."""
    with app.app_context():
        db.create_all()  # Ensure tables are created
        # Ensure the seed fixture data is flushed to the DB for raw SQL visibility
        db.session.flush()

        conn = db.session.connection()
        row = conn.execute(
            sa.text(
                "SELECT id, username, email, is_admin FROM users WHERE "
                "email='srpollardsihhllc@gmail.com'"
            )
        ).fetchone()

        if row is None:
            pytest.skip("Admin user not seeded in database.")

        # Core Assertions
        assert row.username == "srpihhllc", (
            f"Expected username 'srpihhllc', got '{row.username}'"
        )

        # Security Assertion: Handle DB integer/boolean representation (1 vs True)
        # SQLAlchemy rows can return 1 for True in SQLite/MySQL. bool(1) == True.
        is_admin_value = getattr(row, "is_admin", False)
        assert bool(is_admin_value) is True, (
            f"User exists but is not marked as Admin. Got: {is_admin_value}"
        )


# --- USERS FOREIGN KEY COVERAGE (31 TABLES) ---

USER_FK_TABLES = [
    (
        "access_tokens",
        "user_id",
        (
            "INSERT INTO access_tokens (id, user_id, token, created_at) "
            "VALUES (:id, :uid, :tok, CURRENT_TIMESTAMP)"
        ),
        lambda: {"id": str(uuid.uuid4()), "tok": "tokentest"},
    ),
    (
        "audit_log",
        "user_id",
        "INSERT INTO audit_log (user_id, action) VALUES (:uid, 'test_action')",
        lambda: {},
    ),
    (
        "bank_accounts",
        "user_id",
        (
            "INSERT INTO bank_accounts (user_id, account_type, account_number, balance, "
            "created_at) VALUES (:uid, 'checking', 'ACC_TEST', 10.0, CURRENT_TIMESTAMP)"
        ),
        lambda: {},
    ),
    (
        "bank_institutions",
        "user_id",
        (
            "INSERT INTO bank_institutions (id, user_id, name, institution_id) "
            "VALUES (99001, :uid, 'pytest_bank', 'INST_1')"
        ),
        lambda: {},
    ),
    (
        "bank_statements",
        "user_id",
        (
            "INSERT INTO bank_statements (id, user_id, bank, account, name, txn_count, "
            "source_api, timestamp, created_at) VALUES (99002, :uid, 'bank', 'acc', "
            "'stmt', 0, 'api', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ),
        lambda: {},
    ),
    (
        "borrower_cards",
        "user_id",
        (
            "INSERT INTO borrower_cards (id, user_id, card_number, expiration_date, cvv, "
            "score, color) VALUES (99003, :uid, '4111...', '12/30', '123', 700, 'blue')"
        ),
        lambda: {},
    ),
    (
        "complaint_logs",
        "user_id",
        (
            "INSERT INTO complaint_logs (id, transaction_id, user_id, category, status) "
            "VALUES (99004, :txn_id, :uid, 'test', 'open')"
        ),
        lambda: {},
    ),
    (
        "credit_ledger",
        "user_id",
        (
            "INSERT INTO credit_ledger (id, user_id, card_id, credit_limit, balance_used) "
            "VALUES (99005, :uid, 'pytest_card', 1000, 0)"
        ),
        lambda: {},
    ),
    (
        "dispute_log",
        "user_id",
        (
            "INSERT INTO dispute_log (id, user_id, template_title, bureau, method, "
            "content_hash) VALUES (99006, :uid, 'title', 'exp', 'email', 'hash')"
        ),
        lambda: {},
    ),
    (
        "financial_audit_log",
        "actor_id",
        "INSERT INTO financial_audit_log (actor_id, action) VALUES (:uid, 'test_action')",
        lambda: {},
    ),
    (
        "fraud_reports",
        "user_id",
        (
            "INSERT INTO fraud_reports (id, user_id, category, severity, status) "
            "VALUES (:id, :uid, 'fraud', 'low', 'open')"
        ),
        lambda: {"id": str(uuid.uuid4())},
    ),
    (
        "ledger_entries",
        "borrower_id",
        "INSERT INTO ledger_entries (id, borrower_id, amount) VALUES (99007, :uid, 100.0)",
        lambda: {},
    ),
    (
        "lenders",
        "user_id",
        (
            "INSERT INTO lenders (id, user_id, business_name, owner_name, ssn_or_ein, "
            "license_number, address) VALUES (99008, :uid, 'biz', 'own', '123', 'lic', "
            "'addr')"
        ),
        lambda: {},
    ),
    (
        "loan_agreement",
        "borrower_id",
        (
            "INSERT INTO loan_agreement (id, lender_id, borrower_id, terms) "
            "VALUES (99009, :uid, :uid, 'terms')"
        ),
        lambda: {},
    ),
    (
        "mfa_codes",
        "user_id",
        (
            "INSERT INTO mfa_codes (id, user_id, code, created_at, expires_at, fail_count) "
            "VALUES (99010, :uid, '123456', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 0)"
        ),
        lambda: {},
    ),
    (
        "payment_log",
        "user_id",
        (
            "INSERT INTO payment_log (id, user_id, payment_processor_id, amount, currency, "
            "status, transaction_type) VALUES (99011, :uid, 'proc', 1.0, 'USD', 'ok', "
            "'test')"
        ),
        lambda: {},
    ),
    (
        "plaid_items",
        "user_id",
        (
            "INSERT INTO plaid_items (id, user_id, plaid_item_id, access_token) "
            "VALUES (99012, :uid, 'item', 'tok')"
        ),
        lambda: {},
    ),
    (
        "registries",
        "user_id",
        "INSERT INTO registries (id, user_id, name) VALUES (99013, :uid, 'reg')",
        lambda: {},
    ),
    (
        "revoked_tokens",
        "user_id",
        (
            "INSERT INTO revoked_tokens (id, jti, user_id, created_at) "
            "VALUES (99014, 'jti', :uid, CURRENT_TIMESTAMP)"
        ),
        lambda: {},
    ),
    (
        "schema_event",
        "user_id",
        "INSERT INTO schema_event (id, user_id, event_type) VALUES (99015, :uid, 'type')",
        lambda: {},
    ),
    (
        "subscriber_profile",
        "user_id",
        "INSERT INTO subscriber_profile (user_id, api_key) VALUES (:uid, 'test_api_key')",
        lambda: {},
    ),
    (
        "system_versions",
        "user_id",
        "INSERT INTO system_versions (id, user_id, version_hash) VALUES (99017, :uid, 'hash')",
        lambda: {},
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
        "INSERT INTO todos (user_id, title) VALUES (:uid, 'test_todo')",
        lambda: {},
    ),
    (
        "trace_events",
        "user_id",
        (
            "INSERT INTO trace_events (id, event_id, event_type, user_id) "
            "VALUES (99018, 'evt', 'type', :uid)"
        ),
        lambda: {},
    ),
    (
        "tradelines",
        "user_id",
        "INSERT INTO tradelines (id, vendor_name, user_id) VALUES (99019, 'vendor', :uid)",
        lambda: {},
    ),
    (
        "transactions",
        "user_id",
        (
            "INSERT INTO transactions (id, user_id, amount, date) "
            "VALUES (:id, :uid, 1.0, CURRENT_TIMESTAMP)"
        ),
        lambda: {"id": str(uuid.uuid4())},
    ),
    (
        "underwriter_agents",
        "user_id",
        (
            "INSERT INTO underwriter_agents (id, user_id, name, status, created_at) "
            "VALUES (99020, :uid, 'agent', 'active', CURRENT_TIMESTAMP)"
        ),
        lambda: {},
    ),
    (
        "user_dashboards",
        "user_id",
        (
            "INSERT INTO user_dashboards (id, user_id, settings, created_at, updated_at) "
            "VALUES (99021, :uid, '{}', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ),
        lambda: {},
    ),
    (
        "vault_transactions",
        "user_id",
        (
            "INSERT INTO vault_transactions (id, user_id, transaction_id, amount, "
            "currency, status) VALUES (99022, :uid, 'txn', 1.0, 'USD', 'ok')"
        ),
        lambda: {},
    ),
]


@pytest.mark.parametrize(("table_name", "column", "sql", "extra_params"), USER_FK_TABLES)
def test_user_foreign_key_cascades(app, table_name, column, sql, extra_params):
    """
    Verifies that deleting a user cascades to all related tables.
    Iterates through the 31 tables defined in USER_FK_TABLES (all User relationships).
    """
    # Models are imported at module scope to register tables with SQLAlchemy.
    with app.app_context():
        db.create_all()  # Ensure tables are created with FKs

        # Enable SQLite foreign keys (required for CASCADE to work in tests)
        conn = db.session.connection()
        conn.execute(sa.text("PRAGMA foreign_keys = ON;"))

        # 1. Create a temporary test user
        temp_uid = str(uuid.uuid4())
        test_user = User(
            id=temp_uid,
            username=f"test_{table_name}",
            email=f"{table_name}@test.com",
            password_hash="nosync",
        )
        db.session.add(test_user)
        db.session.flush()

        # 2. Insert related record into the child table
        if table_name == "complaint_logs":
            # Create a dummy transaction for FK
            txn_id = str(uuid.uuid4())
            conn.execute(
                sa.text(
                    "INSERT INTO transactions (id, user_id, amount, date) "
                    "VALUES (:txn_id, :uid, 1.0, CURRENT_TIMESTAMP)"
                ),
                {"txn_id": txn_id, "uid": temp_uid},
            )
            params = {"uid": temp_uid, "txn_id": txn_id}
        else:
            params = {"uid": temp_uid}

        params.update(extra_params())
        conn.execute(sa.text(sql), params)

        # Verify insertion
        check_exists = conn.execute(
            sa.text(f"SELECT 1 FROM {table_name} WHERE {column} = :uid"),
            {"uid": temp_uid},
        ).fetchone()
        assert check_exists is not None, f"Failed to insert test record into {table_name}"

        # 3. Delete the User (Trigger the Cascade)
        db.session.delete(test_user)
        db.session.commit()

        # 4. Re-acquire a fresh connection after commit
        conn = db.session.connection()

        # 5. Verify the child record is GONE
        check_deleted = conn.execute(
            sa.text(f"SELECT 1 FROM {table_name} WHERE {column} = :uid"),
            {"uid": temp_uid},
        ).fetchone()
        assert check_deleted is None, (
            f"CASCADE FAILED: Record still exists in {table_name} after user deletion!"
        )


# --- CROSS-TABLE FK & CASCADE TESTS ---


def test_bank_transactions_fk_and_cascade(app):
    """Verifies bank_transactions references valid accounts and cleans up on delete."""
    with app.app_context():
        db.create_all()  # Ensure tables are created
        with db.session.begin_nested():
            conn = db.session.connection()
            admin_id = get_admin_id(conn)

            # Setup Parent Account
            conn.execute(
                sa.text(
                    "INSERT INTO bank_accounts (id, user_id, account_type, account_number, "
                    "balance, created_at) VALUES (99031, :uid, 'checking', 'ACC_X', 10.0, "
                    "CURRENT_TIMESTAMP)"
                ),
                {"uid": admin_id},
            )

            # Setup Transaction (Child)
            conn.execute(
                sa.text(
                    "INSERT INTO bank_transactions (id, from_account_id, to_account_id, "
                    "amount, txn_type, method, timestamp) VALUES (99033, 99031, 99031, 5.0, "
                    "'transfer', 'manual', CURRENT_TIMESTAMP)"
                )
            )

            # Invalid Insert (Bad Account ID)
            with pytest.raises(sa.exc.IntegrityError):
                conn.execute(
                    sa.text(
                        "INSERT INTO bank_transactions (id, from_account_id, to_account_id, "
                        "amount) VALUES (99034, 999999, 99031, 5.0)"
                    )
                )

            # Test CASCADE: Delete Parent, check if Child vanishes
            conn.execute(sa.text("DELETE FROM bank_accounts WHERE id=99031"))
            child = conn.execute(
                sa.text("SELECT id FROM bank_transactions WHERE id=99033")
            ).fetchone()
            assert child is None, "CASCADE delete failed; orphan transaction remains."


def test_subscriptions_fk(app):
    """Verifies subscriptions references valid subscriber_profiles."""
    with app.app_context():
        db.create_all()  # Ensure tables are created
        with db.session.begin_nested():
            conn = db.session.connection()
            admin_id = get_admin_id(conn)
            conn.execute(
                sa.text(
                    "INSERT INTO subscriber_profile (id, user_id, full_name, username, "
                    "email, bank_name, routing_number, home_address, password_hash) "
                    "VALUES (99051, :uid, 'Name', 'uname', 'e@e.com', 'bank', '123', "
                    "'addr', 'hash')"
                ),
                {"uid": admin_id},
            )

            # Valid insert
            conn.execute(
                sa.text(
                    "INSERT INTO subscriptions (id, status, subscriber_profile_id, "
                    "created_at) VALUES (99052, 'active', 99051, CURRENT_TIMESTAMP)"
                )
            )

            # Invalid insert
            with pytest.raises(sa.exc.IntegrityError):
                conn.execute(
                    sa.text(
                        "INSERT INTO subscriptions (id, status, subscriber_profile_id) "
                        "VALUES (99053, 'active', 999999)"
                    )
                )


def test_complaint_logs_transactions_fk(app):
    """Verifies complaint_logs references valid transactions and users."""
    with app.app_context():
        db.create_all()  # Ensure tables are created
        with db.session.begin_nested():
            conn = db.session.connection()
            admin_id = get_admin_id(conn)
            txn_id = str(uuid.uuid4())

            # Parent Transaction
            conn.execute(
                sa.text(
                    "INSERT INTO transactions (id, user_id, amount, date, name) "
                    "VALUES (:tid, :uid, 1.0, CURRENT_TIMESTAMP, 'parent')"
                ),
                {"tid": txn_id, "uid": admin_id},
            )

            # Valid Complaint
            conn.execute(
                sa.text(
                    "INSERT INTO complaint_logs (id, transaction_id, user_id, category, "
                    "status) VALUES (99061, :tid, :uid, 'cat', 'open')"
                ),
                {"tid": txn_id, "uid": admin_id},
            )

            # Invalid Complaint (bad transaction ID)
            with pytest.raises(sa.exc.IntegrityError):
                conn.execute(
                    sa.text(
                        "INSERT INTO complaint_logs (id, transaction_id, user_id) "
                        "VALUES (99062, '00000000-0000-0000-0000-000000000000', :uid)"
                    ),
                    {"uid": admin_id},
                )


def test_ensure_all_user_related_tables_have_cascades(app):
    """
    Metadata audit to ensure no new tables are added without CASCADE rules.
    This prevents 'Data Drift' as you add more features.
    """
    with app.app_context():
        db.create_all()  # Ensure tables are created
        inspector = sa.inspect(db.engine)
        for table_name in inspector.get_table_names():
            fks = inspector.get_foreign_keys(table_name)
            for fk in fks:
                # If it points to the users table
                if fk["referred_table"] == "users":
                    # Ensure ondelete is set to CASCADE for ALL
                    assert fk.get("options", {}).get("ondelete") == "CASCADE", (
                        f"Table '{table_name}' has a FK to 'users' but is missing "
                        "ON DELETE CASCADE!"
                    )