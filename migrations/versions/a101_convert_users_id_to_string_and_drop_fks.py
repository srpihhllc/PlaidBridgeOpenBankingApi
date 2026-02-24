"""Convert users.id to String(36) and drop all referencing FKs.

Revision ID: a101_convert_users_id_to_string_and_drop_fks
Revises: 6e4aba4872cd
Create Date: 2026-01-12 11:37:00
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import mysql

revision = "a101_convert_users_id_to_string_and_drop_fks"
down_revision = "6e4aba4872cd"
branch_labels = None
depends_on = None

# Authoritative list of tables containing a user_id column
USER_ID_TABLES = [
    "access_tokens",
    "bank_accounts",
    "bank_institutions",
    "bank_statements",
    "borrower_cards",
    "complaint_logs",
    "credit_ledger",
    "dispute_log",
    "fraud_reports",
    "lenders",
    "mfa_codes",
    "payment_log",
    "plaid_items",
    "registries",
    "revoked_tokens",
    "schema_event",
    "subscriber_profile",
    "system_versions",
    "timeline_events",
    "todos",
    "trace_events",
    "tradelines",
    "transactions",
    "underwriter_agents",
    "user_dashboards",
    "vault_transactions",
]

# Deterministic FK names for downgrade
DOWNGRADE_FK_NAMES = {
    "access_tokens": "fk_access_tokens_user_id_users",
    "bank_accounts": "fk_bank_accounts_user_id_users",
    "bank_institutions": "fk_bank_institutions_user_id_users",
    "bank_statements": "fk_bank_statements_user_id_users",
    "borrower_cards": "fk_borrower_cards_user_id_users",
    "complaint_logs": "fk_complaint_logs_user_id_users",
    "credit_ledger": "fk_credit_ledger_user_id_users",
    "dispute_log": "fk_dispute_log_user_id_users",
    "fraud_reports": "fk_fraud_reports_user_id_users",
    "lenders": "fk_lenders_user_id_users",
    "mfa_codes": "fk_mfa_codes_user_id_users",
    "payment_log": "fk_payment_log_user_id_users",
    "plaid_items": "fk_plaid_items_user_id_users",
    "registries": "fk_registries_user_id_users",
    "revoked_tokens": "fk_revoked_tokens_user_id_users",
    "schema_event": "fk_schema_event_user_id_users",
    "subscriber_profile": "fk_subscriber_profile_user_id_users",
    "system_versions": "fk_system_versions_user_id_users",
    "timeline_events": "fk_timeline_events_user_id_users",
    "todos": "fk_todos_user_id_users",
    "trace_events": "fk_trace_events_user_id_users",
    "tradelines": "fk_tradelines_user_id_users",
    "transactions": "fk_transactions_user_id_users",
    "underwriter_agents": "fk_underwriter_agents_user_id_users",
    "user_dashboards": "fk_user_dashboards_user_id_users",
    "vault_transactions": "fk_vault_transactions_user_id_users",
}


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)

    # Drop ghost index on ledger_entries if it exists
    indexes = [idx["name"] for idx in inspector.get_indexes("ledger_entries")]
    if "fk_ledger_entries_borrower_id_users" in indexes:
        op.drop_index(
            "fk_ledger_entries_borrower_id_users",
            table_name="ledger_entries",
        )

    # Drop FK from ledger_entries.borrower_id → users.id
    fks = inspector.get_foreign_keys("ledger_entries")
    for fk in fks:
        if (
            fk.get("referred_table") == "users"
            and fk.get("referred_columns") == ["id"]
            and fk.get("constrained_columns") == ["borrower_id"]
        ):
            op.drop_constraint(
                fk["name"],
                "ledger_entries",
                type_="foreignkey",
            )

    # Convert ledger_entries.borrower_id INT → VARCHAR(36)
    op.alter_column(
        "ledger_entries",
        "borrower_id",
        existing_type=mysql.INTEGER(),
        type_=sa.String(length=36),
        existing_nullable=False,
    )

    # Drop all user_id → users.id FKs across 26 tables
    for table in USER_ID_TABLES:
        fks = inspector.get_foreign_keys(table)
        for fk in fks:
            if (
                fk.get("referred_table") == "users"
                and fk.get("referred_columns") == ["id"]
                and fk.get("constrained_columns") == ["user_id"]
            ):
                op.drop_constraint(
                    fk["name"],
                    table,
                    type_="foreignkey",
                )

    # Convert users.id INT → VARCHAR(36)
    op.alter_column(
        "users",
        "id",
        existing_type=mysql.INTEGER(),
        type_=sa.String(length=36),
        existing_nullable=False,
    )


def downgrade():
    # Revert users.id VARCHAR(36) → INT
    op.alter_column(
        "users",
        "id",
        existing_type=sa.String(length=36),
        type_=mysql.INTEGER(),
        existing_nullable=False,
    )

    # Revert ledger_entries.borrower_id VARCHAR(36) → INT
    op.alter_column(
        "ledger_entries",
        "borrower_id",
        existing_type=sa.String(length=36),
        type_=mysql.INTEGER(),
        existing_nullable=False,
    )

    # Restore FK on ledger_entries.borrower_id → users.id
    op.create_foreign_key(
        "fk_ledger_entries_borrower_id_users",
        "ledger_entries",
        "users",
        ["borrower_id"],
        ["id"],
    )

    # Restore all user_id → users.id FKs
    for table in USER_ID_TABLES:
        fk_name = DOWNGRADE_FK_NAMES[table]
        op.create_foreign_key(
            fk_name,
            table,
            "users",
            ["user_id"],
            ["id"],
        )

    # Restore ghost index
    op.create_index(
        "fk_ledger_entries_borrower_id_users",
        "ledger_entries",
        ["borrower_id"],
    )
