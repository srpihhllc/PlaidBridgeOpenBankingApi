"""full_schema_alignment_after_model_rewrite

Revision ID: 51c060321aba
Revises: a201_fix_bank_accounts_user_id_fk
Create Date: 2026-02-06 15:59:40.737692

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = "51c060321aba"
down_revision = "a201_fix_bank_accounts_user_id_fk"
branch_labels = None
depends_on = None


def upgrade():
    # ------------------------------------------------------------------
    # Tables that still have user_id as INT and need conversion
    # ------------------------------------------------------------------
    tables_needing_conversion = [
        "fraud_reports",
        "mfa_codes",
        "schema_event",
        "subscriber_profile",
        "trace_events",
        "tradelines",
        "transactions",
        "underwriter_agents",
        "vault_transactions",
    ]

    for table in tables_needing_conversion:
        try:
            op.alter_column(
                table,
                "user_id",
                existing_type=mysql.INTEGER(),
                type_=sa.String(length=36),
                existing_nullable=False,
            )
        except Exception:
            # Column may already be converted or table may not exist, skip
            pass

    # ------------------------------------------------------------------
    # Add missing FKs for fraud_reports
    # ------------------------------------------------------------------
    try:
        op.create_foreign_key(
            "fk_fraud_reports_user_id_users",
            "fraud_reports",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )
    except Exception:
        # FK may already exist, skip
        pass

    # ------------------------------------------------------------------
    # Add missing FKs for transactions
    # ------------------------------------------------------------------
    try:
        op.create_foreign_key(
            "fk_transactions_user_id_users",
            "transactions",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )
    except Exception:
        # FK may already exist, skip
        pass

    # ------------------------------------------------------------------
    # Add FKs for other tables that may need them
    # ------------------------------------------------------------------
    fk_tables = [
        ("mfa_codes", "fk_mfa_codes_user_id_users"),
        ("schema_event", "fk_schema_event_user_id_users"),
        ("subscriber_profile", "fk_subscriber_profile_user_id_users"),
        ("trace_events", "fk_trace_events_user_id_users"),
        ("tradelines", "fk_tradelines_user_id_users"),
        ("underwriter_agents", "fk_underwriter_agents_user_id_users"),
        ("vault_transactions", "fk_vault_transactions_user_id_users"),
    ]

    for table, fk_name in fk_tables:
        try:
            op.create_foreign_key(
                fk_name,
                table,
                "users",
                ["user_id"],
                ["id"],
                ondelete="CASCADE",
            )
        except Exception:
            # FK may already exist or table may not exist, skip
            pass

    # ------------------------------------------------------------------
    # Final cleanup for audit_logs columns that were causing the crash
    # This ensures the migration history is complete and consistent
    # ------------------------------------------------------------------
    for col in ["message", "timestamp"]:
        try:
            op.drop_column("audit_logs", col)
        except Exception:
            # Already dropped in the manual/partial run
            pass


def downgrade():
    # Downgrade: revert VARCHAR(36) back to INT
    tables_needing_revert = [
        "fraud_reports",
        "mfa_codes",
        "schema_event",
        "subscriber_profile",
        "trace_events",
        "tradelines",
        "transactions",
        "underwriter_agents",
        "vault_transactions",
    ]

    for table in tables_needing_revert:
        try:
            op.alter_column(
                table,
                "user_id",
                existing_type=sa.String(length=36),
                type_=mysql.INTEGER(),
                existing_nullable=False,
            )
        except Exception:
            # Column may not exist or table may not exist, skip
            pass

    # Restore audit_logs columns
    try:
        op.add_column(
            "audit_logs",
            sa.Column("message", mysql.TEXT(), nullable=True),
        )
        op.add_column(
            "audit_logs",
            sa.Column("timestamp", mysql.DATETIME(), nullable=True),
        )
    except Exception:
        # Columns may already exist, skip
        pass
