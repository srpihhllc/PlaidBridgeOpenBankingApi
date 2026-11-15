
"""Add user-scoped Plaid transaction ID.



Revision ID: c1568b7e2b87

Revises: 88acc6dec986

"""



from alembic import op

import sqlalchemy as sa



revision = "c1568b7e2b87"

down_revision = "88acc6dec986"

branch_labels = None

depends_on = None





def upgrade():

    op.add_column(

        "transactions",

        sa.Column("plaid_transaction_id", sa.String(length=120), nullable=True),

    )

    op.create_unique_constraint(

        "uq_transactions_user_plaid_transaction",

        "transactions",

        ["user_id", "plaid_transaction_id"],

    )





def downgrade():

    op.drop_constraint(

        "uq_transactions_user_plaid_transaction",

        "transactions",

        type_="unique",

    )

    op.drop_column("transactions", "plaid_transaction_id")
