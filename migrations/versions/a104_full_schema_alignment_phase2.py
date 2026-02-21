"""Full schema alignment (phase 2: JSON, NOT NULL, new fields, constraints).

Revision ID: a104_full_schema_alignment_phase2
Revises: a103_recreate_user_foreign_keys_string_ids
Create Date: 2026-01-12 11:39:00
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = "a104_full_schema_alignment_phase2"
down_revision = "a103_recreate_user_foreign_keys_string_ids"
branch_labels = None
depends_on = None


def upgrade():
    # --- TODOS: tighten required fields ---
    op.alter_column(
        "todos",
        "text",
        existing_type=mysql.VARCHAR(length=255),
        nullable=False,
    )
    op.alter_column(
        "todos",
        "completed",
        existing_type=mysql.TINYINT(display_width=1),
        nullable=False,
    )
    op.alter_column(
        "todos",
        "priority",
        existing_type=mysql.VARCHAR(length=20),
        server_default=None,
        existing_nullable=False,
    )
    op.alter_column(
        "todos",
        "created_at",
        existing_type=mysql.DATETIME(),
        nullable=False,
    )
    op.alter_column(
        "todos",
        "updated_at",
        existing_type=mysql.DATETIME(),
        server_default=None,
        existing_nullable=False,
    )

    # --- USER_DASHBOARDS: convert settings to JSON + tighten timestamps ---
    op.alter_column(
        "user_dashboards",
        "settings",
        existing_type=mysql.TEXT(),
        type_=sa.JSON(),
        existing_nullable=True,
    )
    op.alter_column(
        "user_dashboards",
        "created_at",
        existing_type=mysql.DATETIME(),
        nullable=False,
    )
    op.alter_column(
        "user_dashboards",
        "updated_at",
        existing_type=mysql.DATETIME(),
        nullable=False,
    )

    # --- USERS: tighten booleans ---
    op.alter_column(
        "users",
        "is_approved",
        existing_type=mysql.TINYINT(display_width=1),
        server_default=None,
        existing_nullable=False,
    )
    op.alter_column(
        "users",
        "is_mfa_enabled",
        existing_type=mysql.TINYINT(display_width=1),
        server_default=None,
        existing_nullable=False,
    )

    # --- USERS: UUID uniqueness ---
    # Unique constraint creation removed — already exists in schema
    pass


def downgrade():
    # --- USERS: restore index + defaults ---
    op.drop_constraint(op.f("uq_users_uuid"), "users", type_="unique")
    op.create_index(op.f("idx_users_uuid"), "users", ["uuid"], unique=True)

    op.alter_column(
        "users",
        "is_mfa_enabled",
        existing_type=mysql.TINYINT(display_width=1),
        server_default=sa.text("'0'"),
        existing_nullable=False,
    )
    op.alter_column(
        "users",
        "is_approved",
        existing_type=mysql.TINYINT(display_width=1),
        server_default=sa.text("'1'"),
        existing_nullable=False,
    )

    # --- USER_DASHBOARDS: revert JSON + timestamps ---
    op.alter_column(
        "user_dashboards",
        "updated_at",
        existing_type=mysql.DATETIME(),
        nullable=True,
    )
    op.alter_column(
        "user_dashboards",
        "created_at",
        existing_type=mysql.DATETIME(),
        nullable=True,
    )
    op.alter_column(
        "user_dashboards",
        "settings",
        existing_type=sa.JSON(),
        type_=mysql.TEXT(),
        existing_nullable=True,
    )

    # --- TRANSACTIONS: remove metadata fields ---
    op.drop_column("transactions", "payment_meta")
    op.drop_column("transactions", "location")
    op.drop_column("transactions", "category_hierarchy")
    op.drop_column("transactions", "cluster")
    op.drop_column("transactions", "fraud_score")
    op.drop_column("transactions", "mcc")

    # --- TODOS: revert tightening ---
    op.alter_column(
        "todos",
        "updated_at",
        existing_type=mysql.DATETIME(),
        server_default=sa.text("CURRENT_TIMESTAMP"),
        existing_nullable=False,
    )
    op.alter_column(
        "todos",
        "created_at",
        existing_type=mysql.DATETIME(),
        nullable=True,
    )
    op.alter_column(
        "todos",
        "priority",
        existing_type=mysql.VARCHAR(length=20),
        server_default=sa.text("'normal'"),
        existing_nullable=False,
    )
    op.alter_column(
        "todos",
        "completed",
        existing_type=mysql.TINYINT(display_width=1),
        nullable=True,
    )
    op.alter_column(
        "todos",
        "text",
        existing_type=mysql.VARCHAR(length=255),
        nullable=True,
    )
