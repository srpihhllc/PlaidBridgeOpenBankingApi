
"""drop legacy financial_audit_log



Revision ID: b7f3c9d2a1e4

Revises: 31e81addce50

Create Date: 2026-05-13 01:40:00

"""

from alembic import op

import sqlalchemy as sa



# revision identifiers, used by Alembic.

revision = "b7f3c9d2a1e4"

down_revision = "31e81addce50"

branch_labels = None

depends_on = None



def upgrade():

    # Defensive: drop only if the table exists

    conn = op.get_bind()

    exists = conn.execute(sa.text(

        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = :schema AND table_name = :t"

    ), {"schema": conn.engine.url.database, "t": "financial_audit_log"}).scalar()

    if exists and int(exists) > 0:

        op.drop_table("financial_audit_log")



def downgrade():

    # Recreate minimal legacy table so downgrade is reversible (no data restored)

    op.create_table(

        "financial_audit_log",

        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),

        sa.Column("actor_id", sa.String(36), nullable=False),

        sa.Column("action_type", sa.String(64), nullable=False),

        sa.Column("description", sa.Text, nullable=True),

        sa.Column("created_at", sa.DateTime, nullable=False),

    )

