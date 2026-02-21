"""Fix bank_accounts.user_id to String(36) with ON DELETE CASCADE"""

import sqlalchemy as sa
from alembic import op

revision = "a201_fix_bank_accounts_user_id_fk"
down_revision = "0c27dd4ad41e"  # your merge head
branch_labels = None
depends_on = None


def upgrade():
    # 1. Convert column type INT → VARCHAR(36)
    op.alter_column(
        "bank_accounts",
        "user_id",
        existing_type=sa.Integer(),
        type_=sa.String(36),
        existing_nullable=False,
    )

    # 2. Create FK with ON DELETE CASCADE
    op.create_foreign_key(
        "fk_bank_accounts_user_id",
        "bank_accounts",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade():
    # Reverse FK creation
    op.drop_constraint(
        "fk_bank_accounts_user_id",
        "bank_accounts",
        type_="foreignkey",
    )

    # Reverse column type change
    op.alter_column(
        "bank_accounts",
        "user_id",
        existing_type=sa.String(36),
        type_=sa.Integer(),
        existing_nullable=False,
    )
