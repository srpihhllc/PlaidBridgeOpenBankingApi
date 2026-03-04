"""Change PlaidItem.access_token to Text

Revision ID: 20260301_plaid_access_token_text
Revises: <PREVIOUS_REVISION_ID>
Create Date: 2026-03-01
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260301_plaid_access_token_text"
down_revision = "<PREVIOUS_REVISION_ID>"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("plaid_items") as batch_op:
        batch_op.alter_column("access_token", type_=sa.Text(), existing_type=sa.String(length=256))


def downgrade():
    with op.batch_alter_table("plaid_items") as batch_op:
        batch_op.alter_column("access_token", type_=sa.String(length=256), existing_type=sa.Text())
