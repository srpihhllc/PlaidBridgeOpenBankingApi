"""Recreate user-related foreign keys using String(36) ids.

Revision ID: a103_recreate_user_foreign_keys_string_ids
Revises: a101_convert_users_id_to_string_and_drop_fks
Create Date: 2026-01-12 11:38:30
"""

from alembic import op

revision = "a103_recreate_user_foreign_keys_string_ids"
down_revision = "a101_convert_users_id_to_string_and_drop_fks"
branch_labels = None
depends_on = None


def upgrade():
    # financial_audit_logs.actor_id → users.id
    op.create_foreign_key(
        "fk_financial_audit_logs_actor_id_users",
        "financial_audit_logs",
        "users",
        ["actor_id"],
        ["id"],
    )


def downgrade():
    op.drop_constraint(
        "fk_financial_audit_logs_actor_id_users",
        "financial_audit_logs",
        type_="foreignkey",
    )
