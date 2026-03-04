"""Add ACH/Wire metadata fields to bank_transactions

Revision ID: 6e4aba4872cd
Revises: bbce485d748c
Create Date: 2026-01-11 18:19:07.010206
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "6e4aba4872cd"
down_revision = "bbce485d748c"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "bank_transactions",
        sa.Column("ach_trace_number", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "bank_transactions",
        sa.Column("ach_sec_code", sa.String(length=10), nullable=True),
    )
    op.add_column(
        "bank_transactions",
        sa.Column("wire_reference", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "bank_transactions",
        sa.Column("originating_routing", sa.String(length=9), nullable=True),
    )
    op.add_column(
        "bank_transactions",
        sa.Column("receiving_routing", sa.String(length=9), nullable=True),
    )
    op.add_column(
        "bank_transactions",
        sa.Column("payment_channel", sa.String(length=20), nullable=True),
    )


def downgrade():
    op.drop_column("bank_transactions", "payment_channel")
    op.drop_column("bank_transactions", "receiving_routing")
    op.drop_column("bank_transactions", "originating_routing")
    op.drop_column("bank_transactions", "wire_reference")
    op.drop_column("bank_transactions", "ach_sec_code")
    op.drop_column("bank_transactions", "ach_trace_number")
