"""Add description column to transactions

Revision ID: bbce485d748c
Revises: 4bbd87e8395e
Create Date: 2026-01-11 01:36:55.036982
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "bbce485d748c"
down_revision = "4bbd87e8395e"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("transactions", sa.Column("description", sa.String(length=255), nullable=True))


def downgrade():
    op.drop_column("transactions", "description")
