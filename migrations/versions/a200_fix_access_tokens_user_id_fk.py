"""Fix access_tokens.user_id to String(36) with ON DELETE CASCADE.

Revision ID: a200_fix_access_tokens_user_id_fk
Revises: f996868ab1a4
Create Date: 2026-02-01 22:50:00
"""

import sqlalchemy as sa
from alembic import op

revision = "a200_fix_access_tokens_user_id_fk"
down_revision = "f996868ab1a4"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    table = "access_tokens"
    column = "user_id"

    # 1. Drop existing FK(s) to users.id on access_tokens.user_id
    fks = inspector.get_foreign_keys(table)
    for fk in fks:
        if fk["referred_table"] == "users" and column in fk["constrained_columns"]:
            op.drop_constraint(fk["name"], table_name=table, type_="foreignkey")

    # 2. Alter column type to String(36)
    op.alter_column(
        table,
        column,
        existing_type=sa.Integer(),
        type_=sa.String(length=36),
        existing_nullable=False,
    )

    # 3. Re-add FK with ON DELETE CASCADE
    op.create_foreign_key(
        "fk_access_tokens_user_id_users",
        source_table=table,
        referent_table="users",
        local_cols=[column],
        remote_cols=["id"],
        ondelete="CASCADE",
    )


def downgrade():
    table = "access_tokens"
    column = "user_id"

    # Drop new FK
    op.drop_constraint(
        "fk_access_tokens_user_id_users",
        table_name=table,
        type_="foreignkey",
    )

    # Revert column type to Integer
    op.alter_column(
        table,
        column,
        existing_type=sa.String(length=36),
        type_=sa.Integer(),
        existing_nullable=False,
    )

    # Re-add old FK without cascade
    op.create_foreign_key(
        "fk_access_tokens_user_id_users_old",
        source_table=table,
        referent_table="users",
        local_cols=[column],
        remote_cols=["id"],
    )
