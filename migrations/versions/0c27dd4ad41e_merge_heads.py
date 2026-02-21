"""Merge heads

Revision ID: 0c27dd4ad41e
Revises: a105_create_cockpit_audit_logs_table, a200_fix_access_tokens_user_id_fk
Create Date: 2026-02-02 01:54:57.711709

"""

# revision identifiers, used by Alembic.
revision = "0c27dd4ad41e"
down_revision = (
    "a105_create_cockpit_audit_logs_table",
    "a200_fix_access_tokens_user_id_fk",
)
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
