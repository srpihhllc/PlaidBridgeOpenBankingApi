"""Neutralized migration: audit_logs table already exists.

Revision ID: a105_create_cockpit_audit_logs_table
Revises: a104_full_schema_alignment_phase2
Create Date: 2026-01-12 11:40:00
"""

revision = "a105_create_cockpit_audit_logs_table"
down_revision = "a104_full_schema_alignment_phase2"
branch_labels = None
depends_on = None


def upgrade():
    # The audit_logs table is now created by the SQLAlchemy model.
    # This migration originally attempted to create a stub version of the table,
    # but the real cockpit-grade schema already exists in production.
    # Leaving this as a no-op preserves migration chain integrity.
    pass


def downgrade():
    # No-op: do not drop the audit_logs table.
    # The table is part of the active production schema.
    pass
