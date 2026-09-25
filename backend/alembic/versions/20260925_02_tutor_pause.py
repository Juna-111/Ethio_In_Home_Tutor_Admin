"""Add tutor pause state for matching.

Revision ID: 20260925_02
Revises: 20260925_01
"""
from alembic import op
import sqlalchemy as sa


revision = "20260925_02"
down_revision = "20260925_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tutors",
        sa.Column("is_paused", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_tutors_is_paused", "tutors", ["is_paused"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_tutors_is_paused", table_name="tutors")
    op.drop_column("tutors", "is_paused")