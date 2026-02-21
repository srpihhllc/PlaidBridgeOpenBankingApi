"""Add updated_at column to users

Revision ID: 4c3ceeaf8283
Revises: 11b5ce097bf4
Create Date: 2025-11-16 17:37:44.623633

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "4c3ceeaf8283"
down_revision = "11b5ce097bf4"
branch_labels = None
depends_on = None


def upgrade():
    # Add updated_at column with a default timestamp for existing rows
    op.add_column(
        "users",
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    # Drop the column if rolling back
    op.drop_column("users", "updated_at")
