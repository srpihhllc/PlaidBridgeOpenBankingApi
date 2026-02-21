"""Add Todo model

Revision ID: bc6b0eacef38
Revises: 211bf581ad99
Create Date: 2025-12-28 02:44:16.378158
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "bc6b0eacef38"
down_revision = "211bf581ad99"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "todos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("completed", sa.Boolean(), default=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )


def downgrade():
    op.drop_table("todos")
